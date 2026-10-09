#define _POSIX_C_SOURCE 200809L
#include <onnxruntime_c_api.h>
#include <errno.h>
#include <inttypes.h>
#include <math.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

/* The CPU partition protocol is intentionally bounded: <= 8 inputs and
 * outputs, <= 64 MiB per tensor, and <= 128 MiB in either direction. */
enum { MAX_TENSORS = 8, MAX_RANK = 8 };
#define MAX_TENSOR_BYTES ((size_t)64 * 1024 * 1024)
#define MAX_TOTAL_BYTES  ((size_t)128 * 1024 * 1024)

typedef struct {
    char *name;
    size_t rank;
    int64_t dims[MAX_RANK];
    size_t bytes;
    float *data;
    OrtValue *value;
} Tensor;

static const OrtApi *g_api;

enum { SHM_DATA_OFFSET = 64 };

static int env_bool(const char *name, int fallback, int *value) {
    const char *text = getenv(name);
    if (!text || !*text) { *value = fallback; return 1; }
    if (strcmp(text, "0") == 0) { *value = 0; return 1; }
    if (strcmp(text, "1") == 0) { *value = 1; return 1; }
    fprintf(stderr, "%s must be 0 or 1\n", name);
    return 0;
}

static void report_status(OrtStatus *status, const char *where) {
    if (status) {
        fprintf(stderr, "%s: %s\n", where, g_api->GetErrorMessage(status));
        g_api->ReleaseStatus(status);
    }
}

#define ORT_TRY(expr, label) do { OrtStatus *s_ = (expr); if (s_) { report_status(s_, label); goto cleanup; } } while (0)

static double elapsed_ms(struct timespec a, struct timespec b) {
    return (double)(b.tv_sec - a.tv_sec) * 1000.0 +
           (double)(b.tv_nsec - a.tv_nsec) / 1000000.0;
}

static int read_exact(FILE *stream, unsigned char *dst, size_t count) {
    size_t have = 0;
    while (have < count) {
        size_t got = fread(dst + have, 1, count - have, stream);
        have += got;
        if (have == count) return 1;
        if (ferror(stream)) return -1;
        if (feof(stream)) return have == 0 ? 0 : -1;
    }
    return 1;
}

static void json_string(const char *s) {
    putchar('"');
    for (; *s; ++s) {
        unsigned char c = (unsigned char)*s;
        if (c == '"' || c == '\\') { putchar('\\'); putchar(c); }
        else if (c < 0x20) printf("\\u%04x", (unsigned)c);
        else putchar(c);
    }
    putchar('"');
}

static int describe_tensors(OrtSession *session, OrtAllocator *allocator,
                            OrtMemoryInfo *memory, int inputs, Tensor *tensors,
                            size_t *total_bytes, int preallocate_outputs) {
    size_t count = 0;
    OrtStatus *status = inputs ? g_api->SessionGetInputCount(session, &count)
                               : g_api->SessionGetOutputCount(session, &count);
    if (status) { report_status(status, inputs ? "SessionGetInputCount" : "SessionGetOutputCount"); return -1; }
    if (count == 0 || count > MAX_TENSORS) {
        fprintf(stderr, "%s count must be in [1,%d], got %zu\n", inputs ? "input" : "output", MAX_TENSORS, count);
        return -1;
    }
    *total_bytes = 0;
    for (size_t i = 0; i < count; ++i) {
        OrtTypeInfo *type_info = NULL;
        const OrtTensorTypeAndShapeInfo *tensor_info = NULL;
        ONNXTensorElementDataType elem_type;
        size_t rank = 0, elements = 1;
        status = inputs ? g_api->SessionGetInputTypeInfo(session, i, &type_info)
                        : g_api->SessionGetOutputTypeInfo(session, i, &type_info);
        if (status) { report_status(status, "SessionGet*TypeInfo"); return -1; }
        status = g_api->CastTypeInfoToTensorInfo(type_info, &tensor_info);
        if (status) { report_status(status, "CastTypeInfoToTensorInfo"); g_api->ReleaseTypeInfo(type_info); return -1; }
        if (tensor_info == NULL) {
            fprintf(stderr, "%s %zu is not a tensor\n", inputs ? "input" : "output", i);
            g_api->ReleaseTypeInfo(type_info); return -1;
        }
        status = g_api->GetTensorElementType(tensor_info, &elem_type);
        if (!status) status = g_api->GetDimensionsCount(tensor_info, &rank);
        if (status) { report_status(status, "tensor metadata"); g_api->ReleaseTypeInfo(type_info); return -1; }
        if (elem_type != ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT || rank == 0 || rank > MAX_RANK) {
            fprintf(stderr, "%s %zu must be a ranked float32 tensor\n", inputs ? "input" : "output", i);
            g_api->ReleaseTypeInfo(type_info); return -1;
        }
        Tensor *t = &tensors[i];
        t->rank = rank;
        status = g_api->GetDimensions(tensor_info, t->dims, rank);
        if (status) { report_status(status, "GetDimensions"); g_api->ReleaseTypeInfo(type_info); return -1; }
        for (size_t d = 0; d < rank; ++d) {
            if (t->dims[d] <= 0 || (uint64_t)t->dims[d] > SIZE_MAX / elements) {
                fprintf(stderr, "%s %zu has a dynamic, non-positive, or overflowing dimension\n", inputs ? "input" : "output", i);
                g_api->ReleaseTypeInfo(type_info); return -1;
            }
            elements *= (size_t)t->dims[d];
        }
        if (elements > SIZE_MAX / sizeof(float)) { g_api->ReleaseTypeInfo(type_info); return -1; }
        t->bytes = elements * sizeof(float);
        if (t->bytes > MAX_TENSOR_BYTES || *total_bytes > MAX_TOTAL_BYTES - t->bytes) {
            fprintf(stderr, "%s byte limit exceeded\n", inputs ? "input" : "output");
            g_api->ReleaseTypeInfo(type_info); return -1;
        }
        *total_bytes += t->bytes;
        status = inputs ? g_api->SessionGetInputName(session, i, allocator, &t->name)
                        : g_api->SessionGetOutputName(session, i, allocator, &t->name);
        g_api->ReleaseTypeInfo(type_info);
        if (status) { report_status(status, "SessionGet*Name"); return -1; }
        if (inputs || preallocate_outputs) {
            t->data = (float *)malloc(t->bytes);
            if (!t->data) { fprintf(stderr, "tensor allocation failed\n"); return -1; }
            status = g_api->CreateTensorWithDataAsOrtValue(memory, t->data, t->bytes,
                t->dims, t->rank, ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT, &t->value);
            if (status) { report_status(status, "CreateTensorWithDataAsOrtValue"); return -1; }
        }
    }
    return (int)count;
}

