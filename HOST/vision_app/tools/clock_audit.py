"""Compile and run the preserved, fixed-address READ-ONLY clock audit."""
import datetime
import json
from vision_app.tools.board_link import ROOT, open_link, run
from vision_app.tools.fine_clock_probe import reader_source

def main():
    client = open_link()
    root = '/root/fz3b-vision-console-20261009-001'
    try:
        sftp = client.open_sftp()
        # Audit helper is separate from the CPU lease's pinned raw reader.
        # Rebuilding an audit must not change its close-time proof format.
        source=reader_source()
        with sftp.file(root+'/audit_read_clock.c','w') as handle:handle.write(source)
        sftp.close()
        raw = run(client,'gcc -O2 -Wall -Wextra -Werror '+root+'/audit_read_clock.c -o '+root+'/audit_read_clock; '+root+'/audit_read_clock')
        clocks = run(client,"grep -E '(^|[[:space:]])(acpu|acpu_mux|apll|apll_half|dpll|dpll_half|ddr_ref|pl1_ref)(_|[[:space:]])' /sys/kernel/debug/clk/clk_summary")
        cpu = run(client,'cat /sys/devices/system/cpu/cpufreq/policy0/scaling_cur_freq')
        report = {'raw':raw,'clocks':clocks,'cpu_sysfs_khz':int(cpu),'read_only_registers':True}
        path = ROOT/'artifacts/ps-application-20261009'/('clock-audit-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.json')
        path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(report,indent=2))
    finally:
        client.close()

if __name__ == '__main__':
    main()
