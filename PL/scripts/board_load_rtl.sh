set -eu
P=/root/rtl_optim-board-20261010
L=/root/workspace/network10-v10.5-pl-loader/fz3b_pl_loader.py
test "$(systemctl is-active fz3b-vision-console.service || true)" = inactive
test ! -e /run/systemd/system/fz3b-pl-loader.service.d/rtl-optim-test.conf
if fuser /dev/network10_v10_signed40; then exit 1; fi
python3 - <<'PY'
import hashlib,json,os
from pathlib import Path
p=Path('/root/rtl_optim-board-20261010')
cfg=json.loads((p/'original-loader-config.json').read_text())
assert hashlib.sha256((p/'original-loader-config.json').read_bytes()).hexdigest()==hashlib.sha256(Path('/root/workspace/network10-v10.5-pl-loader/config.json').read_bytes()).hexdigest()
entries={
 'a0005_firmware':('cnn_rtl.pcap.bin','f227c6f30378942571ade7f239e801e31885609a760c1d6baccd2534ac56c044'),
 'a0005_native_bin':('cnn_rtl.native.bin','b6cee944dc4201ad1d537fcbb4ddac3fe398555c91d381e339fea700abfbbd51'),
 'a0005_source_bit':('cnn_rtl.bit','23056627045da5fb4e9453a8d3369b17baf67d1a33671dfad8622bee7a67f1cd')}
for key,(name,digest) in entries.items():
 raw=(p/name).read_bytes()
 assert hashlib.sha256(raw).hexdigest()==digest
 cfg['assets'][key].update(path=str(p/name),sha256=digest,bytes=len(raw))
cfg['assets']['a0005_firmware'].update(path='/lib/firmware/rtl-optim-20261010/cnn_rtl.pcap.bin',firmware_name='rtl-optim-20261010/cnn_rtl.pcap.bin')
(p/'rtl-loader-config.json').write_text(json.dumps(cfg,indent=2)+'\n')
os.chmod(str(p/'rtl-loader-config.json'),0o600)
print('RTL_CONFIG_ASSETS_SHA_VERIFIED')
PY
install -D -m 0600 "$P/cnn_rtl.pcap.bin" /lib/firmware/rtl-optim-20261010/cnn_rtl.pcap.bin
# CPU lease protects PL1 too. Close it before the factory transition changes PL1.
systemctl stop fz3b-app-cpu-clock.service
test "$(systemctl show fz3b-app-cpu-clock.service -p Result --value)" = success
test "$(systemctl is-active fz3b-app-cpu-clock.service || true)" = inactive
systemctl stop fz3b-app-r5.service
python3 -B "$L" switch-factory > "$P/hls-to-factory.json"
python3 - <<'PY'
import json
s=json.load(open('/root/rtl_optim-board-20261010/hls-to-factory.json'))
assert s['ok'] and s['result']['ready'] and s['result']['status']=='READY_FACTORY'
assert s['result']['observed']['detected_target']=='factory'
assert s['result']['observed']['manager_state']=='operating'
assert s['result']['observed']['raw_clocks']['pl1_ref_ctrl']==0x00052000
assert 'lease' not in s['result']['observed']
print('FACTORY_FENCE_LEASE_RELEASE_CONFIRMED')
PY
mkdir -p /run/systemd/system/fz3b-pl-loader.service.d
cat > /run/systemd/system/fz3b-pl-loader.service.d/rtl-optim-test.conf <<'UNIT'
[Unit]
RefuseManualStop=no
[Service]
ExecStart=
ExecStart=/usr/bin/python3 -B /root/workspace/network10-v10.5-pl-loader/fz3b_pl_loader.py daemon --config /root/rtl_optim-board-20261010/rtl-loader-config.json --auto-target a0005
UNIT
systemctl daemon-reload
systemctl show fz3b-pl-loader.service -p ExecStart --value | grep -F -- "--config $P/rtl-loader-config.json"
systemctl restart fz3b-pl-loader.service
rtl_ready=0
for n in $(seq 1 40); do
  if python3 -B "$L" status > "$P/rtl-loader-ready.json" 2> "$P/rtl-loader-poll.err"; then
    if python3 - <<'PY'
import json,sys
s=json.load(open('/root/rtl_optim-board-20261010/rtl-loader-ready.json'))
if not (s.get('ok') and s['result']['ready'] and s['result']['status']=='READY_A0005'):
 sys.exit(1)
assert s['result']['observed']['manager_state']=='operating'
assert s['result']['observed']['lease']['last_error']==0
assert s['result']['observed']['raw_clocks']['pl1_ref_ctrl']==0x01010f00
PY
    then rtl_ready=1; break; fi
  fi
  sleep 1
done
if [ "$rtl_ready" != 1 ]; then
  echo 'RTL loader failed strict readiness; no test will start.' >&2
  cat "$P/rtl-loader-ready.json" >&2
  exit 1
fi
python3 - <<'PY'
import json
p='/root/rtl_optim-board-20261010/'
s=json.load(open(p+'rtl-loader-ready.json'))
before=json.load(open(p+'hls-loader-ready.json'))
assert s['ok'] and s['result']['ready'] and s['result']['status']=='READY_A0005'
assert s['result']['observed']['manager_state']=='operating'
assert s['result']['observed']['lease']['last_error']==0
assert s['result']['observed']['raw_clocks']==before['result']['observed']['raw_clocks']
assert s['result']['identity']['pass']
assert s['result']['identity']['combined_manifest_sha256']=='4a32c9373e783ac572a5d3374b316181a4d52ae9a92ec45f8b13d763ef028690'
assert s['result']['identity']['identity']['core_id']==0x465a5641
assert s['result']['identity']['identity']['core_abi']==0x000a0005
print('RTL_PROGRAMMED_IDENTITY_READY')
PY
systemctl start fz3b-app-r5.service fz3b-app-cpu-clock.service
cd /root/fz3b-vision-console-20261009-001
python3 -B - <<'PY' > "$P/rtl-cpu-before.json"
import json
from vision_app.cpu_clock_service import request
s=request('set',1200000)
assert s['verified'] and s['requested_khz']==1200000 and abs(s['actual_hz']-1200000000)<100
print(json.dumps(s))
PY
cat "$P/rtl-cpu-before.json"
sha256sum "$P/rtl-loader-config.json" /lib/firmware/rtl-optim-20261010/cnn_rtl.pcap.bin
systemctl show fz3b-pl-loader.service -p MainPID -p ExecStart -p ActiveState
echo RTL_READY_CPU1200_PL200_400
