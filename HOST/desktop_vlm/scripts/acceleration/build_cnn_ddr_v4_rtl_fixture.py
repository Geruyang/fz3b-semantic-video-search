"""Root-owned binary-to-128-bit-mem fixture adapter; no board/tool invocation."""
import argparse
import hashlib
import json
from pathlib import Path


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--sample', default='image-00', choices=['image-00', 'image-01', 'image-02'])
    parser.add_argument('--blocks', type=int, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    original = args.manifest.read_bytes()
    manifest = json.loads(original)
    c = manifest['channel_count']
    if c not in (128, 256):
        raise ValueError('unsupported profile')
    profile, width, maximum = (0, 32, 12) if c == 128 else (1, 16, 20)
    if not 2 <= args.blocks <= maximum:
        raise ValueError('RTL fixture requires at least two blocks')
    stride = (138*c + 16 + 131072 +
              96*((3*c+5)//6*(c//16) + (c+5)//6*(3*c//16)))

    def source(name):
        meta = manifest['files'][name]
        raw = (args.manifest.parent / name).read_bytes()
        if len(raw) != meta['bytes'] or digest(raw) != meta['sha256']:
            raise ValueError('fixture integrity mismatch: ' + name)
        return raw

    params = source('params-v4.bin')
    if len(params) != stride*manifest['block_count']:
        raise ValueError('parameter length does not match frozen layout')
    params = params[:stride*args.blocks]
    inp = source(args.sample + '/input-slot0-hcw.i16le')
    expected = source(args.sample + '/block-%02d-output-slot%d-hcw.i16le' %
                      (args.blocks-1, args.blocks & 1))
    if len(inp) != c*width*width*2 or len(expected) != len(inp):
        raise ValueError('activation extent mismatch')
    args.out.mkdir(parents=True, exist_ok=False)
    files = {}
    for name, raw in [('params.mem', params), ('input.mem', inp), ('expected.mem', expected)]:
        if len(raw) % 16:
            raise ValueError('128-bit alignment required')
        mem = ''.join('%032x\n' % int.from_bytes(raw[i:i+16], 'little')
                      for i in range(0, len(raw), 16)).encode('ascii')
        path = args.out / name
        path.write_bytes(mem)
        # Independent round trip guards byte order and accidental formatting changes.
        decoded = b''.join(int(line, 16).to_bytes(16, 'little') for line in mem.splitlines())
        if decoded != raw:
            raise AssertionError('mem round-trip mismatch')
        files[name] = {'path': str(path.resolve()), 'bytes': len(mem),
                       'sha256': digest(mem), 'source_binary_sha256': digest(raw),
                       'word_count': len(raw)//16}
    receipt = {'status': 'OFFLINE_RTL_FIXTURE_ONLY', 'profile': profile,
               'blocks': args.blocks, 'sample': args.sample,
               'source_manifest': str(args.manifest.resolve()),
               'source_manifest_sha256': digest(original), 'files': files,
               'plusargs': ['PARAMS='+files['params.mem']['path'].replace('\\', '/'),
                            'INPUT='+files['input.mem']['path'].replace('\\', '/'),
                            'EXPECTED='+files['expected.mem']['path'].replace('\\', '/'),
                            'PROFILE='+str(profile), 'BLOCKS='+str(args.blocks)]}
    (args.out / 'manifest.json').write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'status': receipt['status'], 'profile': profile, 'blocks': args.blocks,
                      'words': {k: v['word_count'] for k, v in files.items()}}))


if __name__ == '__main__':
    main()
