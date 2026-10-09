"""Select the matching prepared headers/scripts, not a board kernel rebuild."""
import copy
from pathlib import Path
import tarfile
from vision_app.tools.board_link import ROOT

def main():
    folder = ROOT/'artifacts/ps-application-20261009/cpu-clock'
    folder.mkdir(exist_ok=True)
    archive = ROOT/'releases/current/tools/kernel/board-prepared-kernel-20261009/board-debug-kernel-20261004.tar.gz'
    prefix = 'board-debug-kernel-20261004/linux-xlnx-xilinx-v2018.3/'
    count, size = 0, 0
    with tarfile.open(archive,'r:gz') as source, tarfile.open(folder/'prepared-headers.tar.gz','w:gz') as target:
        for member in source:
            if not member.name.startswith(prefix):
                continue
            name = member.name[len(prefix):]
            if any(x in name for x in ('firmware/xilinx','clk/zynqmp')) and name.endswith(('.c','.h')):
                data = source.extractfile(member)
                if data:
                    path = folder/'source-audit'/name
                    path.parent.mkdir(parents=True,exist_ok=True)
                    path.write_bytes(data.read())
            if not (name.startswith(('include/','scripts/','arch/arm64/include/','arch/arm64/tools/')) or name in ('Makefile','Module.symvers','.config','arch/arm64/Makefile')):
                continue
            info = copy.copy(member)
            info.name = 'prepared-headers/'+name
            info.pax_headers = {}
            target.addfile(info, source.extractfile(member) if member.isfile() else None)
            count += 1
            size += member.size
    print({'selected_members':count,'expanded_bytes':size,'archive':str(folder/'prepared-headers.tar.gz')})

if __name__ == '__main__':
    main()
