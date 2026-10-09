#!/usr/bin/env python3
from __future__ import print_function
import argparse, json, sys

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--config',required=True); args=parser.parse_args()
    config=json.load(open(args.config))
    for path in reversed(config['paths']['runtime_python_paths']): sys.path.insert(0,path)
    from cnn_pipeline_v10_signed40_parameters import load_v10_signed40_parameters
    from cnn_ddr_v10_signed40_candidate_runtime import open_signed40_candidate
    assets=config['assets']; expected=config['identity']
    params=load_v10_signed40_parameters(
        assets['combined_manifest']['path'], assets['combined_manifest']['sha256'],
        assets['admission']['path'], assets['admission']['sha256'],
        assets['range_proof']['path'], assets['range_proof']['sha256'])
    transport=open_signed40_candidate(params, config['paths']['a0005_device'])
    try:
        identity=dict(transport.identity)
        words=list(identity['parameter_manifest_words']); identity['parameter_manifest_words']=words
        assert identity['core_id']==int(expected['core_id'],16)
        assert identity['core_abi']==int(expected['core_abi'],16)
        assert identity['guard_caps']==int(expected['guard_caps'],16)
        assert identity['abi_version']==expected['software_uapi']
        assert identity['profile_count']==4
        assert words==list(params['parameter_manifest_words'])
        result={'schema':'fz3b-v10.5-loader-strict-identity-v1','pass':True,
                'identity':identity,'combined_manifest_sha256':params['manifest_sha256']}
        print(json.dumps(result,sort_keys=True))
    finally: transport.close()

if __name__=='__main__': main()
