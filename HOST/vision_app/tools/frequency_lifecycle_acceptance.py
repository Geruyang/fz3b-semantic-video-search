"""Real client protocol: running drain/set/resume and same-link cancellation."""
import datetime
import json
import threading
import time
from vision_app.tools.board_link import ROOT,open_link,run
from vision_app.transports import Link
from vision_app.text_encoder import TextEncoder,parse_prompts
from vision_app.contract import load_contract

def main():
    config=json.loads((ROOT/'vision_app/client-config.json').read_text(encoding='utf-8'))
    events=[];errors=[];record={'ok':False,'pl_changed':False,'steps':[]}
    def receive(value):events.append((time.monotonic(),value))
    link=Link(receive,errors.append)
    def wait(predicate,timeout=40):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            for stamp,value in list(events):
                if predicate(stamp,value):return stamp,value
            if errors:raise RuntimeError(str(errors))
            time.sleep(.05)
        raise TimeoutError('frequency lifecycle acceptance deadline')
    def command(op,key,**kw):
        link.send(dict(op=op,request_id=key,**kw))
        return wait(lambda t,v:v.get('request_id')==key)[1]
    def frequency(khz,key,resume):
        ack=command('cpu_frequency',key,khz=khz)
        record['steps'].append(ack)
        assert ack['ok'] and ack['result']['verified']
        assert ack['result']['requested_khz']==khz and ack['result']['inference_resumed']==resume
        return time.monotonic()
    def running(at):
        # Give the fresh runtime time to load; periodic frames must be from the
        # resumed session, rather than old result packets draining in the wire.
        return wait(lambda t,v:t>at+25 and v.get('type')=='status' and v['inference']['state']=='RUNNING' and v['inference']['frames']>=2,timeout=65)[1]
    path=ROOT/'artifacts/ps-application-20261009/cpu-clock'/('lifecycle-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.json')
    try:
        link.connect_tcp(config['host'],config['token'])
        unused,hello=wait(lambda t,v:v.get('type')=='hello',10)
        assert hello['inference']['state']=='STOPPED'
        encoder=TextEncoder(load_contract(str(ROOT/'vision_app/semantic-contract.json')),config['model_root'])
        items=parse_prompts('杯子\n瓶子\n桌面')
        features,identity=encoder.encode(items)
        ack=command('queries','frequency-query',items=items,features=features.tolist(),identity=identity,revision=hello['query_revision']+1)
        assert ack['ok']
        assert command('start','frequency-start')['ok']
        wait(lambda t,v:v.get('type')=='result',65)
        for khz in (800000,1000000,600000,1200000):
            at=frequency(khz,'frequency-live-%d'%khz,True)
            record['running_%d'%khz]=running(at)
        link.send(dict(op='cpu_frequency',khz=600000,request_id='frequency-cancelled'))
        time.sleep(.03)
        stop=command('stop','frequency-user-stop')
        ack=wait(lambda t,v:v.get('request_id')=='frequency-cancelled')[1]
        record['cancelled']=dict(stop=stop,frequency=ack)
        assert stop['ok'] and ack['ok'] and not ack['result']['inference_resumed']
        at=frequency(1200000,'frequency-final-1200',False)
        wait(lambda t,v:t>at and v.get('type')=='status' and v['inference']['state']=='STOPPED',10)
        client=open_link()
        try:
            record['raw_before_denied']=run(client,'/root/fz3b-vision-console-20261009-001/read_clock')
            denied=command('cpu_frequency','frequency-denied-601',khz=601000)
            record['denied']=denied
            assert not denied['ok'] and '600/800/1000/1200' in denied['error']
            record['raw_after_denied']=run(client,'/root/fz3b-vision-console-20261009-001/read_clock')
            assert record['raw_before_denied']==record['raw_after_denied']
        finally:client.close()
        record['ok']=True
    finally:
        try:
            command('stop','frequency-cleanup-stop')
            record['final_cpu']=command('cpu_frequency','frequency-cleanup-default',khz=1200000)
            assert record['final_cpu']['ok'] and record['final_cpu']['result']['verified']
            time.sleep(.5)
        except BaseException as exc:
            record['ok']=False;record['cleanup_error']=str(exc)
        link.close();record['transport_errors']=errors
        path.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if not record['ok']:raise RuntimeError('frequency lifecycle qualification failed: '+str(path))
    print(json.dumps(dict(ok=True,running_auto_resume=True,same_link_stop_cancels=True,denied_default_restored=True,path=str(path))))

if __name__=='__main__':main()
