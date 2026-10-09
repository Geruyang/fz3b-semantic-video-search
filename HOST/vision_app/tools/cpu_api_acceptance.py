"""Application frequency command must return actual PM/raw-verified Hz."""
import datetime
import json
import socket
from vision_app.protocol import Decoder, JSON, encode_message
from vision_app.tools.board_link import ROOT
from vision_app.tools.frequency_reboot_acceptance import status

def main():
    config=json.loads((ROOT/'vision_app/client-config.json').read_text(encoding='utf-8'))
    report={'ok':False,'pl_changed':False}
    try:
        with socket.create_connection((config['host'],8765),timeout=12) as sock:
            sock.settimeout(12)
            decoder=Decoder()
            sock.sendall(encode_message(JSON,{'op':'hello','token':config['token']}))
            hello=status(sock,decoder,lambda x:x.get('type')=='hello')
            if hello['inference']['state']!='STOPPED':raise RuntimeError('inference must be drained')
            report['before']=hello['cpu']
            report['steps']=[]
            try:
                for khz,hz in ((600000,599999994),(800000,799999992),(1000000,999999990),(1200000,1199999988)):
                    key='cpu-verified-%d'%khz
                    sock.sendall(encode_message(JSON,dict(op='cpu_frequency',khz=khz,request_id=key)))
                    ack=status(sock,decoder,lambda x:x.get('request_id')==key)
                    report['steps'].append(ack)
                    if not ack['ok'] or not ack['result']['verified'] or ack['result']['actual_hz']!=hz:raise RuntimeError('CPU command did not verify physical frequency')
            finally:
                sock.sendall(encode_message(JSON,dict(op='cpu_frequency',khz=1200000,request_id='cpu-restore-default')))
                report['restore']=status(sock,decoder,lambda x:x.get('request_id')=='cpu-restore-default')
            report['ok']=report['restore']['ok'] and report['restore']['result']['actual_hz']==1199999988
            print(json.dumps(report,indent=2))
    finally:
        path=ROOT/'artifacts/ps-application-20261009/cpu-clock'/('api-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.json')
        path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':main()
