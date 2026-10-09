"""Physical USB-UART truncated request/reconnect/error ACK acceptance."""
import json
from pathlib import Path
import time
import serial
from vision_app.protocol import Decoder, JSON, encode_message


def main():
    root = Path(__file__).resolve().parents[1]
    config = json.loads((root / 'client-config.json').read_text(encoding='utf-8'))
    def port():
        handle = serial.Serial()
        handle.port, handle.baudrate, handle.timeout = 'COM6', 115200, .1
        handle.dtr = handle.rts = False
        handle.open()
        return handle
    hello = encode_message(JSON, {'op': 'hello', 'token': config['token']})
    def wait(handle, predicate, seconds=12):
        decoder = Decoder()
        end, next_hello = time.monotonic() + seconds, 0
        while time.monotonic() < end:
            if time.monotonic() >= next_hello:
                handle.write(hello)
                next_hello = time.monotonic() + 1
            for kind, payload in decoder.feed(handle.read(4096)):
                if kind == JSON:
                    message = json.loads(payload)
                    if predicate(message):
                        return message
        raise TimeoutError('UART acceptance timeout')
    with port() as handle:
        wait(handle, lambda x: x.get('type') == 'hello')
        incomplete = encode_message(JSON, {'op': 'queries', 'features_f32_b64': 'A' * 699000})
        handle.write(incomplete[:1000])
        handle.flush()
    time.sleep(.4)
    started = time.monotonic()
    with port() as handle:
        message = wait(handle, lambda x: x.get('type') == 'hello')
        recovered_s = time.monotonic() - started
        handle.write(encode_message(JSON, {'op': 'unsupported-acceptance', 'request_id': 'expected-failure'}))
        ack = wait(handle, lambda x: x.get('request_id') == 'expected-failure')
        assert ack['ok'] is False and ack['op'] == 'unsupported-acceptance', ack
    result = {'ok': True, 'truncated_query_bytes': 1000, 'declared_payload_bytes': 699000,
              'recovery_seconds': recovered_s, 'boot_id': message['boot_id'], 'failure_ack': ack,
              'r5': message['r5'], 'query_revision': message['query_revision']}
    output = root.parent / 'artifacts/ps-application-20261009/uart-reconnect.json'
    output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
