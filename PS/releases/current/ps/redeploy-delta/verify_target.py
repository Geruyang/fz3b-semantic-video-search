from __future__ import print_function
import importlib.util, pathlib, json, datetime, hashlib, re, os
HERE=pathlib.Path(__file__).resolve().parent; REPO=HERE.parents[4]
SRC=REPO/'artifacts/board-debug-20261009/acceleration/network/network10-v10.5-a0005-board-exact-003/run_exact.py'
spec=importlib.util.spec_from_file_location('exact',str(SRC)); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
account=re.findall(r"默认账户\s+`([^`]+)`\s*/\s*`([^`]+)`",m.DOC.read_text(encoding='utf-8'))[0]
env=os.environ.copy(); env.update({'FZ3B_SSH_PASSWORD':account[1],'SSH_ASKPASS':str(m.ASKPASS),'SSH_ASKPASS_REQUIRE':'force','DISPLAY':'codex-a0005-delta-verify'})
target='%s@192.168.1.254'%account[0]; account=None; records=[]
cmd=r'''set -eu
base=/root/workspace/network10-v10.5-a0005-board-validation-001
test "$(sha256sum "$base/validation/contract/p3-params.bin"|cut -d' ' -f1)" = f6ece07c73678835a6d25dd13b5ecafa7f106f03d279eea7b2b51a1898cc09ce
for p in "$base/runtime/cnn_ddr_v10_p3_dma_runtime.py" "$base/validation/runtime/cnn_ddr_v10_p3_dma_runtime.py"; do test "$(sha256sum "$p"|cut -d' ' -f1)" = 2edced5bc1cb3d314a6c76cce118160798f32002b71f006b8798dd3c34773d97; done
for p in "$base/runtime/cnn_ddr_v10_signed40_candidate_runtime.py" "$base/validation/runtime/cnn_ddr_v10_signed40_candidate_runtime.py"; do test "$(sha256sum "$p"|cut -d' ' -f1)" = f77049e380ba522fe4c605774fe64bbbac5da60b2caa5e7736fd4bb204746d60; done
sha256sum "$base/validation/contract/p3-params.bin" "$base/runtime/cnn_ddr_v10_p3_dma_runtime.py" "$base/validation/runtime/cnn_ddr_v10_p3_dma_runtime.py" "$base/runtime/cnn_ddr_v10_signed40_candidate_runtime.py" "$base/validation/runtime/cnn_ddr_v10_signed40_candidate_runtime.py"
cat /root/workspace/factory-backups/network10-factory-20261009-a0005-retained/README.txt
cat /root/workspace/factory-backups/network10-factory-20261009-a0005-retained/SHA256SUMS
'''
r=m.run(env,target,records,'verify-redeploy-delta-and-factory-metadata',cmd,timeout=120)
manifest=HERE/'manifest.json'; msh=hashlib.sha256(manifest.read_bytes()).hexdigest()
report={'schema':'fz3b-v10.5-a0005-redeploy-delta-target-verify-v1','status':'PASS','pass':True,'manifest_sha256':msh,'remote_base':'/root/workspace/network10-v10.5-a0005-board-validation-001','all_five_paths_match':True,'factory_backup_metadata_captured':True,'commands':records,'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
data=(json.dumps(report,indent=2,sort_keys=True)+'\n').encode(); out=HERE/'target-verification.json'; out.write_bytes(data)
# Save exact remote small metadata locally without changing the frozen delta manifest.
stdout=r['stdout']; marker='Factory recovery assets copied'; begin=stdout.find(marker); sha_marker=stdout.find('59e1a617',begin)
(REPO/'artifacts/board-debug-20261009/acceleration/network/network10-v10.5-a0005-retain-redeploy-001/factory-backup-metadata.txt').write_text(stdout[begin:],encoding='utf-8')
print(out); print(hashlib.sha256(data).hexdigest()); print('manifest',msh)
