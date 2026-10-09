#pragma once

// Fixed-model, lossless GELU compression contract for cnn_pipeline_v10.
// Bounds were proved against the 36 frozen v5 W16 parameter tables listed in
// artifacts/.../host/v8-resource-analysis-001/gelu-scan.json.  Unknown
// profile/block keys are rejected; callers must never substitute a default.
namespace cnn_v10 {

static const unsigned kGeluEntries = 65536u;
static const unsigned kGeluPerWord = 8u;       // 128-bit word / signed16
static const unsigned kGeluStorageEntries = 56256u;
static const unsigned kGeluStorageWords = 7032u;

struct GeluBound {
    unsigned zero_prefix;  // [0, zero_prefix) is exactly signed16 zero.
    unsigned tail_start;   // [tail_start, 65536) is exactly signed16 32767.
};

// Return the only accepted fixed-model bound.  The output is unchanged for an
// invalid key so an erroneous caller cannot accidentally use a fallback table.
static inline bool gelu_bound(unsigned profile, unsigned block, GeluBound& out) {
#pragma HLS INLINE
    static const unsigned zero0[12] = {
        15136u, 7424u, 7109u, 1949u, 0u, 0u,
        2420u, 0u, 0u, 6159u, 4602u, 25501u
    };
    static const unsigned tail0[12] = {
        52936u, 48646u, 48845u, 53151u, 49881u, 48536u,
        47407u, 53999u, 50477u, 45132u, 49941u, 38148u
    };
    static const unsigned zero1[20] = {
        1756u, 4433u, 6077u, 6559u, 8485u, 10116u, 9466u,
        11635u, 8084u, 5675u, 0u, 292u, 4914u, 13445u,
        11670u, 17357u, 19327u, 18908u, 19032u, 19136u
    };
    static const unsigned tail1[20] = {
        48704u, 51761u, 54883u, 52628u, 53218u, 49106u, 50628u,
        56097u, 53282u, 48134u, 56252u, 53479u, 56320u, 57196u,
        50287u, 50325u, 51714u, 52132u, 59373u, 61454u
    };
    static const unsigned zero2[4] = {25496u, 16299u, 13211u, 17193u};
    static const unsigned tail2[4] = {50236u, 55552u, 49509u, 52328u};

    GeluBound selected;
    if (profile == 0u) {
        if (block >= 12u) return false;
        selected.zero_prefix = zero0[block];
        selected.tail_start = tail0[block];
    } else if (profile == 1u) {
        if (block >= 20u) return false;
        selected.zero_prefix = zero1[block];
        selected.tail_start = tail1[block];
    } else if (profile == 2u) {
        if (block >= 4u) return false;
        selected.zero_prefix = zero2[block];
        selected.tail_start = tail2[block];
    } else {
        return false;
    }
    out = selected;
    return true;
}

static inline unsigned gelu_load_begin(const GeluBound& bound) {
#pragma HLS INLINE
    return bound.zero_prefix & ~7u;
}

static inline unsigned gelu_load_end(const GeluBound& bound) {
#pragma HLS INLINE
    return (bound.tail_start + 7u) & ~7u;
}

static inline unsigned gelu_load_words(const GeluBound& bound) {
#pragma HLS INLINE
    return (gelu_load_end(bound) - gelu_load_begin(bound)) / kGeluPerWord;
}

// ABI10 stores the compact table at a fixed slot, with the aligned retained
// interval starting at entry zero of that slot.
static inline unsigned gelu_table_word_offset(unsigned channels) {
#pragma HLS INLINE
    return (220u * channels + 16u) / 16u;
}

// Source offset within one ABI10 block for the aligned compact load.
static inline unsigned gelu_load_source_word_offset(unsigned channels,
                                                    const GeluBound& bound) {
#pragma HLS INLINE
    (void)bound;
    return gelu_table_word_offset(channels);
}

// Valid only for an index in [zero_prefix, tail_start).  Keeping this helper
// explicit lets the pointwise loop use one subtract for the compact BRAM.
static inline unsigned gelu_lookup_offset(unsigned index,
                                          const GeluBound& bound) {
#pragma HLS INLINE
    return index - gelu_load_begin(bound);
}

template<typename Pixel>
static inline Pixel gelu_lookup(const Pixel* compact, unsigned index,
                                const GeluBound& bound) {
#pragma HLS INLINE
    if (index < bound.zero_prefix) return Pixel(0);
    if (index >= bound.tail_start) return Pixel(32767);
    return compact[gelu_lookup_offset(index, bound)];
}

// Metadata preflight applies this predicate to every lane in each clipped
// prefix/tail word before any activation read or write is issued.  Middle
// values are intentionally unconstrained and are loaded bit-for-bit.
template<typename Pixel>
static inline bool gelu_clipped_value_valid(unsigned index, Pixel value,
                                            const GeluBound& bound) {
#pragma HLS INLINE
    if (index < bound.zero_prefix) return value == Pixel(0);
    if (index >= bound.tail_start) return value == Pixel(32767);
    return true;
}

}  // namespace cnn_v10

