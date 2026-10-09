"""Real two-pointwise GELU FFN integer emulation; engineering smoke only.

Quantization ranges are intentionally estimated from the supplied smoke inputs,
not advertised as representative calibration or held-out accuracy. Residual and
layer-scale remain float32 at the region boundary. Requires split_subgraph output.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import onnx
from onnx import numpy_helper
import onnxruntime as ort
from onnxruntime.tools.symbolic_shape_infer import SymbolicShapeInference

from integer_postops import gelu_lut, multiplier_shift, requantize
from prepare_pointwise import error, quantize, sha, symmetric_scale


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--partition',required=True)
    ap.add_argument('--input',action='append',required=True)
    ap.add_argument('--output',required=True)
    args=ap.parse_args()
    base=Path(args.partition)
    partition=json.loads((base/'manifest.json').read_text(encoding='utf-8'))
    for stage in partition['stages']:
        if sha(base/(stage['stage']+'.onnx')) != stage['sha256']:
            raise ValueError('partition model hash mismatch')
    out=Path(args.output);out.mkdir(parents=True,exist_ok=False)
    options=ort.SessionOptions();options.intra_op_num_threads=4;options.inter_op_num_threads=1
    ort.disable_telemetry_events()
    def session(path):
        return ort.InferenceSession(str(path),options,providers=['CPUExecutionProvider'])
    prefix,suffix=session(base/'prefix.onnx'),session(base/'suffix.onnx')
    model=SymbolicShapeInference.infer_shapes(onnx.load(base/'region.onnx'),auto_merge=True)
    nodes=list(model.graph.node)
    conv=[n for n in nodes if n.op_type=='Conv']
    supported=['Conv','Constant','Div','Erf','Constant','Add','Mul','Constant','Mul','Conv','Mul','Add']
    if [n.op_type for n in nodes]!=supported:
        raise ValueError('requires exact two-conv GELU/layerscale/residual region')
    constants=[]
    for i in (1,4,7):
        attrs={a.name:onnx.helper.get_attribute_value(a) for a in nodes[i].attribute}
        constants.append(float(numpy_helper.to_array(attrs['value'])))
    if not np.allclose(constants,[np.sqrt(2),1,0.5],rtol=1e-7,atol=0):
        raise ValueError('unsupported GELU constants')
    links=[(2,0,0),(2,1,1),(3,0,2),(5,0,3),(5,1,4),
           (6,0,0),(6,1,5),(8,0,6),(8,1,7),(9,0,8)]
    if any(nodes[dest].input[port]!=nodes[src].output[0] for dest,port,src in links):
        raise ValueError('unsupported GELU data dependencies')
    for n in conv:
        a={v.name:onnx.helper.get_attribute_value(v) for v in n.attribute}
        if (a.get('group',1)!=1 or a.get('kernel_shape')!=[1,1] or
                a.get('strides',[1,1])!=[1,1] or any(a.get('pads',[0,0,0,0]))):
            raise ValueError('only pointwise region supported')
    initial={v.name:numpy_helper.to_array(v) for v in model.graph.initializer}
    region_output=model.graph.output[0].name
    first_input=conv[0].input[0]
    residual=next(x for x in nodes[-1].input if x != nodes[-2].output[0])
    layer_scale=next(initial[x] for x in nodes[-2].input if x in initial)
    if first_input==residual:
        raise ValueError('unexpected region signature')
    probes=[conv[0].output[0],conv[1].input[0],conv[1].output[0],region_output]
    info={v.name:v for v in list(model.graph.value_info)+list(model.graph.output)}
    del model.graph.output[:];model.graph.output.extend([info[x] for x in probes])
    fp=ort.InferenceSession(model.SerializeToString(),options,providers=['CPUExecutionProvider'])
    records=[]
    for path in args.input:
        x=np.fromfile(path,'<f4')
        if x.size!=196608 or not np.isfinite(x).all():raise ValueError('invalid image tensor')
        values=dict(zip([v.name for v in prefix.get_outputs()],prefix.run(None,{'image':x.reshape(1,3,256,256)})))
        z,g,y,region=fp.run(None,{v.name:values[v.name] for v in fp.get_inputs()})
        records.append((path,values,z,g,y,region))
    scale_a=float(symmetric_scale(np.array([np.max(np.abs(r[1][first_input])) for r in records])))
    scale_z=float(symmetric_scale(np.array([np.max(np.abs(r[2])) for r in records])))
    scale_g=float(symmetric_scale(np.array([np.max(np.abs(r[3])) for r in records])))
    scale_y=float(symmetric_scale(np.array([np.max(np.abs(r[4])) for r in records])))
    packed=[]
    for index,(node,sin,sout) in enumerate(zip(conv,[scale_a,scale_g],[scale_z,scale_y])):
        w=initial[node.input[1]][:,:,0,0].T.copy()
        sw=symmetric_scale(w,axis=0)
        b=initial[node.input[2]] if len(node.input)>2 else np.zeros(w.shape[1],np.float32)
        b64=np.rint(b.astype(np.float64)/(sin*sw))
        if np.any(b64<-(1<<31)) or np.any(b64>((1<<31)-1)):raise OverflowError('quantized bias')
        coeff=[multiplier_shift(float(r)) for r in sin*sw/sout]
        mult,shift=(np.array(v,dtype='<i4') for v in zip(*coeff))
        qw=quantize(w,sw);qb=b64.astype('<i4')
        stem='fc%d'%(index+1)
        qw.tofile(out/(stem+'-weights-kn.i8'));qb.tofile(out/(stem+'-bias.i32'))
        mult.tofile(out/(stem+'-multiplier.i32'));shift.tofile(out/(stem+'-shift.i32'))
        sw.astype('<f8').tofile(out/(stem+'-weight-scale.f64'))
        packed.append((qw,qb,mult,shift))
    lut=gelu_lut(scale_z,scale_g);lut.tofile(out/'gelu-u8-index.i8')
    def matrix(x):return x[0].transpose(1,2,0).reshape(-1,x.shape[1]).copy()
    def layer(qa,parameters):
        w,b,m,s=parameters
        accum=qa.astype(np.int64)@w.astype(np.int64)
        return requantize(accum,b,m,s)
    results=[]
    for idx,(path,values,z,g,y,expected) in enumerate(records):
        a=values[first_input];qa=quantize(matrix(a),scale_a)
        qz=layer(qa,packed[0]);qg=lut[qz.view(np.uint8)];qy=layer(qg,packed[1])
        actual_y=(qy.astype(np.float64)*scale_y).reshape(a.shape[2],a.shape[3],-1).transpose(2,0,1)[None].astype(np.float32)
        actual_region=(actual_y*layer_scale+values[residual]).astype(np.float32)
        feeds={region_output:actual_region}
        expected_feeds={region_output:expected}
        for item in suffix.get_inputs():
            if item.name!=region_output:
                feeds[item.name]=expected_feeds[item.name]=values[item.name]
        mixed=suffix.run(None,feeds)[0];golden=suffix.run(None,expected_feeds)[0]
        mixed.astype('<f4').tofile(out/('sample-%02d-features.f32'%idx))
        qa[:16].tofile(out/('sample-%02d-fc1-input.i8'%idx))
        qz[:16].tofile(out/('sample-%02d-fc1-output.i8'%idx))
        qg[:16].tofile(out/('sample-%02d-gelu-output.i8'%idx))
        qy[:16].tofile(out/('sample-%02d-fc2-output.i8'%idx))
        results.append({'input_sha256':sha(path),'region_error':error(actual_region,expected),
                        'feature_error':error(mixed,golden),
                        'fc1_saturated':int(np.count_nonzero(np.abs(qz.astype(np.int16))==127)),
                        'fc2_saturated':int(np.count_nonzero(np.abs(qy.astype(np.int16))==127))})
    report={'status':'INTEGER_FFN_ENGINEERING_SMOKE_ONLY',
            'partition_manifest_sha256':sha(base/'manifest.json'),
            'source_model_sha256':partition['source_sha256'],
            'calibration':'same smoke inputs; no held-out accuracy claim',
            'contract':'two INT8 Conv; checked INT32 bias+accum; Q31 ties-even requant; GELU byte-index LUT; FP32 layer-scale/residual',
            'scales':{'input':scale_a,'pre_gelu':scale_z,'post_gelu':scale_g,'fc2_output':scale_y},
            'weight_kn_shapes':[list(p[0].shape) for p in packed],
            'results':results,'files':{p.name:{'bytes':p.stat().st_size,'sha256':sha(p)} for p in out.iterdir() if p.is_file()}}
    (out/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(results,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
