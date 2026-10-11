"""Frozen independent numeric stimuli and exact RTL request scoreboard.
Only --run publishes evidence; standalone invocation verifies an existing bound run.
"""
import re,json,hashlib,pathlib,subprocess,sys,datetime
ROOT=pathlib.Path(__file__).resolve().parents[1]; REPORT=ROOT/'reports/preflight'
# Numeric constants are independent of the DUT; HLS source has been removed.
CONSTANTS=ROOT/'tb/preflight_constants.json'; TOOLS=pathlib.Path('D:/Vivado/2026.1/Vivado/bin')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def generate():
 constants=json.loads(CONSTANTS.read_text(encoding='utf-8'))
 z=constants['gelu_zero'];t=constants['gelu_tail']
 stride=constants['stride'];bias=constants['bias_offset'];gelu=constants['gelu_offset']
 functions={'channels':[128,256,64,64], 'stride':stride+[11280], 'bias_offset':bias+[464], 'gelu_offset':gelu+[881], 'slot_words_for':[16384,8192,32768,32768]}
 inc=['// Generated independently from frozen C++ headers; never imports DUT package.']
 for name,values in functions.items():
  inc.append(f'function automatic integer {name}(input integer p); case(p) '+''.join(f'{i}:return {n};' for i,n in enumerate(values))+' default:return 0;endcase endfunction')
 for name,arr in [('gelu_zero',z),('gelu_tail',t)]:
  inc.append(f'function automatic integer {name}(input integer p,b);case(p)')
  for p,values in enumerate(arr):inc.append(f'{p}:case(b)'+''.join(f'{i}:return {n};' for i,n in enumerate(values))+' default:return 0;endcase')
  inc.append('default:return 0;endcase endfunction')
 # Exactly the TB job order; all metadata errors continue to scan and drain.
 jobs=[(0,12,False),(1,20,False),(2,4,False),(3,1,False)]
 jobs += [(1 if m==5 else 2 if m==6 else 0,1,False) for m in range(1,8)]
 jobs += [(2,1,False)]*2+[(3,1,False)]*4
 jobs += [(0,1,True)]*4+[(0,0,True),(1,21,True),(4,1,True),(0,1,False)]
 requests=[];starts=[];ends=[];beats=[]
 for p,blocks,reject in jobs:
  starts.append(len(requests));nb=0
  if not reject:
   for block in range(blocks):
    if p==3:regions=[(0,784,64),(0,880,32),(0,7056,64),(0,7152,32),(0,912,4096),(0,7184,4096)]
    else:
     c=functions['channels'][p];base=block*stride[p];q=bias[p]
     regions=[(client,base+offset,count) for client in [0,1] for offset,count in [(q,3*c),(q+3*c+6*c//4,6*c//4),(q+6*c+c//4,c//4),(q+6*c+c//2,1)]]+[(0,base+gelu[p],7032)]
    for client,addr,count in regions:
     nb+=count
     for off in range(0,count,32):requests.append((client<<38)|((addr+off)<<6)|min(32,count-off))
  ends.append(len(requests));beats.append(nb)
 for name,vals in [('gold_start',starts),('gold_end',ends),('gold_beats',beats)]:
  inc.append(f'function automatic integer {name}(input integer job);case(job)'+''.join(f'{i}:return {n};' for i,n in enumerate(vals))+'default:return -1;endcase endfunction')
 (ROOT/'tb/preflight_golden.svh').write_text('\n'.join(inc)+'\n')
 (REPORT/'golden_requests.mem').write_text('\n'.join(f'{n:010x}' for n in requests)+'\n')
 (REPORT/'golden_regions.json').write_text(json.dumps({'jobs':jobs,'command_count':len(requests),'job_starts':starts,'job_ends':ends,'job_word_counts':beats},indent=2))
 return len(requests)
def inputs():return [ROOT/'rtl/cnn_preflight.sv',ROOT/'rtl/cnn_profile_pkg.sv',ROOT/'tb/preflight_tb.sv',ROOT/'tb/preflight_golden.svh',ROOT/'scripts/preflight_reference.py',ROOT/'scripts/preflight_test.ps1',REPORT/'golden_requests.mem',REPORT/'golden_regions.json',CONSTANTS]
def manifest():return {str(p):sha(p) for p in inputs()}
def call(tool,args,log):
 cmd=[str(TOOLS/(tool+'.bat'))]+list(map(str,args))
 result=subprocess.run(cmd,cwd=REPORT,capture_output=True,text=True)
 (REPORT/log).write_text(result.stdout+result.stderr)
 if result.returncode:raise RuntimeError(f'{tool} failed; see {log}')
 return cmd
if '--run' not in sys.argv:
 receipt=json.loads((REPORT/'receipt.json').read_text())
 if receipt.get('input_sha256')!=manifest():raise SystemExit('REJECT stale or unbound source identity; invoke --run')
 for name,digest in receipt['artifact_sha256'].items():
  if sha(REPORT/name)!=digest:raise SystemExit('REJECT modified artifact '+name)
 print('PREFLIGHT BOUND EVIDENCE VERIFIED');sys.exit(0)
commands=[];n=generate();before=manifest();(REPORT/'run_inputs.json').write_text(json.dumps(before,indent=2))
commands.append(call('xvlog',['-sv','-i',ROOT/'tb',ROOT/'rtl/cnn_profile_pkg.sv',ROOT/'rtl/cnn_preflight.sv',ROOT/'tb/preflight_tb.sv'],'compile.log'))
commands.append(call('xelab',['tb_preflight','-s','preflight_sim'],'elaborate.log'))
commands.append(call('xsim',['preflight_sim','-runall'],'simulation.log'))
log=(REPORT/'simulation.log').read_text()
if 'PREFLIGHT PASS tests=25' not in log or 'Fatal:' in log:raise RuntimeError('RTL test failed')
if 'INDEPENDENT REQUEST COVERAGE PASS' not in log:raise RuntimeError('Missing independent coverage')
# Deliberate missing-first-metadata-region RTL mutant, never overwrite production.
source=(ROOT/'rtl/cnn_preflight.sv').read_text();needle='blocks<=block_count;block_no<=0;base<=0;region<=0;'
assert needle in source
mutant=REPORT/'preflight_missing_region_mutant.sv';mutant.write_text(source.replace(needle,needle.replace('region<=0','region<=1'),1))
commands.append(call('xvlog',['-sv','-i',ROOT/'tb',ROOT/'rtl/cnn_profile_pkg.sv',mutant,ROOT/'tb/preflight_tb.sv'],'mutation_compile.log'))
commands.append(call('xelab',['tb_preflight','-s','preflight_mutant'],'mutation_elaborate.log'))
commands.append(call('xsim',['preflight_mutant','-runall'],'mutation_simulation.log'))
mlog=(REPORT/'mutation_simulation.log').read_text()
if 'Fatal: REQUEST SCOREBOARD' not in mlog or 'PREFLIGHT PASS' in mlog:raise RuntimeError('Missing-region mutant escaped scoreboard')
if before!=manifest():raise RuntimeError('Inputs changed during run; no passing receipt published')
artifacts=['compile.log','elaborate.log','simulation.log','mutation_compile.log','mutation_elaborate.log','mutation_simulation.log','preflight_missing_region_mutant.sv','run_inputs.json']
receipt={'pass':True,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'xsim_tests':25,'independent_command_comparisons':n,'missing_region_mutant':'rejected at first command','input_sha256':before,'artifact_sha256':{name:sha(REPORT/name) for name in artifacts},'commands':commands,'tool':'Vivado XSim 2026.1 SW Build 6511674','limits':['Preflight standalone only; no full activation integration or synthesis qualification','Sequential clients, one outstanding burst; errors scan remaining validation regions before done']}
temp=REPORT/'receipt.json.tmp';temp.write_text(json.dumps(receipt,indent=2));temp.replace(REPORT/'receipt.json')
print(f'PREFLIGHT INDEPENDENT PASS commands={n}, missing-region mutant rejected; sources unchanged')

