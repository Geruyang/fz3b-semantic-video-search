"""Generate independent exact-codec fixtures; no synthesis or board access.

Normal reference tables come from the original W16 oracle assets. Their
retained intervals are cross-checked against the currently frozen ABI10.1
parameter bytes. Folded P3 reconstruction follows the existing raw ABI.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

import numpy as np
import cnn_shared_v7_gelu_analysis as original
import cnn_w16_contract as w16


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('.'))
    parser.add_argument('--out-dir', type=Path, required=True)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=False)
    blob = bytearray(struct.pack('<I', 38))
    records = []
    base = args.root / ('artifacts/board-debug-20261006/acceleration/host/'
                        'network10-v10.1-paired-fixtures-001')

    def add(label, source_path, source_bytes, compact, full, begin, zero, tail, folded):
        spans = [int(np.ptp(compact[i:i+32].astype(np.int32)))
                 for i in range(0, len(compact), 32)]
        if max(spans) > 255:
            raise ValueError('span overflow: ' + label)
        for i in range(0, len(compact), 32):
            values = compact[i:i+32].astype(np.int32)
            anchor = int(values.min())
            restored = anchor + (((values & 255) - (anchor & 255)) & 255)
            if not np.array_equal(values, restored):
                raise ValueError('codec failure: ' + label)
        blob.extend(struct.pack('<5I', len(compact), begin, zero, tail, folded))
        blob.extend(compact.astype('<i2').tobytes())
        blob.extend(full.astype('<i2').tobytes())
        records.append(dict(label=label, source_path=str(source_path),
                            source_sha256=digest(source_bytes), entries=len(compact),
                            retained_sha256=digest(compact.astype('<i2').tobytes()),
                            golden_sha256=digest(full.astype('<i2').tobytes()),
                            max_segment_span=max(spans),
                            full_domain_values=65536,
                            raw_bytes=len(compact)*2,
                            logical_compressed_bytes=len(compact)+2*len(spans),
                            extra_preflight_read_words=len(compact)//8))

    for profile, block, path in original._block_paths(args.root):
        source = path.read_bytes()
        fields, _ = w16.layout(w16.PROFILES[profile]['channels'])
        field = next(item for item in fields if item['name'] == 'gelu_lut_i16')
        table = np.frombuffer(source[field['offset']:field['offset']+field['bytes']],
                              dtype='<i2')
        nonzero = np.flatnonzero(table != 0)
        nonfull = np.flatnonzero(table != 32767)
        zero, tail = int(nonzero[0]), int(nonfull[-1])+1
        begin, end = zero & ~7, (tail+7) & ~7
        compact = table[begin:end]
        channels = w16.PROFILES[profile]['channels']
        stride = {64:10985,128:21081,256:59705}[channels]
        gelu_offset = {64:881,128:1761,256:3521}[channels]
        packed_path = base / ('profile%d-params-%d-blocks-v10.1.bin' %
                             (profile, {0:12,1:20,2:4}[profile]))
        packed = packed_path.read_bytes()
        offset = (stride*block+gelu_offset)*16
        if packed[offset:offset+len(compact)*2] != compact.tobytes():
            raise ValueError('ABI10.1 compact/reference mismatch')
        add('profile%d/block%d' % (profile,block), path, source, compact,
            table, begin, zero, tail, 0)
        records[-1]['abi10_1_parameter_sha256'] = digest(packed)

    p3_path = args.root / ('artifacts/board-debug-20261007/acceleration/host/'
                          'cnn-v10-p3-chain-parameters-002/p3-params.bin')
    p3 = p3_path.read_bytes()
    for name, offset in [('dw',912),('pw',7184)]:
        compact = np.frombuffer(p3[offset*16:(offset+4096)*16], dtype='<i2')
        full = np.empty(65536, dtype='<i2')
        full[:32768] = compact
        full[32768] = 0
        full[32769:] = (np.arange(1,32768,dtype=np.int32)+
                        compact[32767:0:-1].astype(np.int32)).astype('<i2')
        add('p3/'+name,p3_path,p3,compact,full,0,0,65536,1)
    fixture = args.out_dir / 'fixtures.bin'
    fixture.write_bytes(blob)
    receipt = dict(schema='cnn-v10-segmented-gelu-independent-fixtures-v1',
                   status='PYTHON_EXACT_CPP_PENDING', hardware_execution=False,
                   rtl_simulation=False, resource_estimate_kind='logical_bits_only',
                   table_count=len(records), full_domain_values=65536*len(records),
                   previous_capacity_bits=56256*16,
                   proposed_capacity_bits=56256*8+1758*16,
                   logical_capacity_reduction_percent=46.875,
                   raw_parameter_abi_unchanged=True, ddr_load_bytes_unchanged=True,
                   fixture_sha256=digest(blob), tables=records)
    (args.out_dir/'fixture-receipt.json').write_text(
        json.dumps(receipt,indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k:v for k,v in receipt.items() if k!='tables'}))


if __name__ == '__main__':
    main()
