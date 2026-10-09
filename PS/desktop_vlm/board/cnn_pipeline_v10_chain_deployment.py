"""Explicit A0002 deployment gate for the shared-arena N0/N1/N2 chain.

This is an offline artifact check. It never loads a module or programs PL.
The parameter loader separately checks the P3 arithmetic/model evidence.
"""
import json

try:
    from cnn_pipeline_v10_deployment import (
        KERNEL_RELEASE, _checked_sha, _load_platform_package)
except ImportError:
    from .cnn_pipeline_v10_deployment import (
        KERNEL_RELEASE, _checked_sha, _load_platform_package)


SCHEMA = 'cnn-pipeline-v10.1-pl-chain-deployment-v1'
IDENTITY = dict(core_id='0x465A5641', core_abi='0x000A0002',
                guard_caps='0x000007FF', software_uapi=10)
TARGET = dict(kernel_release=KERNEL_RELEASE,
              device='/dev/network10_v10_p3', module='cnn_ddr_v10_p3_candidate')
CHAIN_CONTRACT = {
    'profiles': [2, 3, 0], 'arena_words': 69632, 'word_bits': 128,
    'p3': {'profile': 3, 'blocks': 1, 'flags': 0, 'params_words': 11280,
           'input_offset_words': 0, 'input_words': 32768,
           'intermediate_offset_words': 32768, 'intermediate_words': 16384,
           'output_offset_words': 0, 'output_words': 16384,
           'slot_words': 32768},
    'p0_base_offset_words': 0,
}
EXTRA_FILES = {'chain_parameter_manifest'}
EXTRA_GATES = {'p3_native_integer_exact', 'p3_rtl_integer_exact',
               'p3_chain_memory_bounds_pass'}


def load_v10_chain_deployment(manifest_path, expected_manifest_sha256,
                              expected_release_manifest_sha256,
                              expected_chain_manifest_sha256):
    expected_chain = _checked_sha(expected_chain_manifest_sha256,
                                  'combined chain parameter manifest')
    loaded = _load_platform_package(
        manifest_path, expected_manifest_sha256, expected_release_manifest_sha256,
        SCHEMA, IDENTITY, TARGET, EXTRA_FILES, EXTRA_GATES)
    manifest = loaded['manifest']
    # Compare serialized data as well as equality so bool cannot impersonate an
    # integer size/profile (Python considers True == 1).
    contract = manifest.get('chain_contract')
    if (not isinstance(contract, dict) or
            json.dumps(contract, sort_keys=True, allow_nan=False) !=
            json.dumps(CHAIN_CONTRACT, sort_keys=True, allow_nan=False)):
        raise ValueError('P3 shared-arena chain contract mismatch')
    if (manifest.get('chain_parameter_manifest_sha256') != expected_chain or
            manifest['files']['chain_parameter_manifest']['sha256'] != expected_chain):
        raise ValueError('combined chain parameter manifest binding mismatch')
    loaded['chain_manifest_sha256'] = expected_chain
    return loaded


__all__ = ['SCHEMA', 'IDENTITY', 'TARGET', 'CHAIN_CONTRACT', 'EXTRA_FILES',
           'EXTRA_GATES', 'load_v10_chain_deployment']
