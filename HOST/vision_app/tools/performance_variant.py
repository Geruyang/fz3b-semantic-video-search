"""Change only application preprocessing scheduling, with normal owner drain."""
import argparse
import datetime
import json
from vision_app.tools.board_link import ROOT, open_link, run

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--async-preprocess',choices=('on','off'),required=True)
    args=parser.parse_args()
    remote='/root/fz3b-vision-console-20261009-001'
    client=open_link()
    try:
        run(client,'systemctl stop fz3b-vision-console.service',timeout=370)
        run(client,'if fuser /dev/network10_v10_signed40; then exit 17; fi')
        s=client.open_sftp()
        try:
            for name in ('prefetch.py','board_agent.py','camera.py'):
                s.put(str(ROOT/'vision_app'/name),remote+'/vision_app/'+name)
            with s.file(remote+'/config.json') as handle:config=json.loads(handle.read().decode())
            config['preprocess_async']=args.async_preprocess=='on'
            with s.file(remote+'/config.json','w') as handle:handle.write(json.dumps(config))
        finally:s.close()
        run(client,'systemctl start fz3b-vision-console.service')
        state=json.loads(run(client,'cd '+remote+'; python3 -B -m vision_app.cpu_clock_service --status'))
        report=dict(preprocess_async=config['preprocess_async'],clock=state,pl_changed=False)
        path=ROOT/'artifacts/ps-application-20261009'/('performance-variant-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.json')
        path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(report))
    finally:client.close()

if __name__=='__main__':main()
