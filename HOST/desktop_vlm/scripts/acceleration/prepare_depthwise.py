"""Extract actual same-size depthwise Conv integer fixtures for C/RTL tests."""
import argparse
import json
from pathlib import Path

import numpy as np
import onnx
from onnx import numpy_helper
import onnxruntime as ort
from onnxruntime.tools.symbolic_shape_infer import SymbolicShapeInference

from prepare_pointwise import quantize, sha, symmetric_scale


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--model',required=True)
    ap.add_argument('--expected-model-sha256',required=True)
    ap.add_argument('--node',required=True)
    ap.add_argument('--input',action='append',required=True)
    ap.add_argument('--channels',type=int,default=2)
    ap.add_argument('--output',required=True)
    args=ap.parse_args()
    if sha(args.model)!=args.expected_model_sha256:raise ValueError('model SHA mismatch')
    out=Path(args.output);out.mkdir(parents=True,exist_ok=False)
    model=SymbolicShapeInference.infer_shapes(onnx.load(args.model),auto_merge=True)
    selected=[n for n in model.graph.node if n.name==args.node and n.op_type=='Conv']
    if len(selected)!=1:raise ValueError('expected exact unique Conv')
    n=selected[0];attr={x.name:onnx.helper.get_attribute_value(x) for x in n.attribute}
    init={x.name:numpy_helper.to_array(x) for x in model.graph.initializer}
    w=init[n.input[1]];c=w.shape[0];k=w.shape[2];pad=k//2
    if (w.shape!=(c,1,k,k) or k not in (3,7) or attr.get('group')!=c or
            attr.get('strides',[1,1])!=[1,1] or attr.get('dilations',[1,1])!=[1,1] or
            attr.get('pads')!=[pad,pad,pad,pad] or not 1<=args.channels<=c):
        raise ValueError('supports channel-multiplier1 same-size DW3/7 only')
    info={v.name:v for v in list(model.graph.value_info)+list(model.graph.output)}
    del model.graph.output[:];model.graph.output.append(info[n.input[0]])
    options=ort.SessionOptions();options.intra_op_num_threads=4;options.inter_op_num_threads=1
    ort.disable_telemetry_events()
    session=ort.InferenceSession(model.SerializeToString(),options,providers=['CPUExecutionProvider'])
    records=[]
    for path in args.input:
        x=np.fromfile(path,'<f4')
        if x.size!=196608 or not np.isfinite(x).all():raise ValueError('invalid input')
        a=session.run(None,{'image':x.reshape(1,3,256,256)})[0][0]
        records.append((path,a))
    sx=float(symmetric_scale(np.array([np.max(np.abs(a)) for _,a in records])))
    sw=symmetric_scale(w[:,0],axis=(1,2))
    qw=quantize(w[:,0],sw[:,None,None])[:args.channels]
    qw.tofile(out/'weights-chw.i8');sw[:args.channels].astype('<f8').tofile(out/'weight-scales.f64')
    if len(n.input)==3:init[n.input[2]][:args.channels].astype('<f4').tofile(out/'bias-unused.f32')
    results=[]
    for idx,(path,a) in enumerate(records):
        qa=quantize(a[:args.channels],sx)
        padded=np.pad(qa,((0,0),(pad,pad),(pad,pad)),mode='constant')
        windows=np.lib.stride_tricks.sliding_window_view(padded,(k,k),axis=(1,2))
        accum=np.einsum('chyij,cij->chy',windows.astype(np.int64),qw.astype(np.int64),optimize=True)
        # Independent explicit bounds-checked zero-padding and scalar MAC.
        channels,height,width=qa.shape
        for ch in range(channels):
            for y in range(height):
                for x in range(width):
                    scalar=0
                    for ky in range(k):
                        for kx in range(k):
                            iy,ix=y+ky-pad,x+kx-pad
                            if 0<=iy<height and 0<=ix<width:
                                scalar+=int(qa[ch,iy,ix])*int(qw[ch,ky,kx])
                    if scalar!=int(accum[ch,y,x]):raise AssertionError('DW scalar golden mismatch')
        if np.any(accum<-(1<<31)) or np.any(accum>(1<<31)-1):raise OverflowError('accumulator')
        stem='sample-%02d'%idx
        qa.tofile(out/(stem+'-input-chw.i8'));accum.astype('<i4').tofile(out/(stem+'-output-chw.i32'))
        np.savetxt(out/(stem+'-input.txt'),qa.reshape(-1),fmt='%d')
        np.savetxt(out/(stem+'-output.txt'),accum.reshape(-1),fmt='%d')
        results.append({'input_sha256':sha(path),'original_activation_shape':list(a.shape),
                        'fixture_chw':[channels,height,width],'scalar_checks':int(accum.size)})
    np.savetxt(out/'weights.txt',qw.reshape(-1),fmt='%d')
    report={'status':'REAL_MODEL_INTEGER_FIXTURES_NOT_ACCURACY_VALIDATION','model_sha256':sha(args.model),
            'node':args.node,'contract':{'layout':'CHW row-major','kernel':k,'pad':pad,'stride':1,
                'weight_layout':'C,Kh,Kw','input_type':'signed int8','output_type':'signed little-endian int32',
                'zero_point':0,'activation_scale':sx,'weight_scales':'per channel',
                'bias':'NOT applied; FPGA must output raw sum only','padding':'integer zero',
                'rounding':'nearest ties-even','quant_range':[-127,127]},
            'results':results,'files':{p.name:{'bytes':p.stat().st_size,'sha256':sha(p)} for p in out.iterdir() if p.is_file()}}
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(results,indent=2))


if __name__=='__main__':main()
