set -eu
P=/root/rtl_optim-board-20261010
V=/root/workspace/network10-v10.5-a0005-board-validation-001
python3 -B /root/workspace/network10-v10.5-pl-loader/fz3b_pl_loader.py prepare-a0005 > "$P/rtl-profiles-loader-before.json"
python3 -B "$P/compare_board.py" --payload-root "$V/validation" --runtime-root "$V/runtime" --contract-root "$P/contract" --execute --label rtl --artifact-sha256 23056627045da5fb4e9453a8d3369b17baf67d1a33671dfad8622bee7a67f1cd --job-clock-hz 200000000 --repeat 5 --warmup 1 --output "$P/rtl-profiles.json"
python3 - <<'PY'
import json
p='/root/rtl_optim-board-20261010/'
s=json.load(open(p+'rtl-profiles.json'))
print('RTL_PROFILES_PASS',[(r['profile'],r['median_job_cycles'],r['median_submit_wait_ns']/1e6) for r in s['rows']])
PY
