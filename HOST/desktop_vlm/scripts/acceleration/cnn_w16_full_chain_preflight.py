"""End-to-end HOST W16 chain: stem/N0 -> PS N1 -> N2 -> PS N3 -> N4 -> suffix."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort

import cnn_w16_contract as c16
import cnn_w16_joint_oracle as w16
import build_network2_int_oracle as n2

ROOT=w16.ROOT
HOST=w16.HOST
OLD=w16.OLD
MODEL_PATH=w16.MODEL
N0_REF=HOST/"root-stage0-preflight-001"
N0_W16=HOST/"network0-w16-preflight-001"
N2_TRACE_PATH=w16.N2_TRACE_PATH
N4_TRACE_PATH=w16.N4_TRACE_PATH
N4_CONTRACT_PATH=w16.N4_CONTRACT_PATH
SPLITS=w16.SPLITS
BUNDLE=HOST/"network-w16-runtime-bundles-001"
OUT=HOST/"network-w16-full-chain-preflight-001"


def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for chunk in iter(lambda:f.read(1<<20),b''):h.update(chunk)
 return h.hexdigest()

def save_array(root,rel,a,dtype):
 arr=np.ascontiguousarray(a,dtype=dtype);p=root/rel;p.parent.mkdir(parents=True,exist_ok=True);arr.tofile(p)
 return {'path':rel.replace('\\','/'),'dtype':dtype,'shape':list(arr.shape),'bytes':p.stat().st_size,'sha256':sha(p)}

def session(model):
 opts=ort.SessionOptions();opts.intra_op_num_threads=1;opts.inter_op_num_threads=1;opts.execution_mode=ort.ExecutionMode.ORT_SEQUENTIAL
 return ort.InferenceSession(model.SerializeToString(),opts,providers=['CPUExecutionProvider'])

def rank(feature,text_unit,ids):
 x=np.asarray(feature,dtype=np.float64).reshape(-1);x/=max(float(np.linalg.norm(x)),1e-300)
 scores=x@text_unit.T
 return [ids[int(i)] for i in np.argsort(-scores,kind='stable')]

def main():
 if OUT.exists():raise FileExistsError(str(OUT))
 model=onnx.load(str(MODEL_PATH))
 if sha(MODEL_PATH)!=w16.sha(MODEL_PATH):raise ValueError('model hash changed')
 n0m=json.loads((N0_REF/'manifest.json').read_text(encoding='utf-8'))
 n0blocks=n0m['blocks'];n0scales=[x['scales'] for x in n0m['parameters']]
 n0layers=[n2.extract_block_parameters(model,b) for b in n0blocks]
 n0params=[w16.make_params(l,s) for l,s in zip(n0layers,n0scales)]
 n2trace=json.loads(N2_TRACE_PATH.read_text(encoding='utf-8'));n2layers=[n2.extract_block_parameters(model,b) for b in n2trace['blocks']]
 n2m=json.loads(w16.N2_MANIFEST_PATH.read_text(encoding='utf-8'));n2scales=w16.read_boundary_scales(n2m)
 n2params=[w16.make_params(l,s) for l,s in zip(n2layers,n2scales)]
 n4trace=json.loads(N4_TRACE_PATH.read_text(encoding='utf-8'));n4contract=json.loads(N4_CONTRACT_PATH.read_text(encoding='utf-8'))
 n4layers=[n2.extract_block_parameters(model,b) for b in n4trace['blocks']]
 n4scales=[b['calibration_scales'] for b in n4contract['blocks']]
 n4params=[w16.make_params(l,s) for l,s in zip(n4layers,n4scales)]
 n0stem_tensor=n0blocks[0]['input'];n0_add=n0blocks[-1]['outputs']['add'];n2_in=n2trace['blocks'][0]['input']
 stem=session(onnx.utils.Extractor(model).extract_model(['image'],[n0stem_tensor]))
 n1=session(onnx.utils.Extractor(model).extract_model([n0_add],[n2_in]))
 n3=w16.ort_session(SPLITS/'network3-bridge.onnx')
 suffix=w16.ort_session(SPLITS/'suffix.onnx')
 bundle=json.loads((BUNDLE/'manifest.json').read_text(encoding='utf-8'))
 oldm=json.loads((OLD/'manifest.json').read_text(encoding='utf-8'))
 text=np.fromfile(OLD/'text-features.f32',dtype='<f4').reshape(8,512).astype(np.float64)
 text/=np.maximum(np.linalg.norm(text,axis=1,keepdims=True),1e-300)
 ids=[x['id'] for x in oldm['prompts']]
 OUT.mkdir(parents=True)
 results=[]
 for rec in n2m['results']:
  sid=rec['sample_id'];image_path=OLD/f'{sid}-input.f32'
  image=np.fromfile(image_path,dtype='<f4').reshape(1,3,256,256)
  stem_float=stem.run(None,{stem.get_inputs()[0].name:image})[0]
  q0=c16.quantize_symmetric_i16(stem_float,float(n0scales[0]['input']))[0]
  input0=q0.copy();out0=[]
  for i,p in enumerate(n0params):
   q0,st,ac=w16.execute_block(q0,p)
   out0.append({'index':i,'output':save_array(OUT,f'{sid}/profile2/block-{i:02d}-add-hcw.i16le',w16.to_hcw(q0),'<i2'),
                'accumulators':ac})
  n0deq=(q0[None].astype(np.float32)*np.float32(n0scales[-1]['add'])).astype('<f4')
  n1_float=n1.run(None,{n1.get_inputs()[0].name:n0deq})[0]
  n2q=c16.quantize_symmetric_i16(n1_float,float(n2scales[0]['input']))[0];input2=n2q.copy();out2=[]
  for i,p in enumerate(n2params):
   n2q,st,ac=w16.execute_block(n2q,p)
   out2.append({'index':i,'output':save_array(OUT,f'{sid}/profile0/block-{i:02d}-add-hcw.i16le',w16.to_hcw(n2q),'<i2'),
                'accumulators':ac})
  n2deq=(n2q[None].astype(np.float32)*np.float32(n2scales[-1]['add'])).astype('<f4')
  n3_float=n3.run(None,{n3.get_inputs()[0].name:n2deq})[0]
  n4q=c16.quantize_symmetric_i16(n3_float,float(n4scales[0]['input']))[0];input4=n4q.copy();out4=[]
  for i,p in enumerate(n4params):
   n4q,st,ac=w16.execute_block(n4q,p)
   out4.append({'index':i,'output':save_array(OUT,f'{sid}/profile1/block-{i:02d}-add-hcw.i16le',w16.to_hcw(n4q),'<i2'),
                'accumulators':ac})
  n4deq=(n4q[None].astype(np.float32)*np.float32(n4scales[-1]['add'])).astype('<f4')
  feature=suffix.run(None,{suffix.get_inputs()[0].name:n4deq})[0].reshape(512).astype('<f4')
  pure=np.fromfile(OLD/f'{sid}-ort.f32',dtype='<f4').reshape(512)
  diff=feature.astype(np.float64)-pure.astype(np.float64)
  results.append({'sample_id':sid,'input_sha256':sha(image_path),
    'stem_n0_input_float_sha256':hashlib.sha256(np.ascontiguousarray(stem_float,dtype='<f4').tobytes()).hexdigest(),
    'profile2_n0_input_i16_hcw':save_array(OUT,f'{sid}/profile2/input-hcw.i16le',w16.to_hcw(input0),'<i2'),
    'profile2_blocks':out0,'network1_output_sha256':hashlib.sha256(np.ascontiguousarray(n1_float,dtype='<f4').tobytes()).hexdigest(),
    'profile0_n2_input_i16_hcw':save_array(OUT,f'{sid}/profile0/input-hcw.i16le',w16.to_hcw(input2),'<i2'),
    'profile0_blocks':out2,'network3_output_sha256':hashlib.sha256(np.ascontiguousarray(n3_float,dtype='<f4').tobytes()).hexdigest(),
    'profile1_n4_input_i16_hcw':save_array(OUT,f'{sid}/profile1/input-hcw.i16le',w16.to_hcw(input4),'<i2'),
    'profile1_blocks':out4,'feature':save_array(OUT,f'{sid}/w16-full-chain-feature.f32',feature,'<f4'),
    'pure_ps_feature_sha256':sha(OLD/f'{sid}-ort.f32'),
    'metrics_vs_pure_ps':{'cosine':float(np.dot(feature,pure)/max(float(np.linalg.norm(feature)*np.linalg.norm(pure)),1e-300)),
      'max_abs':float(np.max(np.abs(diff))),'relative_l2':float(np.linalg.norm(diff)/max(float(np.linalg.norm(pure)),1e-300)),
      'rms_abs':float(np.sqrt(np.mean(diff*diff)))},
    'ranking':rank(feature,text,ids),'pure_ps_ranking':rank(pure,text,ids),
    'full_ranking_matches_pure_ps':rank(feature,text,ids)==rank(pure,text,ids)})
  print(sid,results[-1]['metrics_vs_pure_ps'],results[-1]['full_ranking_matches_pure_ps'],flush=True)
  del input0,input2,input4,stem_float,n1_float,n3_float,n0deq,n2deq,n4deq
 profiles={str(k):{'parameter_file_sha256':bundle['profiles'][str(k)]['parameter_file']['sha256'],
   'block_count':bundle['profiles'][str(k)]['block_count'],'stride_bytes':bundle['profiles'][str(k)]['block_stride_bytes']}
   for k in (0,1,2)}
 report={'schema_version':1,'status':'HOST_REAL_FP32_SOURCE_W16_ALL_STAGES_JOINT_QUALITY_PREFLIGHT_NOT_PL',
  'chain':['real FP32 stem to network0 input','network0 profile2 W16 4 blocks','real FP32 network1 bridge',
   'network2 profile0 W16 12 blocks','real FP32 network3 full SE bridge','network4 profile1 W16 20 blocks','real FP32 suffix to 512 features'],
  'source_hashes':{'model':sha(MODEL_PATH),'runtime_split_manifest':sha(SPLITS/'manifest.json'),
    'network0_reference_manifest':sha(N0_REF/'manifest.json'),'network0_w16_manifest':sha(N0_W16/'manifest.json'),
    'network2_oracle_manifest':sha(w16.N2_MANIFEST_PATH),'network2_trace_manifest':sha(N2_TRACE_PATH),
    'network4_trace_manifest':sha(N4_TRACE_PATH),'network4_contract_manifest':sha(N4_CONTRACT_PATH),
    'canonical_bundle_manifest':sha(BUNDLE/'manifest.json'),'scale_manifest':sha(BUNDLE/'scale-manifest.json'),
    'pure_ps_inputs_manifest':sha(OLD/'manifest.json')},
  'profiles':profiles,'calibration':{'profile2':'same three HOST pure-PS N0 traces; not BOARD_PS',
    'profile0':'frozen BOARD_PS-calibrated N2 per-block scale manifests, executed in HOST oracle',
    'profile1':'three HOST pure-PS N4 boundary traces; not BOARD_PS'},
  'arithmetic':'FZV5; symmetric INT16 activation/weight; i64 serialized bias checked signed48; signed48 accum; exact Python-wide signed Q31 product; i32 multiplier, shift0..62; ties-even; one saturate per operator and one at residual Add',
  'execution':{'host_only':True,'board_capture':False,'pl_execution':False,'onnx':onnx.__version__,'onnxruntime':ort.__version__},
  'results':results,'quality_interpretation':'Compare the full three-profile W16 chain to same-host pure FP32 PS; three engineering regression inputs only, no independent accuracy claim.',
  'checks':{'three_images':len(results)==3,'all_full_rankings_match':all(x['full_ranking_matches_pure_ps'] for x in results),
    'all_three_profiles_executed':True,'board_or_pl_execution':False}}
 report['files']={p.relative_to(OUT).as_posix():{'bytes':p.stat().st_size,'sha256':sha(p)}
   for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='manifest.json'}
 mf=OUT/'manifest.json';mf.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf-8')
 print(json.dumps({'manifest':str(mf),'manifest_sha256':sha(mf),'samples':[{'id':x['sample_id'],**x['metrics_vs_pure_ps'],'ranking':x['full_ranking_matches_pure_ps']} for x in results]},indent=2))

if __name__=='__main__':main()
