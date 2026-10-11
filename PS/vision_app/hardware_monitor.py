"""Read existing Linux AMS exports once a second; never configure hardware."""
import copy
import math
import os
import threading
import time

CHANNELS={
    'cpu_fpd_c':'in_temp1_remote_temp', 'ps_lpd_c':'in_temp0_ps_temp', 'pl_c':'in_temp2_pl_temp',
    'ps_fpd_v':'in_voltage8_vccpsintfp', 'ps_lpd_v':'in_voltage7_vccpsintlp',
    'ps_aux_v':'in_voltage9_vccpsaux', 'ps_ddr_v':'in_voltage10_vccpsddr',
    'pl_core_v':'in_voltage18_vccint', 'pl_aux_v':'in_voltage19_vccaux',
    'pl_bram_v':'in_voltage22_vccbram', 'ps_pll_v':'in_voltage0_vcc_pspll0',
}


def read(path):
    with open(path) as stream:return stream.read().strip()


def pl_operating():
    try:return read('/sys/class/fpga_manager/fpga0/state')=='operating'
    except (OSError,IOError):return False


class HardwareMonitor:
    def __init__(self,root='/sys/bus/iio/devices',pl_ready=None,proc_stat='/proc/stat'):
        self.root=root;self.pl_ready=pl_ready or pl_operating;self.proc_stat=proc_stat
        self.lock=threading.Lock();self.sequence=0;self.previous_cpu={}
        self.snapshot={'available':False,'values':{},'sample_id':0,'sampled_at':None,'cpu_usage_percent':None}

    def cpu_usage(self):
        usage={}
        try:lines=read(self.proc_stat).splitlines()
        except (OSError,IOError):return {}
        for line in lines:
            fields=line.split()
            if not fields or fields[0] not in ('cpu','cpu0','cpu1','cpu2','cpu3'):continue
            counters=[int(x) for x in fields[1:9]]
            total=sum(counters);idle=counters[3]+counters[4];previous=self.previous_cpu.get(fields[0])
            self.previous_cpu[fields[0]]=(total,idle)
            if previous and total>previous[0]:usage[fields[0]]=max(0.,min(100.,100*(1-(idle-previous[1])/(total-previous[0]))))
        return usage

    def sample(self):
        values={};reason=None;usage=self.cpu_usage();started=time.monotonic()
        # AMD documents lockup risk if PL temperature is queried during initialization.
        # The application is ordered after the loader; also gate every sample on manager state.
        if not self.pl_ready():reason='PL is not operating'
        else:
            try:devices=[os.path.join(self.root,name) for name in os.listdir(self.root) if name.startswith('iio')]
            except (OSError,IOError):devices=[]
            for device in devices:
                try:
                    if read(os.path.join(device,'name'))!='ams':continue
                except (OSError,IOError):continue
                for key,stem in CHANNELS.items():
                    try:
                        raw=float(read(os.path.join(device,stem+'_raw')))
                        scale=float(read(os.path.join(device,stem+'_scale')))
                        offset_path=os.path.join(device,stem+'_offset')
                        offset=float(read(offset_path)) if os.path.isfile(offset_path) else 0.
                        value=(raw+offset)*scale/1000.
                        if math.isfinite(value):values[key]=value
                    except (OSError,IOError,ValueError):pass
                break
        self.sequence+=1
        report=dict(available=bool(values),values=values,sample_id=self.sequence,sampled_at=time.monotonic(),
                    cpu_usage_percent=usage.get('cpu'),cpu_cores_percent=[usage.get('cpu%d'%i) for i in range(4)],
                    read_ms=(time.monotonic()-started)*1000,source='Linux AMS / procfs',error=reason)
        with self.lock:self.snapshot=report

    def status(self):
        with self.lock:report=copy.deepcopy(self.snapshot)
        report['age_s']=time.monotonic()-report['sampled_at'] if report['sampled_at'] is not None else None
        report['stale']=report['age_s'] is None or report['age_s']>3
        return report

    def run(self,stop):
        while not stop.is_set():
            self.sample()
            stop.wait(1.)
