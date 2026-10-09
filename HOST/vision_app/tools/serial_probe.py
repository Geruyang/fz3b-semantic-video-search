import json
from pathlib import Path
import time
import serial
import socket
from vision_app.protocol import Decoder, JSON, encode_message

config = json.loads(Path('vision_app/client-config.json').read_text(encoding='utf-8'))
p = serial.Serial(port=None, baudrate=115200, timeout=.2, write_timeout=2)
p.dtr = p.rts = False
p.port = 'COM6'
p.open()
try:
    p.write(encode_message(JSON, {'op': 'hello', 'token': config['token']}))
    decoder, count, types = Decoder(), 0, []
    end = time.monotonic() + 4
    while time.monotonic() < end:
        data = p.read(4096)
        count += len(data)
        for kind, value in decoder.feed(data):
            if kind == JSON:
                message = json.loads(value)
                types.append(message.get('type'))
    print({'serial_rx': count, 'decoder_errors': decoder.errors, 'message_types': types})
finally:
    p.close()
s = socket.create_connection((config['host'], 8765))
s.settimeout(3)
s.sendall(encode_message(JSON, {'op': 'hello', 'token': config['token']}))
decoder = Decoder()
try:
    for kind, value in decoder.feed(s.recv(65536)):
        if kind == JSON:
            message = json.loads(value)
            print({k: message.get(k) for k in ('serial', 'r5', 'inference')})
finally:
    s.close()
