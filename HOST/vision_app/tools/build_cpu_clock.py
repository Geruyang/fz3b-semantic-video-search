"""On-board OOT CPU module build with matching prepared header subset."""
from vision_app.tools.board_link import ROOT,open_link,run

def main():
    remote='/root/fz3b-vision-console-20261009-001/cpu-clock-build'
    client=open_link()
    try:
        run(client,'mkdir -p '+remote)
        s=client.open_sftp()
        for name in ('fz3b_cpu_clock.c','fz3b_cpu_four.h','Makefile'):
            s.put(str(ROOT/'vision_app/cpu_clock'/name),remote+'/'+name)
        s.put(str(ROOT/'artifacts/ps-application-20261009/cpu-clock/prepared-headers.tar.gz'),remote+'/prepared-headers.tar.gz')
        s.close()
        result=run(client,'cd '+remote+'; tar --warning=no-timestamp -xzf prepared-headers.tar.gz; LC_ALL=C make -C prepared-headers M='+remote+' ARCH=arm64 modules >build.log 2>&1; rc=$?; tail -60 build.log; exit $rc',timeout=180)
        print(result)
        s=client.open_sftp()
        s.get(remote+'/build.log',str(ROOT/'artifacts/ps-application-20261009/cpu-clock/build.log'))
        s.close()
        s=client.open_sftp()
        s.get(remote+'/fz3b_cpu_clock.ko',str(ROOT/'artifacts/ps-application-20261009/cpu-clock/fz3b_cpu_clock.ko'))
        s.close()
        print(run(client,'modinfo '+remote+'/fz3b_cpu_clock.ko'))
    finally:client.close()

if __name__=='__main__':main()
