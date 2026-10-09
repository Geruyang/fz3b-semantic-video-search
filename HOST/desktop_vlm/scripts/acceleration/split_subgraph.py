"""Extract a contiguous ONNX region, retaining all live residual branches.

The three CPU sessions verify the partition before a PL implementation replaces
the middle session. This does not claim PL execution or performance improvement.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort
from onnxruntime.tools.symbolic_shape_infer import SymbolicShapeInference


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--model', required=True)
    ap.add_argument('--expected-model-sha256', required=True)
    ap.add_argument('--first-node', required=True)
    ap.add_argument('--last-node', required=True)
    ap.add_argument('--input', action='append', required=True)
    ap.add_argument('--output', required=True)
    ap.add_argument('--threads', type=int, choices=(1, 2, 4), default=2)
    args = ap.parse_args()
    if sha(args.model) != args.expected_model_sha256:
        raise ValueError('model identity mismatch')
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=False)
    model = SymbolicShapeInference.infer_shapes(onnx.load(args.model), auto_merge=True)
    nodes = list(model.graph.node)
    first = [i for i,n in enumerate(nodes) if n.name == args.first_node]
    last = [i for i,n in enumerate(nodes) if n.name == args.last_node]
    if len(first) != 1 or len(last) != 1 or not 0 < first[0] <= last[0] < len(nodes)-1:
        raise ValueError('requires unique interior first and last node in topological order')
    lo, hi = first[0], last[0]
    initial = {x.name for x in model.graph.initializer}
    constants = {x for n in nodes if n.op_type == 'Constant' for x in n.output}
    static = initial | constants
    producer = {x:i for i,n in enumerate(nodes) for x in n.output}
    # Determine a cut's live dynamic tensors, not just the last node's output.
    def live_at(cut):
        needed = set(v.name for v in model.graph.output)
        needed.update(x for n in nodes[cut:] for x in n.input if x)
        return sorted(x for x in needed if x not in static and producer.get(x,-1) < cut)
    cut1, cut2 = live_at(lo), live_at(hi+1)
    middle_inputs = sorted({x for n in nodes[lo:hi+1] for x in n.input
                            if x and x not in static and producer.get(x,-1) < lo})
    middle_outputs = [x for x in cut2 if lo <= producer.get(x,-1) <= hi]
    bypass = [x for x in cut2 if producer.get(x,-1) < lo]
    extractor = onnx.utils.Extractor(model)
    stages = [('prefix', [x.name for x in model.graph.input], cut1),
              ('region', middle_inputs, middle_outputs),
              ('suffix', cut2, [x.name for x in model.graph.output])]
    options = ort.SessionOptions()
    options.intra_op_num_threads = args.threads
    options.inter_op_num_threads = 1
    ort.disable_telemetry_events()
    sessions = []
    stage_info = []
    info = {v.name:v for v in list(model.graph.input)+list(model.graph.value_info)+list(model.graph.output)}
    def describe(name):
        t = info[name].type.tensor_type
        dims = [d.dim_value for d in t.shape.dim]
        if t.elem_type != onnx.TensorProto.FLOAT or not all(dims):
            raise ValueError('this ABI prototype requires fixed FP32 boundaries: '+name)
        return {'name':name, 'shape':dims, 'bytes_fp32':int(np.prod(dims))*4}
    for name, ins, outs in stages:
        graph = extractor.extract_model(ins, outs)
        onnx.checker.check_model(graph)
        file = out/(name+'.onnx')
        onnx.save(graph, str(file))
        sessions.append(ort.InferenceSession(str(file), options, providers=['CPUExecutionProvider']))
        stage_info.append({'stage':name,'inputs':[describe(x) for x in ins],
                           'outputs':[describe(x) for x in outs], 'nodes':len(graph.graph.node),
                           'sha256':sha(file), 'bytes':file.stat().st_size})
    original = ort.InferenceSession(args.model, options, providers=['CPUExecutionProvider'])
    validations = []
    for index,path in enumerate(args.input):
        x = np.fromfile(path, '<f4')
        if x.size != 3*256*256 or not np.isfinite(x).all():
            raise ValueError('invalid NCHW input')
        x=x.reshape(1,3,256,256)
        expected=original.run(None, {'image':x})[0]
        values={'image':x}
        for session in sessions:
            inputs={v.name:values[v.name] for v in session.get_inputs()}
            outputs=session.run(None, inputs)
            values.update({v.name:a for v,a in zip(session.get_outputs(),outputs)})
        actual=values['features']
        np.testing.assert_allclose(actual, expected, rtol=1e-3, atol=1e-4)
        actual.astype('<f4').tofile(out/('sample-%02d-features.f32'%index))
        validations.append({'input':str(Path(path).resolve()), 'input_sha256':sha(path),
                            'feature_max_abs':float(np.max(np.abs(actual-expected)))})
    report={'status':'CPU_PARTITION_VALIDATED_NOT_PL', 'source_sha256':sha(args.model),
            'ort_threads':args.threads,
            'first_node':args.first_node, 'last_node':args.last_node,
            'middle_node_names':[n.name for n in nodes[lo:hi+1]],
            'bypass_tensors':[describe(x) for x in bypass], 'stages':stage_info,
            'validation':validations}
    (out/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