static void emit_tensor_array(Tensor *tensors, int count) {
    putchar('[');
    for (int i = 0; i < count; ++i) {
        if (i) putchar(',');
        printf("{\"name\":"); json_string(tensors[i].name);
        printf(",\"shape\":[");
        for (size_t d = 0; d < tensors[i].rank; ++d) {
            if (d) putchar(',');
            printf("%" PRId64, tensors[i].dims[d]);
        }
        printf("],\"dtype\":\"float32\",\"bytes\":%zu}", tensors[i].bytes);
    }
    putchar(']');
}

static int shm_main(int argc, char **argv) {
    int rc = 2, input_count = 0, output_count = 0;
    long threads;
    char *end = NULL;
    OrtEnv *env = NULL; OrtSessionOptions *options = NULL; OrtSession *session = NULL;
    OrtMemoryInfo *memory = NULL; OrtAllocator *allocator = NULL;
    unsigned char *mapping = MAP_FAILED;
    size_t mapping_bytes = 0;
    Tensor inputs[MAX_TENSORS] = {{0}}, outputs[MAX_TENSORS] = {{0}};
    size_t input_bytes = 0, output_bytes = 0;
    int allow_spinning = 0, preallocate_outputs = 0;
    if (argc != 5) {
        fprintf(stderr, "usage: %s --shm FD MODEL.onnx THREADS\n", argv[0]); return 2;
    }
    char *fd_end = NULL;
    long shm_fd = strtol(argv[2], &fd_end, 10);
    if (fd_end == argv[2] || *fd_end || shm_fd < 0 || shm_fd > INT32_MAX) {
        fprintf(stderr, "invalid shared-memory fd\n"); return 2;
    }
    threads = strtol(argv[4], &end, 10);
    if (end == argv[4] || *end || threads < 1 || threads > 8) {
        fprintf(stderr, "threads must be in [1,8]\n"); return 2;
    }
    if (!env_bool("ORT_PARTITION_ALLOW_SPINNING", 0, &allow_spinning) ||
        !env_bool("ORT_PARTITION_PREALLOC_OUTPUTS", 0, &preallocate_outputs)) return 2;
    const uint32_t one = 1;
    if (*(const unsigned char *)&one != 1) { fprintf(stderr, "protocol requires little-endian host\n"); return 2; }
    const OrtApiBase *base = OrtGetApiBase();
    g_api = base ? base->GetApi(ORT_API_VERSION) : NULL;
    if (!g_api) { fprintf(stderr, "ORT C API version %d unavailable\n", ORT_API_VERSION); return 2; }
    ORT_TRY(g_api->CreateEnv(ORT_LOGGING_LEVEL_WARNING, "ort-partition-runner", &env), "CreateEnv");
    ORT_TRY(g_api->CreateSessionOptions(&options), "CreateSessionOptions");
    ORT_TRY(g_api->SetIntraOpNumThreads(options, (int)threads), "SetIntraOpNumThreads");
    ORT_TRY(g_api->SetInterOpNumThreads(options, 1), "SetInterOpNumThreads");
    ORT_TRY(g_api->SetSessionExecutionMode(options, ORT_SEQUENTIAL), "SetSessionExecutionMode");
    ORT_TRY(g_api->SetSessionGraphOptimizationLevel(options, ORT_ENABLE_ALL), "SetSessionGraphOptimizationLevel");
    ORT_TRY(g_api->AddSessionConfigEntry(options, "session.intra_op.allow_spinning",
                                         allow_spinning ? "1" : "0"),
            "AddSessionConfigEntry(intra_op.allow_spinning)");
    ORT_TRY(g_api->AddSessionConfigEntry(options, "session.inter_op.allow_spinning",
                                         allow_spinning ? "1" : "0"),
            "AddSessionConfigEntry(inter_op.allow_spinning)");
    struct timespec load_start, load_end;
    clock_gettime(CLOCK_MONOTONIC, &load_start);
    ORT_TRY(g_api->CreateSession(env, argv[3], options, &session), "CreateSession");
    clock_gettime(CLOCK_MONOTONIC, &load_end);
    ORT_TRY(g_api->GetAllocatorWithDefaultOptions(&allocator), "GetAllocatorWithDefaultOptions");
    ORT_TRY(g_api->CreateCpuMemoryInfo(OrtArenaAllocator, OrtMemTypeDefault, &memory), "CreateCpuMemoryInfo");
    input_count = describe_tensors(session, allocator, memory, 1, inputs, &input_bytes, 0);
    if (input_count < 1) goto cleanup;
    output_count = describe_tensors(session, allocator, memory, 0, outputs, &output_bytes,
                                    preallocate_outputs);
    if (output_count < 1) goto cleanup;
    struct stat shm_stat;
    if (fstat((int)shm_fd, &shm_stat) != 0 || shm_stat.st_size < 0 ||
        (uintmax_t)shm_stat.st_size != (uintmax_t)SHM_DATA_OFFSET + input_bytes + output_bytes) {
        fprintf(stderr, "shared-memory file size mismatch\n"); goto cleanup;
    }
    mapping_bytes = (size_t)shm_stat.st_size;
    mapping = (unsigned char *)mmap(NULL, mapping_bytes, PROT_READ | PROT_WRITE,
                                    MAP_SHARED, (int)shm_fd, 0);
    if (mapping == MAP_FAILED) { perror("mmap"); goto cleanup; }
    if (memcmp(mapping, "ORTSHM3", 7) != 0 || mapping[7] != 0 ||
        mapping[8] != 3 || mapping[9] != 0 || mapping[10] != 0 || mapping[11] != 0) {
        fprintf(stderr, "shared-memory protocol header mismatch\n"); goto cleanup;
    }
    printf("{\"kind\":\"ready\",\"protocol\":3,\"ort_version\":"); json_string(base->GetVersionString());
    printf(",\"api_version\":%d,\"threads\":%ld,\"load_ms\":%.3f,"
           "\"allow_spinning\":%s,\"preallocated_outputs\":%s,"
           "\"input_bytes\":%zu,\"output_bytes\":%zu,\"inputs\":",
           ORT_API_VERSION, threads, elapsed_ms(load_start, load_end),
           allow_spinning ? "true" : "false",
           preallocate_outputs ? "true" : "false", input_bytes, output_bytes);
    emit_tensor_array(inputs, input_count); printf(",\"outputs\":"); emit_tensor_array(outputs, output_count);
    putchar('}'); putchar('\n');
    if (fflush(stdout) != 0) { fprintf(stderr, "startup header write failed\n"); goto cleanup; }

    const char *input_names[MAX_TENSORS], *output_names[MAX_TENSORS];
    const OrtValue *input_values[MAX_TENSORS];
    for (int i = 0; i < input_count; ++i) { input_names[i] = inputs[i].name; input_values[i] = inputs[i].value; }
    for (int i = 0; i < output_count; ++i) output_names[i] = outputs[i].name;
    uint64_t request_id = 0;
    for (;;) {
        uint64_t incoming_id = 0;
        int got = read_exact(stdin, (unsigned char *)&incoming_id, sizeof(incoming_id));
        if (got == 0) break;
        if (got != 1 || incoming_id != request_id + 1) { fprintf(stderr, "invalid/truncated request id\n"); goto cleanup; }
        size_t input_offset = SHM_DATA_OFFSET;
        for (int i = 0; i < input_count; ++i) {
            memcpy(inputs[i].data, mapping + input_offset, inputs[i].bytes);
            input_offset += inputs[i].bytes;
        }
        for (int i = 0; i < input_count; ++i)
            for (size_t j = 0; j < inputs[i].bytes / sizeof(float); ++j)
                if (!isfinite(inputs[i].data[j])) { fprintf(stderr, "non-finite input %d index %zu\n", i, j); goto cleanup; }
        OrtValue *result[MAX_TENSORS] = {0};
        if (preallocate_outputs)
            for (int i = 0; i < output_count; ++i) result[i] = outputs[i].value;
        struct timespec start, finish;
        clock_gettime(CLOCK_MONOTONIC, &start);
        OrtStatus *status = g_api->Run(session, NULL, input_names, input_values, (size_t)input_count,
                                       output_names, (size_t)output_count, result);
        clock_gettime(CLOCK_MONOTONIC, &finish);
        if (status) { report_status(status, "Run"); goto cleanup; }
        int outputs_ok = 1;
        size_t output_offset = SHM_DATA_OFFSET + input_bytes;
        for (int i = 0; i < output_count && outputs_ok; ++i) {
            OrtTensorTypeAndShapeInfo *info = NULL;
            ONNXTensorElementDataType type; size_t rank = 0, count = 0;
            int64_t dims[MAX_RANK]; float *data = NULL;
            status = g_api->GetTensorTypeAndShape(result[i], &info);
            if (!status) status = g_api->GetTensorElementType(info, &type);
            if (!status) status = g_api->GetDimensionsCount(info, &rank);
            if (!status && rank > MAX_RANK) {
                fprintf(stderr, "output %d rank exceeds protocol limit\n", i); outputs_ok = 0;
            }
            if (!status && outputs_ok) status = g_api->GetDimensions(info, dims, rank);
            if (!status) status = g_api->GetTensorShapeElementCount(info, &count);
            if (status) { report_status(status, "output metadata"); outputs_ok = 0; }
            else if (outputs_ok && count > SIZE_MAX / sizeof(float)) {
                fprintf(stderr, "output %d element count overflows byte size\n", i); outputs_ok = 0;
            }
            else if (outputs_ok && (type != ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT || rank != outputs[i].rank || count * sizeof(float) != outputs[i].bytes ||
                     memcmp(dims, outputs[i].dims, rank * sizeof(int64_t)) != 0)) {
                fprintf(stderr, "output %d type/shape changed after Run\n", i); outputs_ok = 0;
            }
            if (outputs_ok) {
                status = g_api->GetTensorMutableData(result[i], (void **)&data);
                if (status) { report_status(status, "GetTensorMutableData"); outputs_ok = 0; }
                for (size_t j = 0; outputs_ok && j < outputs[i].bytes / sizeof(float); ++j)
                    if (!isfinite(data[j])) { fprintf(stderr, "non-finite output %d index %zu\n", i, j); outputs_ok = 0; }
                if (outputs_ok) memcpy(mapping + output_offset, data, outputs[i].bytes);
            }
            output_offset += outputs[i].bytes;
            if (info) g_api->ReleaseTensorTypeAndShapeInfo(info);
        }
        if (!preallocate_outputs)
            for (int i = 0; i < output_count; ++i) if (result[i]) g_api->ReleaseValue(result[i]);
        if (!outputs_ok) goto cleanup;
        ++request_id;
        printf("{\"kind\":\"result\",\"request_id\":%" PRIu64 ",\"run_ms\":%.3f}\n", request_id, elapsed_ms(start, finish));
        if (fflush(stdout) != 0) { fprintf(stderr, "result header write failed\n"); goto cleanup; }
    }
    rc = 0;
cleanup:
    if (mapping != MAP_FAILED) munmap(mapping, mapping_bytes);
    for (int i = 0; i < MAX_TENSORS; ++i) {
        if (inputs[i].value) g_api->ReleaseValue(inputs[i].value);
        if (outputs[i].value) g_api->ReleaseValue(outputs[i].value);
        if (inputs[i].name && allocator) allocator->Free(allocator, inputs[i].name);
        if (outputs[i].name && allocator) allocator->Free(allocator, outputs[i].name);
        free(inputs[i].data); free(outputs[i].data);
    }
    if (memory) g_api->ReleaseMemoryInfo(memory);
    if (session) g_api->ReleaseSession(session);
    if (options) g_api->ReleaseSessionOptions(options);
    if (env) g_api->ReleaseEnv(env);
    return rc;
}

int main(int argc, char **argv) {
    if (argc > 1 && strcmp(argv[1], "--shm") == 0) return shm_main(argc, argv);
    fprintf(stderr, "usage: %s --shm FD MODEL.onnx THREADS\n", argv[0]);
    return 2;
}
