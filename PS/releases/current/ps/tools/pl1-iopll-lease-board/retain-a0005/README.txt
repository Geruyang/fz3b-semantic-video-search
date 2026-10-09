A0005 retained PL1/IOPLL lease owner.
The original lease_jtag_hold.py process is intentionally SIGSTOPed to remove its 7200-second userspace deadline while keeping the already-open lease FD and kernel IOPLL reference alive.
Do not kill, reboot, rmmod fz3b_pl1_iopll_lease, or release PL1 while A0005 is running.
To perform a future controlled restore only after a verified old-bit/PL1-raw restore receipt:
  cd /root/workspace/network10-v10.4-pl1-iopll-lease-candidate-001
  printf 'FINALIZE\n' > a0005.command
  kill -CONT $(cat a0005.pid)
  wait/poll for a0005.result.json PASS_FINALIZED, then verify refcounts/raw before unloading.
