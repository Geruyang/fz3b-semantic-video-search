#!/usr/bin/env python3
"""Audit the fused full-RTL simulation snapshot against qualified half2x-004."""
from __future__ import annotations

import argparse, hashlib, json, re
from pathlib import Path

def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

def modules(p: Path) -> dict[str, str]:
    s = p.read_text(encoding="utf-8")
    out = {}
    for m in re.finditer(r"(?m)^module\s+(\w+)\b", s):
        e = re.search(r"(?m)^endmodule\s*$", s[m.start():])
        if not e: raise ValueError(f"unterminated module {m.group(1)}")
        out[m.group(1)] = s[m.start():m.start()+e.end()]
    return out

def norm(s: str) -> str:
    maps = {
        "cnn_v10_pw_dsp16_half2x_fused_alu": "cnn_v10_pw_dsp16_half2x",
        "cnn_v10_pw_dsp8_fast_fused_alu": "cnn_v10_pw_dsp8_fast",
        "fused_half2x": "half2x",
    }
    for a,b in maps.items(): s = re.sub(rf"\b{a}\b", b, s)
    s = re.sub(r"//.*?$|/\*.*?\*/", "", s, flags=re.M|re.S)
    return re.sub(r"\s+", "", s)

def inventory(d: Path) -> dict[str, str]:
    return {p.name: sha(p) for p in sorted(d.iterdir()) if p.is_file()}

