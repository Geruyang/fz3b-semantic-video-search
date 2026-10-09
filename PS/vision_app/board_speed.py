"""Application factory speed with the frozen benchmark's exact timing scope."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import numpy as np
from .board_runtime import create_runtime, RETAINED
from .contract import load_contract


def cpu_state():
    from .cpu_clock_service import request
    state = request()
    if not state['verified'] or state['actual_hz'] != 1199999988:
        raise RuntimeError('speed test requires verified actual 1.2GHz')
    return state


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir()
    contract = load_contract('vision_app/semantic-contract.json')
    tensors = [np.fromfile(RETAINED + '/inputs/image-%02d-input.f32' % i, dtype='<f4').reshape(1,3,256,256) for i in range(2)]
    references = [np.fromfile(RETAINED + '/references/image-%02d-feature.f32' % i, dtype='<f4') for i in range(2)]
    expected = [hashlib.sha256(value.tobytes()).hexdigest() for value in references]
    before = cpu_state()
    runtime, result = None, {'ok':False,'cpu_before':before,'cpu_khz_before':before['actual_hz']//1000,'contract_id':contract['contract_id']}
    try:
        setup = time.perf_counter()
        runtime = create_runtime(contract)
        result['setup_s'] = time.perf_counter() - setup
        from benchmark_cnn_pipeline_v10_live import measure_live_phase
        result['warmup'] = measure_live_phase(runtime,tensors,expected,3,100000,4,references)
        result['measured'] = measure_live_phase(runtime,tensors,expected,100,200000,4,references,
                                                feature_dump_path=output/'measured-features.f32')
    finally:
        if runtime is not None:
            result['cleanup'] = runtime.close()
        result['cpu_after'] = cpu_state()
        result['cpu_khz_after'] = result['cpu_after']['actual_hz']//1000
        result['ok'] = 'measured' in result and result['cpu_after'] == before and all(result.get('cleanup',{}).get(key) for key in ('transport_closed','clients_closed','all_handles_freed','quiesce_confirmed'))
        result['scope'] = 'Two resident frozen tensors repeated for 100 pairs/200 real frames; includes pipeline fill/drain and result collection; excludes setup, image loading, JPEG/preprocessing and feature validation.'
        (output/'result.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({'ok':result['ok'],'cpu_khz':before['actual_hz']//1000,'cpu_actual_hz':before['actual_hz'],'cpu_verified':before['verified'],'setup_s':result['setup_s'],
                      'frames':result['measured']['real_frames'],'seconds':result['measured']['execution_ms']/1000,
                      'fps':result['measured']['fps_including_fill_and_drain'],'output':str(output)}))
    if not result['ok']:
        raise RuntimeError('speed or lifecycle qualification failed')


if __name__ == '__main__':
    main()
