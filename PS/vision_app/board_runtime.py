"""Application factory assembled from frozen A0005 benchmark; Python 3.6."""
import os
import pathlib
import subprocess
import sys

RETAINED = '/root/network10-v10.5-a0005-retained-current'
PAYLOAD = '/root/workspace/network10-v10.5-a0005-board-validation-001'
LOADER = '/root/workspace/network10-v10.5-pl-loader/fz3b_pl_loader.py'


def create_runtime(contract):
    from .contract import sha_file
    if sha_file(RETAINED + '/suffix11-selection/selection-manifest.json') != contract['suffix_selection_sha256']:
        raise ValueError('PS suffix identity differs from application contract')
    os.environ['ORT_PARTITION_ALLOW_SPINNING'] = '0'
    os.environ['ORT_PARTITION_PREALLOC_OUTPUTS'] = '0'
    sys.path[:0] = [PAYLOAD + '/runtime', RETAINED + '/runtime-compat']
    from cnn_pipeline_v10_bundle import load_v10_release_bundle
    from cnn_pipeline_v10_signed40_deployment import load_v10_signed40_deployment, ADMISSION_SHA256, PROOF_SHA256
    from cnn_pipeline_v10_signed40_parameters import load_v10_signed40_parameters
    from cnn_ddr_v10_signed40_candidate_runtime import LinuxIoctlV10Signed40CandidateTransport
    from cnn_pipeline_v10_signed40_runtime import V10Signed40ChainMixin
    from cnn_pipeline_v10_mixed_runtime import build_v10_mixed_components, V10MixedBoundaryMixin
    from cnn_pipeline_v10_split_ps_runtime import V10SplitPsLiveRuntime

    subprocess.run(['python3', '-B', LOADER, 'prepare-a0005'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    loaded = load_v10_release_bundle(RETAINED + '/release', contract['bundle_sha256'])
    deployment = load_v10_signed40_deployment(PAYLOAD + '/deployment/manifest.json', contract['deployment_sha256'], loaded['manifest_sha256'], contract['combined_manifest_sha256'])
    params = load_v10_signed40_parameters(PAYLOAD + '/validation/contract/combined-manifest.json', contract['combined_manifest_sha256'], deployment['files']['signed40_admission'], ADMISSION_SHA256, deployment['files']['signed40_range_proof'], PROOF_SHA256)
    clients = transport = None
    try:
        clients, unused, kwargs, evidence = build_v10_mixed_components(loaded['model_root'], loaded['model_manifest'], loaded['model_manifest_sha256'], RETAINED + '/bin/ort_partition_runner_v3', threads=3, n1_manifest=None, suffix_candidate=RETAINED + '/suffix11-selection/selection-manifest.json', native_lib=RETAINED + '/bin/libcnn_v10_native_quant.so', partition_threads={'stem-prefix': 1, 'network1-bridge': 1, 'network3-bridge': 1, 'suffix': 3})
        kwargs.update(p3_dma_parameters=params, activation_upload_backend='direct_wc')
        words = tuple(int(contract['combined_manifest_sha256'][i:i+8], 16) for i in range(0, 64, 8))
        transport = LinuxIoctlV10Signed40CandidateTransport('/dev/network10_v10_signed40', expected_parameter_manifest_words=words, pw2_signed40_admission=params['pw2_signed40_admission'])
        class Runtime(V10Signed40ChainMixin, V10MixedBoundaryMixin, V10SplitPsLiveRuntime):
            pass
        return Runtime(transport, loaded['parameter_contract'], loaded['manifest_sha256'], clients, timeout_s=300, **kwargs)
    except BaseException:
        if transport is not None:
            transport.close()
        if clients is not None:
            for client in clients.values():
                client.close()
        raise
