"""Verified v5 binary-to-128-bit-hex adapter for the shared-DDR RTL testbench."""
import argparse
import hashlib
import json
from pathlib import Path


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--profile', type=int, choices=(0, 1, 2), required=True)
    parser.add_argument('--blocks', type=int, required=True)
    parser.add_argument('--params', required=True)
    parser.add_argument('--input', required=True)
    parser.add_argument('--expected', required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    raw_manifest = args.manifest.read_bytes()
    manifest = json.loads(raw_manifest)
    c, width, maximum = ((128, 32, 12), (256, 16, 20), (64, 64, 4))[args.profile]
    if not 2 <= args.blocks <= maximum:
        raise ValueError('shared-memory fixture requires at least two valid blocks')
    stride = 220*c+16+131072+192*(((3*c+5)//6)*(c//16)+((c+5)//6)*(3*c//16))

    def load(relative):
        path = (args.manifest.parent / relative).resolve()
        path.relative_to(args.manifest.parent.resolve())
        declaration = manifest['files'][relative]
        value = path.read_bytes()
        if len(value) != declaration['bytes'] or sha(value) != declaration['sha256']:
            raise ValueError('source fixture integrity mismatch: ' + relative)
        return value

    params, source, expected = (load(name) for name in (args.params, args.input, args.expected))
    if len(params) != stride*args.blocks:
        raise ValueError('parameter payload must contain exactly the requested blocks')
    if len(source) != 2*c*width*width or len(expected) != len(source):
        raise ValueError('HCW activation extent mismatch')
    args.out.mkdir(parents=True, exist_ok=False)
    files = {}
    for name, binary in [('params.mem', params), ('input.mem', source), ('expected.mem', expected)]:
        mem = ''.join('%032x\n' % int.from_bytes(binary[i:i+16], 'little')
                      for i in range(0, len(binary), 16)).encode('ascii')
        if b''.join(int(line, 16).to_bytes(16, 'little') for line in mem.splitlines()) != binary:
            raise AssertionError('128-bit memory round trip failed')
        path = args.out / name
        path.write_bytes(mem)
        files[name] = {'path': path.resolve().as_posix(), 'bytes': len(mem), 'sha256': sha(mem),
                       'source_binary_sha256': sha(binary), 'word_count': len(binary)//16}
    report = {'status': 'V5_OFFLINE_RTL_FIXTURE_ONLY', 'profile': args.profile, 'blocks': args.blocks,
              'source_manifest_sha256': sha(raw_manifest), 'files': files,
              'converter_sha256': sha(Path(__file__).read_bytes()),
              'plusargs': ['PARAMS='+files['params.mem']['path'], 'INPUT='+files['input.mem']['path'],
                           'EXPECTED='+files['expected.mem']['path'], 'PROFILE='+str(args.profile),
                           'BLOCKS='+str(args.blocks)]}
    (args.out / 'manifest.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()
