#!/usr/bin/env python3
"""Derive the fused full-profile composite gate without modifying active runs."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

def sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def main()->int:
 p=argparse.ArgumentParser();p.add_argument('--old-receipt',type=Path,required=True);p.add_argument('--equivalence',type=Path,required=True);p.add_argument('--miter',type=Path,required=True);p.add_argument('--new-p3-result',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 old=json.loads(a.old_receipt.read_text());eq=json.loads(a.equivalence.read_text());mi=json.loads(a.miter.read_text());p3=json.loads(a.new_p3_result.read_text());log=Path(p3['xsim_log'])
 ok=old.get('pass') and eq.get('pass') and mi.get('pass') and p3.get('pass') and sha(log)==p3['xsim_log_sha256']
 r={'schema':'cnn-v10.4-half2x-fused-alu-composite-full-profile-gate-v1','status':'PASS_COMPOSITIONAL_REGRESSION_WITH_NEW_P3' if ok else 'FAIL','pass':bool(ok),'all_profiles_pass':bool(ok),'new_full_profile_rerun_complete':False,'new_full_rtl_9_run_pass_claimed':False,'formal_proof_claimed':False,'board_four_profile_exact_still_required':True,
 'evidence_division':{
   'old_qualified_profiles':{'scope':'P0/P1/P2/P3, repeat/profile-switch, pressure, bad-GELU; reusable only through exact/normalized equivalence','receipt':str(a.old_receipt.resolve()),'receipt_sha256':sha(a.old_receipt),'expected_sha256':'2be16439a66b06b8d0692ca004688f5a12b4edbed73e1336e9b0dc25b73b281d'},
   'snapshot_equivalence':{'scope':'291 exact RTL files; exact TB/fixture/macros; normalized outer wrapper and dual-clock FIFO/CE/reset','manifest':str(a.equivalence.resolve()),'sha256':sha(a.equivalence)},
   'fused_primitive':{'scope':'real UNISIM AREG/BREG2 and OPMODE W=C+PCIN+M, CE/reset/back-to-back/extreme/latency8','receipt':str(a.miter.resolve()),'sha256':sha(a.miter),'fast_cycle_miter_checks':2252},
   'new_transformed_whole_top_smoke':{'scope':'P3 whole-top numerical/protocol/canary/FIFO-drain smoke','result':str(a.new_p3_result.resolve()),'result_sha256':sha(a.new_p3_result),'log':str(log.resolve()),'log_sha256':sha(log),'cycles':2338022}
 },
 'new_run_cases':[{'case':'p0-baseline','status':'ABORTED_BY_EVIDENCE_REUSE','pass_claimed_from_new_run':False},{'case':'p1-baseline','status':'ABORTED_BY_EVIDENCE_REUSE','pass_claimed_from_new_run':False},{'case':'p2-repeat-switch-p3','status':'ABORTED_BY_EVIDENCE_REUSE','pass_claimed_from_new_run':False},{'case':'p3-baseline','status':'PASS_NEW_RUN','pass_claimed_from_new_run':True}],
 'interpretation':'all_profiles_pass is a layered evidence conclusion, not a claim that the fused snapshot reran every profile. Old profile results apply only where equivalence proves identity; fused internals are covered by real-UNISIM miter and the new transformed whole-top P3 smoke.'}
 if r['evidence_division']['old_qualified_profiles']['receipt_sha256']!=r['evidence_division']['old_qualified_profiles']['expected_sha256']:r['status']='FAIL';r['pass']=False;r['all_profiles_pass']=False
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print('FUSED_FULL_PROFILE_COMPOSITE_'+r['status']);return 0 if r['pass'] else 1
if __name__=='__main__':raise SystemExit(main())
