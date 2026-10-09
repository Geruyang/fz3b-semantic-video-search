"""Fixed tensor regression through the application factory, not benchmark CLI."""
import json
import hashlib
import numpy as np
from .board_runtime import create_runtime, RETAINED, PAYLOAD
from .contract import load_contract


def main():
    contract = load_contract('vision_app/semantic-contract.json')
    tensors = [np.fromfile(RETAINED + '/inputs/image-%02d-input.f32' % i, dtype='<f4').reshape(1, 3, 256, 256) for i in range(2)]
    references = [np.fromfile(RETAINED + '/references/image-%02d-feature.f32' % i, dtype='<f4') for i in range(2)]
    runtime = create_runtime(contract)
    records = []
    try:
        from benchmark_cnn_pipeline_v10_live import compare_feature
        with runtime.iter_results([(i, value) for i, value in enumerate(tensors)], max_in_flight=4, record_history=False) as stream:
            for output in stream:
                i = output['frame_id']
                reference = references[i]
                record = compare_feature(output['features'], hashlib.sha256(reference.tobytes()).hexdigest(), reference, min_cosine=.999, max_relative_l2=.05)
                record['frame_id'] = i
                records.append(record)
    finally:
        runtime.close()
    if len(records) != 2:
        raise RuntimeError('incomplete application regression')
    print(json.dumps({'ok': True, 'contract_id': contract['contract_id'], 'records': records}))


if __name__ == '__main__':
    main()
