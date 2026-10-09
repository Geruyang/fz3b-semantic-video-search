"""Real-board application acceptance, raw evidence with separate clocks."""
import argparse
import json
from pathlib import Path
import threading
import time
import datetime
import numpy as np
from vision_app.transports import Link
from vision_app.contract import load_contract
from vision_app.text_encoder import TextEncoder, parse_prompts
from vision_app.protocol import JSON


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--seconds', type=float, default=25)
    parser.add_argument('--serial', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    config = json.loads((root / 'client-config.json').read_text(encoding='utf-8'))
    contract = load_contract(str(root / 'semantic-contract.json'))
    events, errors = [], []
    hello = threading.Event()
    def receive(message):
        events.append({'received_monotonic': time.monotonic(), 'message': message})
        if message.get('type') == 'hello':
            hello.set()
    link = Link(receive, errors.append)
    name = ('serial-smoke-' if args.serial else 'live-smoke-') + datetime.datetime.now().strftime('%Y%m%dT%H%M%S')
    output = root.parent / 'artifacts/ps-application-20261009' / name
    output.mkdir(exist_ok=True)
    try:
        if args.serial:
            link.connect_serial('COM6', config['token'])
        else:
            link.connect_tcp(config['host'], config['token'])
        if not hello.wait(10):
            raise RuntimeError('no hello: ' + str(errors))
        previous_revision = next(e['message']['query_revision'] for e in events if e['message'].get('type') == 'hello')
        encoder = TextEncoder(contract, config['model_root'])
        items = parse_prompts('杯子\n瓶子\n手机\n键盘\n桌面\n房间')
        features, identity = encoder.encode(items)
        link.send({'op': 'queries', 'items': items, 'features': features.tolist(), 'identity': identity, 'revision': previous_revision + 1, 'request_id': 'smoke-query'})
        end = time.monotonic() + (60 if args.serial else 5)
        while time.monotonic() < end and not any(e['message'].get('request_id') == 'smoke-query' for e in events):
            time.sleep(.1)
        ack = next(e['message'] for e in events if e['message'].get('request_id') == 'smoke-query')
        if not ack['ok']:
            raise RuntimeError(ack['error'])
        link.send({'op': 'start', 'request_id': 'smoke-start'})
        started, before = time.monotonic(), link.state.preview_count
        snapshots = []
        while time.monotonic() - started < args.seconds:
            time.sleep(.25)
            if link.state.preview:
                snapshots.append({'received': time.monotonic(), 'frame_id': link.state.preview[0]['frame_id']})
        wall = time.monotonic() - started
        sampled_events = list(events)
        results = [e for e in sampled_events if e['message'].get('type') == 'result']
        if link.state.preview:
            (output / 'preview.jpg').write_bytes(link.state.preview[1])
        if link.state.result_image:
            (output / 'inference-frame.jpg').write_bytes(link.state.result_image[1])
        report = {'preview_received_fps': (link.state.preview_count - before) / wall, 'inference_results_received': len(results), 'inference_received_fps_including_setup': len(results) / wall, 'elapsed_s': wall, 'window_start_monotonic': started, 'window_end_monotonic': started+wall, 'errors': errors, 'preview_samples': snapshots, 'events': sampled_events}
        if len(results) > 1:
            report['inference_result_interval_fps'] = (len(results)-1) / (results[-1]['received_monotonic']-results[0]['received_monotonic'])
            report['result_age_p50_ms'] = float(np.median([e['message']['result_age_ms'] for e in results]))
        statuses = [e['message'] for e in sampled_events if e['message'].get('type') == 'status']
        if statuses:
            report['last_board_status'] = statuses[-1]
        report['evidence_path'] = str(output)
        (output / 'evidence.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(json.dumps({k: v for k, v in report.items() if k not in ('events', 'preview_samples')}, ensure_ascii=False))
        if errors or not results or not link.state.preview:
            raise RuntimeError('live smoke did not produce both video and real inference results')
    finally:
        if hello.is_set():
            link.send({'op': 'stop', 'request_id': 'smoke-stop'})
            time.sleep(3)
        link.close()


if __name__ == '__main__':
    main()
