"""Concatenate the frozen W16 profile parameter files and calibration manifest."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
HOST=ROOT/"artifacts/board-debug-20261005/acceleration/host"
JOINT=HOST/"network-w16-joint-oracle-001"
N0=HOST/"network0-w16-preflight-001"
N2=HOST/"network2-int-oracle-board-ps-001"
N4=HOST/"network4-host-quant-contract-001"
N0REF=HOST/"root-stage0-preflight-001"
OUT=HOST/"network-w16-runtime-bundles-001"

def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for x in iter(lambda:f.read(1<<20),b''):h.update(x)
 return h.hexdigest()

def main():
 if OUT.exists():raise FileExistsError(str(OUT))
 jm=json.loads((JOINT/'manifest.json').read_text())
 n0m=json.loads((N0/'manifest.json').read_text())
 n2m=json.loads((N2/'manifest.json').read_text())
 n4m=json.loads((N4/'manifest.json').read_text())
 n0ref=json.loads((N0REF/'manifest.json').read_text())
 OUT.mkdir(parents=True)
 specs=[
  (0,128,32,12,262144,[JOINT/x['path'] for x in jm['profiles']['profile0']['params']],
   [sha(JOINT/x['path']) for x in jm['profiles']['profile0']['params']],
   [json.loads((N2/f'block-{i:02d}'/'manifest.json').read_text())['calibration_scales'] for i in range(12)],
   'network2-int-oracle-board-ps-001 per-block manifests; calibrated from BOARD_PS traces, oracle is host recomputation'),
  (1,256,16,20,131072,[JOINT/x['path'] for x in jm['profiles']['profile1']['params']],
   [sha(JOINT/x['path']) for x in jm['profiles']['profile1']['params']],
   [b['calibration_scales'] for b in n4m['blocks']],
   'network4-host-quant-contract-001; calibration from three HOST pure-PS traces, not board PS'),
  (2,64,64,4,524288,[N0/x['path'] for x in n0m['params']['blocks']],
   [sha(N0/x['path']) for x in n0m['params']['blocks']],
   [b['scales'] for b in n0ref['parameters']],
   'root-stage0-preflight-001; network0 calibration from three HOST pure-PS traces, not board PS')]
 profiles={}
 scale_profiles={}
 for p,c,w,bcount,slot,paths,hashes,scales,prov in specs:
  stride={64:195088,128:358928,256:976912}[c]
  parts=[]
  refs=[]
  for i,(path,expected_hash) in enumerate(zip(paths,hashes)):
   raw=path.read_bytes()
   if len(raw)!=stride or sha(path)!=expected_hash:raise ValueError(f'block {p}/{i} integrity/stride mismatch')
   parts.append(raw);refs.append({'index':i,'bytes':len(raw),'sha256':expected_hash,'source':str(path.relative_to(ROOT)).replace('\\','/')})
  blob=b''.join(parts)
  target=OUT/f'params-profile{p}.bin';target.write_bytes(blob)
  profiles[str(p)]={'profile':p,'network':{0:'network2',1:'network4',2:'network0'}[p],
    'channels':c,'width':w,'block_count':bcount,'block_stride_bytes':stride,
    'parameter_words_per_block':stride//16,'parameter_file':{'path':target.name,'bytes':len(blob),'sha256':sha(target)},
    'slot_bytes':slot,'activation':'little-endian signed INT16 HCW, two slots',
    'block_parameter_sources':refs,'scale_provenance':prov}
  scale_profiles[str(p)]={'profile':p,'per_block':[
    {'block_index':i,'scales':{k:float(v) for k,v in s.items()},'parameter_block_sha256':hashes[i]}
    for i,s in enumerate(scales)]}
 scales_path=OUT/'scale-manifest.json'
 scales_path.write_text(json.dumps({'schema_version':1,'abi':{'magic':'FZV5','version':0x00050000,'flags':0},
   'profiles':scale_profiles},indent=2,sort_keys=True)+'\n')
 manifest={'schema_version':1,'status':'HOST_FZV5_W16_RUNTIME_PARAM_BUNDLE_NOT_PL',
   'abi':{'magic':'FZV5','version':0x00050000,'flags':0},'profiles':profiles,
   'scale_manifest':{'path':scales_path.name,'sha256':sha(scales_path),'bytes':scales_path.stat().st_size},
   'source_manifests':{'w16_joint_sha256':sha(JOINT/'manifest.json'),'network0_w16_sha256':sha(N0/'manifest.json'),
     'network2_calibration_sha256':sha(N2/'manifest.json'),'network4_calibration_sha256':sha(N4/'manifest.json'),
     'network0_calibration_sha256':sha(N0REF/'manifest.json')},
   'checks':{'profiles':['0','1','2'],'single_constant_stride_per_profile':True,
     'parameter_files_have_no_headers':True,'board_or_pl_execution':False}}
 manifest['files']={p.relative_to(OUT).as_posix():{'bytes':p.stat().st_size,'sha256':sha(p)}
   for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='manifest.json'}
 mf=OUT/'manifest.json';mf.write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
 print(json.dumps({'manifest':str(mf),'manifest_sha256':sha(mf),
   'profiles':{k:{'params_path':v['parameter_file']['path'],'params_bytes':v['parameter_file']['bytes'],
      'params_sha256':v['parameter_file']['sha256'],'stride':v['block_stride_bytes'],
      'words_per_block':v['parameter_words_per_block'],'blocks':v['block_count'],'slot_bytes':v['slot_bytes']}
      for k,v in profiles.items()},'scale_manifest_sha256':sha(scales_path)},indent=2))

if __name__=='__main__':main()