def main() -> int:
    ap=argparse.ArgumentParser(); ap.add_argument('--old',type=Path,required=True); ap.add_argument('--new',type=Path,required=True); ap.add_argument('--miter',type=Path,required=True); ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args(); old=inventory(a.old/'rtl-snapshot'); new=inventory(a.new/'rtl-snapshot')
    common=sorted(set(old)&set(new)); exact=[n for n in common if old[n]==new[n]]; changed=[n for n in common if old[n]!=new[n]]
    ot,nt=inventory(a.old/'tb-snapshot'),inventory(a.new/'tb-snapshot')
    om=modules(a.old/'rtl-snapshot/cnn_v10_pw_dsp16.v'); nm=modules(a.new/'rtl-snapshot/cnn_v10_pw_dsp16.v')
    normalized={}
    for x,y in [('outer_wrapper','cnn_v10_pw_dsp16'),('dual_clock_fifo_ce_reset','cnn_v10_pw_dsp16_half2x')]:
        yn = y if y in nm else y+'_fused_alu'
        normalized[x]={'old_module':y,'new_module':yn,'equal':norm(om[y])==norm(nm[yn]),'old_sha256':hashlib.sha256(norm(om[y]).encode()).hexdigest(),'new_sha256':hashlib.sha256(norm(nm[yn]).encode()).hexdigest()}
    source_lists={}
    for label,d in [('old',a.old),('new',a.new)]:
        lines=[Path(x.strip()).name for x in (d/'source-files.f').read_text().splitlines() if x.strip()]
        source_lists[label]=lines
    old_receipt=json.loads((a.old/'receipt.json').read_text())
    miter=json.loads(a.miter.read_text())
    old_fast=om['cnn_v10_pw_dsp8_fast']; new_fast=nm['cnn_v10_pw_dsp8_fast_fused_alu']
    behavior={
      'interface_widths_equal': all(x in old_fast and x in new_fast for x in ['[47:0]      prior','[15:0]      value0','[15:0]      weight0','[47:0]      partial']),
      'latency_fast_enabled_edges':7,
      'old_valid_pipe_7': 'reg  [6:0] valid_pipe' in old_fast and 'partial_valid = valid_pipe[6]' in old_fast,
      'new_valid_pipe_7': 'reg [6:0] valid_pipe' in new_fast and 'partial_valid = valid_pipe[6]' in new_fast,
      'reset_precedes_ce_both': all(re.search(r'if\s*\(fast_rst\).*?else if\s*\(fast_ce\)',s,re.S) for s in [old_fast,new_fast]),
      'ce_holds_state_both': all('else if (fast_ce)' in s for s in [old_fast,new_fast]),
      'signed_products_and_mod48': all('$signed(value' in s and '[47:0]' in s for s in [om['cnn_v10_pw_dsp_muladd']+old_fast,new_fast]),
      'prior_included_once': 'START_WITH_PRIOR(1)' in old_fast and '$signed(prior) + sx0' in new_fast,
      'outer_accept_return_timing_exact': normalized['dual_clock_fifo_ce_reset']['equal'],
      'unisim_miter_receipt_sha256':sha(a.miter),'unisim_miter_pass':bool(miter.get('pass')),
      'boundary':'The old actor is a staged chain model while the fused actor is a seven-edge vector model, so actor expressions are not token-identical. Equivalence is limited to signed 16x16 terms accumulated modulo 2^48 with prior once, seven enabled-fast-edge valid/phase timing, reset priority, and CE hold. AREG/BREG2 and W=C+PCIN+M cycle fidelity is proven only by the real-UNISIM miter.'
    }
    result={
      'schema':'cnn-v10-pw-half2x-fused-alu-full-rtl-equivalence-audit-v1','status':'PASS','pass':True,
      'old_evidence':str(a.old.resolve()),'new_active_evidence_read_only':str(a.new.resolve()),
      'rtl_inventory':{'old_count':len(old),'new_count':len(new),'exact_count':len(exact),'changed':changed,'only_old':sorted(set(old)-set(new)),'only_new':sorted(set(new)-set(old))},
      'normalized_module_checks':normalized,
      'tb_snapshot':{'count':len(ot),'all_exact':ot==nt,'files':[{'path':n,'sha256':ot[n]} for n in sorted(ot)]},
      'fixture_and_macros':{'product_source_manifest_exact':sha(a.old/'product-source-manifest.json')==sha(a.new/'product-source-manifest.json'),'source_file_basename_sequence_equal':source_lists['old']==source_lists['new'],'old_source_file_count':len(source_lists['old']),'new_source_file_count':len(source_lists['new'])},
      'fast_behavior_model_comparison':behavior,
      'old_profile_evidence':{'receipt_sha256':sha(a.old/'receipt.json'),'status':old_receipt.get('status'),'case_count':len(old_receipt.get('cases',[]))},
      'strict_conclusion':{
        'shared_outer_tb_fixture_evidence_reusable': len(exact)==291 and changed==['cnn_v10_pw_dsp16.v'] and ot==nt and normalized['outer_wrapper']['equal'] and normalized['dual_clock_fifo_ce_reset']['equal'],
        'old_full_profile_result_is_fused_proof':False,
        'reason':'The qualified -004 run used the former fast-actor model and cannot bind fused AREG/BREG2, W=C+PCIN+M, or the new packaging identity. It is reusable only for byte-identical generated RTL, TB/fixture, macros, and normalized outer bridge/FIFO/CE/reset behavior. Fused primitive behavior is separately bound by UNISIM miter receipt d98b0ed1; the active fused full-profile run must provide the transformed-component result.'
      }
    }
    required=[len(old)==292,len(new)==292,len(exact)==291,changed==['cnn_v10_pw_dsp16.v'],ot==nt,normalized['outer_wrapper']['equal'],normalized['dual_clock_fifo_ce_reset']['equal'],result['fixture_and_macros']['product_source_manifest_exact'],all(v for k,v in behavior.items() if k not in {'boundary','unisim_miter_receipt_sha256','latency_fast_enabled_edges'})]
    if not all(required): result['status']='FAIL'; result['pass']=False
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(f"FUSED_FULL_RTL_EQUIVALENCE_AUDIT_{result['status']} exact={len(exact)} changed={changed}")
    return 0 if result['pass'] else 1
if __name__=='__main__': raise SystemExit(main())
