set -eu
cat /proc/sys/kernel/random/boot_id
P=/root/rtl_optim-board-20261010/candidate008
D="$P/deployment"
L=/root/workspace/network10-v10.5-pl-loader/fz3b_pl_loader.py
U=/etc/systemd/system/fz3b-pl-loader.service.d/rtl-optim-retained.conf
T=/run/systemd/system/fz3b-pl-loader.service.d/rtl-optim-retain-transition.conf
test ! -e "$U"
test ! -e "$T"
test ! -e /run/systemd/system/fz3b-pl-loader.service.d/rtl-optim-test.conf
mkdir -p "$D"
systemctl cat fz3b-pl-loader.service > "$D/original-loader-unit.txt"
python3 -B - <<'PY'
import hashlib,json
from pathlib import Path
p=Path('/root/rtl_optim-board-20261010/candidate008')
assert (p/'original-loader-config.json').read_bytes()==Path('/root/workspace/network10-v10.5-pl-loader/config.json').read_bytes()
cfg=json.loads((p/'rtl-loader-config.json').read_text())
assert hashlib.sha256((p/'rtl-loader-config.json').read_bytes()).hexdigest()=='10d5878bcc40278f47995453662099fdc5814ed42fbd68973c1161a5664c81c8'
for key,expected in [('a0005_source_bit','78038efd603cde7763a1b3ff4581b799cabd1a11395db2d78af33b7c81d46726'),('a0005_native_bin','bf788681c0e990c337b07ee949bec735dd81224bcabc4d5948d03221e217d439'),('a0005_firmware','76dff052e3648a4634585bbed186cfa202b434c66c996a3d2b3349fa3b908c02')]:
    entry=cfg['assets'][key];raw=Path(entry['path']).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==entry['sha256']==expected and len(raw)==entry['bytes']
print('RETAINED_RTL_ASSETS_AND_ORIGINAL_HLS_BACKUP_VERIFIED')
PY
systemctl stop fz3b-vision-console.service
test "$(systemctl is-active fz3b-vision-console.service || true)" = inactive
if fuser /dev/network10_v10_signed40; then exit 1; fi
systemctl stop fz3b-app-cpu-clock.service
test "$(systemctl show fz3b-app-cpu-clock.service -p Result --value)" = success
test "$(systemctl is-active fz3b-app-cpu-clock.service || true)" = inactive
systemctl stop fz3b-app-r5.service
python3 -B "$L" switch-factory > "$D/hls-to-factory.json"
python3 -B - <<'PY'
import json
s=json.load(open('/root/rtl_optim-board-20261010/candidate008/deployment/hls-to-factory.json'))
assert s['ok'] and s['result']['ready'] and s['result']['status']=='READY_FACTORY'
assert s['result']['observed']['manager_state']=='operating'
assert s['result']['observed']['raw_clocks']['pl1_ref_ctrl']==0x52000
assert 'lease' not in s['result']['observed']
print('RETAIN_FACTORY_FENCE_LEASE_RELEASE_CONFIRMED')
PY
mkdir -p /etc/systemd/system/fz3b-pl-loader.service.d /run/systemd/system/fz3b-pl-loader.service.d
cat > "$U" <<'UNIT'
[Service]
ExecStart=
ExecStart=/usr/bin/python3 -B /root/workspace/network10-v10.5-pl-loader/fz3b_pl_loader.py daemon --config /root/rtl_optim-board-20261010/candidate008/rtl-loader-config.json --auto-target a0005 --log /root/rtl_optim-board-20261010/candidate008/deployment/loader-events.jsonl
UNIT
cat > "$T" <<'UNIT'
[Unit]
RefuseManualStop=no
UNIT
systemctl daemon-reload
systemctl restart fz3b-pl-loader.service
ready=0
for n in $(seq 1 40); do
  if python3 -B "$L" status > "$D/rtl-loader-ready.json"; then
    if python3 -B - <<'PY'
import json
s=json.load(open('/root/rtl_optim-board-20261010/candidate008/deployment/rtl-loader-ready.json'))
assert s['ok'] and s['result']['ready'] and s['result']['status']=='READY_A0005'
assert s['result']['identity']['pass'] and s['result']['observed']['manager_state']=='operating'
assert s['result']['observed']['lease']['last_error']==0
assert s['result']['observed']['raw_clocks']['pl1_ref_ctrl']==0x01010f00
PY
    then ready=1; break; fi
  fi
  sleep 1
done
test "$ready" = 1
rm -- "$T"
systemctl daemon-reload
test "$(systemctl show fz3b-pl-loader.service -p RefuseManualStop --value)" = yes
systemctl is-enabled fz3b-pl-loader.service > "$D/loader-enabled.txt"
systemctl show fz3b-pl-loader.service -p ExecStart --value | grep -F -- '--config /root/rtl_optim-board-20261010/candidate008/rtl-loader-config.json'
systemctl start fz3b-app-r5.service fz3b-app-cpu-clock.service
cd /root/fz3b-vision-console-20261009-001
python3 -B - <<'PY' > "$D/rtl-cpu-ready.json"
import json
from vision_app.cpu_clock_service import request
s=request('set',1200000)
assert s['verified'] and s['held'] and s['requested_khz']==1200000 and abs(s['actual_hz']-1200000000)<100
print(json.dumps(s))
PY
systemctl start fz3b-vision-console.service
for unit in fz3b-pl-loader fz3b-app-r5 fz3b-app-cpu-clock fz3b-vision-console; do systemctl is-active "$unit.service"; done
cp -- "$U" "$D/rtl-optim-retained.conf"
sha256sum "$U" /root/workspace/network10-v10.5-pl-loader/config.json
python3 -B "$P/capture_state.py" --root "$D" --variant rtl --phase before
echo RETAINED_RTL_PERSISTENT_SERVICE_AND_FOUR_SERVICES_READY
cat /proc/sys/kernel/random/boot_id
