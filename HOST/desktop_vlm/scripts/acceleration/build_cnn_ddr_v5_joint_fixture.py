"""Materialize complete v5 CSIM fixtures from a verified joint integer oracle.

Only concatenates declared parameters and transposes CHW bytes to HCW. It does
not recompute the numerical expected output or alter the source manifest.
"""
import argparse
import hashlib
import json
from pathlib import Path


def digest(value):
    return hashlib.sha256(value).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--expected-manifest-sha256', required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    raw_manifest = args.manifest.read_bytes()
    if digest(raw_manifest) != args.expected_manifest_sha256:
        raise ValueError('joint oracle manifest SHA mismatch')
    source = json.loads(raw_manifest)
    if 'profiles' not in source and source.get('scope', {}).get('profile') == 2:
        # The isolated N0 preflight predates the three-profile joint envelope.
        scope = source['scope']
        source['profiles'] = {'profile2': {
            'channels': scope['channels'], 'width': scope['width'],
            'blocks': scope['block_count'], 'stride_bytes': source['params']['stride_bytes'],
            'params': source['params']['blocks']}}
        source['results'] = [
            {'sample_id': result['sample_id'], 'profile2_input_i16': result['profile2_input_hcw'],
             'profile2_blocks': [{'output': item['output_chw'], 'output_hcw': item['output_hcw']}
                                 for item in result['blocks']]}
            for result in source['results']]
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out/'builder-source.py').write_bytes(Path(__file__).read_bytes())
    files, cases, profiles = {}, [], {}

    def read(record):
        name = record['path']
        path = (args.manifest.parent/name).resolve()
        path.relative_to(args.manifest.parent.resolve())
        value = path.read_bytes()
        declaration = source['files'][name]
        if (len(value) != record['bytes'] or digest(value) != record['sha256'] or
                len(value) != declaration['bytes'] or digest(value) != declaration['sha256']):
            raise ValueError('oracle file integrity mismatch: '+name)
        return value

    def write(name, value):
        path = args.out/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)
        files[name] = {'bytes': len(value), 'sha256': digest(value)}
        return path.resolve().as_posix()

    for profile, c, w, blocks in ((0, 128, 32, 12), (1, 256, 16, 20), (2, 64, 64, 4)):
        key = 'profile%d' % profile
        spec = source['profiles'].get(key, {})
        if not spec.get('params'):
            continue
        stride = 220*c+16+131072+192*(((3*c+5)//6)*(c//16)+((c+5)//6)*(3*c//16))
        if (spec['channels'], spec['width'], spec['blocks'], spec['stride_bytes']) != (c, w, blocks, stride):
            raise ValueError('profile geometry/layout mismatch')
        chunks = [read(record) for record in spec['params']]
        if len(chunks) != blocks or any(len(value) != stride for value in chunks):
            raise ValueError('parameter block extent mismatch')
        parameter_paths = {count: write(key+'/params-%d-blocks.bin' % count, b''.join(chunks[:count]))
                           for count in (2, blocks)}
        profiles[key] = {'channels': c, 'width': w, 'blocks': blocks, 'stride_bytes': stride,
                         'params': parameter_paths}
        for result in source['results']:
            sid = result['sample_id']
            input_record = result[key+'_input_i16']
            if input_record['shape'] != [w, c, w] or input_record['dtype'] != '<i2':
                raise ValueError('input must already be HCW signed16')
            input_path = write(key+'/'+sid+'/input-hcw.i16', read(input_record))
            for count in (2, blocks):
                block_record = result[key+'_blocks'][count-1]
                record = block_record['output']
                if record['shape'] != [c, w, w] or record['dtype'] != '<i2':
                    raise ValueError('oracle Add must be CHW signed16')
                chw = read(record)
                if len(chw) != 2*c*w*w:
                    raise ValueError('activation byte count mismatch')
                hcw = b''.join(chw[2*(channel*w+y)*w:2*(channel*w+y+1)*w]
                               for y in range(w) for channel in range(c))
                round_trip = b''.join(hcw[2*(y*c+channel)*w:2*(y*c+channel+1)*w]
                                      for channel in range(c) for y in range(w))
                if round_trip != chw:
                    raise AssertionError('HCW layout round trip failed')
                if 'output_hcw' in block_record and read(block_record['output_hcw']) != hcw:
                    raise ValueError('oracle serialized HCW differs from independently transposed CHW')
                expected_path = write(key+'/'+sid+'/expected-%d-blocks-hcw.i16' % count, hcw)
                cases.append({'profile': profile, 'blocks': count, 'sample_id': sid,
                              'csim_args': [parameter_paths[count], input_path, expected_path,
                                            str(profile), str(count)],
                              'expected_source': record})
    report = {'status': 'V5_CSIM_SHARED_DDR_FIXTURES_NOT_EXECUTED', 'pl_execution': False,
              'source_manifest_sha256': digest(raw_manifest), 'profiles': profiles,
              'builder_sha256': digest(Path(__file__).read_bytes()), 'cases': cases, 'files': files}
    (args.out/'manifest.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'profiles': list(profiles), 'cases': len(cases), 'files': len(files)}))


if __name__ == '__main__':
    main()
