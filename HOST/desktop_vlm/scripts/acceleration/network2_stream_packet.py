"""Candidate cascade wire format. Offline serializer, never accesses hardware.

This new format does not alter the frozen FZS3 ABI. Coefficient order is
DW3[128], DW7[128], PW1[384], PW2[128]; PW matrices are output-major.
"""
import struct

import numpy as np

MAGIC = 0x465A4331
VERSION = 0x00030000
IMAGE_BYTES = 262144
PARAMETER_BYTES = 248584
BLOCK_HEADER_BYTES = 32
FRAME_HEADER_BYTES = 64


def _array(value, shape, dtype, name):
    array = np.asarray(value)
    if array.shape != tuple(shape) or array.dtype != np.dtype(dtype):
        raise ValueError('%s requires shape %s dtype %s' % (name, shape, dtype))
    return np.ascontiguousarray(array)


def pack_pw_weights(pw1, pw2):
    matrices = (_array(pw1, (384, 128), 'i1', 'pw1'),
                _array(pw2, (128, 384), 'i1', 'pw2'))
    chunks = []
    for matrix in matrices:
        outputs, inputs = matrix.shape
        for group in range((outputs + 11) // 12):
            for reduction in range(inputs // 16):
                word = np.zeros((12, 16), dtype='i1')
                valid = min(12, outputs - group * 12)
                word[:valid] = matrix[group * 12:group * 12 + valid,
                                      reduction * 16:(reduction + 1) * 16]
                chunks.append(word.tobytes())
    payload = b''.join(chunks)
    assert len(payload) == 520 * 192
    return payload


def pack_parameters(parameters):
    def array(name, shape, dtype):
        return _array(parameters[name], shape, dtype, name)
    shifts = array('shift', (768,), '<i4')
    scale_shift = array('scale_shift', (128,), '<i4')
    residual_shift = array('residual_shift', (1,), '<i4')
    for values in (shifts, scale_shift, residual_shift):
        if np.any(values < 0) or np.any(values > 62):
            raise ValueError('Q31 shifts must be in 0..62')
    parts = [
        array('dw3_weights', (128, 9), 'i1').tobytes(),
        array('dw7_weights', (128, 49), 'i1').tobytes(),
        array('bias', (768,), '<i4').tobytes(),
        array('multiplier', (768,), '<i4').tobytes(), shifts.tobytes(),
        pack_pw_weights(parameters['pw1_weights'], parameters['pw2_weights']),
        array('gelu', (65536,), '<i2').tobytes(),
        array('scale_multiplier', (128,), '<i4').tobytes(), scale_shift.tobytes(),
        array('residual_multiplier', (1,), '<i4').tobytes(), residual_shift.tobytes(),
    ]
    payload = b''.join(parts)
    assert len(payload) == PARAMETER_BYTES
    return payload


def build_packet(parameter_payloads, activation, manifest_sha256):
    count = len(parameter_payloads)
    if not 1 <= count <= 12:
        raise ValueError('block count must be 1..12')
    if len(activation) != IMAGE_BYTES:
        raise ValueError('activation must be one INT16 [128,32,32] image')
    if len(manifest_sha256) != 64 or any(c not in '0123456789abcdef' for c in manifest_sha256):
        raise ValueError('manifest SHA256 must be lower-case hexadecimal')
    if any(len(payload) != PARAMETER_BYTES for payload in parameter_payloads):
        raise ValueError('wrong parameter payload size')
    size = FRAME_HEADER_BYTES + IMAGE_BYTES + count * (BLOCK_HEADER_BYTES + PARAMETER_BYTES)
    sha_words = [int(manifest_sha256[i:i + 8], 16) for i in range(0, 64, 8)]
    chunks = [struct.pack('<16I', MAGIC, VERSION, count, size, IMAGE_BYTES,
                          IMAGE_BYTES, PARAMETER_BYTES, 0, *sha_words)]
    for block, payload in enumerate(parameter_payloads):
        chunks.extend((struct.pack('<8I', block, PARAMETER_BYTES, block, block + 1,
                                   0x000C0010, 0, 0, 0), payload))
        if block == 0:
            chunks.append(activation)
    packet = b''.join(chunks)
    assert len(packet) == size and size % 8 == 0 and size <= 4 * 1024 * 1024
    return packet


def identity_header(block_count, manifest_sha256):
    if not 1 <= block_count <= 12:
        raise ValueError('block count must be 1..12')
    # Reuse the packet validator rather than accepting a malformed identity.
    build_packet([bytes(PARAMETER_BYTES)] * block_count, bytes(IMAGE_BYTES), manifest_sha256)
    lines = ['#pragma once', '#define NETWORK2_BLOCK_COUNT %d' % block_count]
    lines.extend('#define NETWORK2_SHA_WORD%d 0x%sU' % (i, manifest_sha256[i * 8:i * 8 + 8])
                 for i in range(8))
    return '\n'.join(lines) + '\n'
