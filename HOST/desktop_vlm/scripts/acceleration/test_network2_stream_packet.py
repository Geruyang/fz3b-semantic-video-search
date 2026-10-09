import struct
import unittest

import numpy as np

from network2_stream_packet import (build_packet, pack_pw_weights, PARAMETER_BYTES,
                                   IMAGE_BYTES)


class PacketTests(unittest.TestCase):
    def test_weight_group_reduction_lane_order_and_tail(self):
        a = (np.arange(384 * 128) % 251 - 125).astype('i1').reshape(384, 128)
        b = (np.arange(128 * 384) % 253 - 126).astype('i1').reshape(128, 384)
        packed = np.frombuffer(pack_pw_weights(a, b), dtype='i1').reshape(520, 12, 16)
        for matrix, base in ((a, 0), (b, 256)):
            outputs, inputs = matrix.shape
            for c in range(outputs):
                for reduction in range(inputs // 16):
                    np.testing.assert_array_equal(
                        packed[base + (c // 12) * (inputs // 16) + reduction, c % 12],
                        matrix[c, reduction * 16:(reduction + 1) * 16])
        self.assertTrue(np.all(packed[256 + 10 * 24:, 8:] == 0))

    def test_one_and_twelve_block_packet_boundaries(self):
        sha = '0123456789abcdef' * 4
        for count in (1, 12):
            payloads = [bytes([i + 1]) * PARAMETER_BYTES for i in range(count)]
            activation = bytes([0xAB]) * IMAGE_BYTES
            packet = build_packet(payloads, activation, sha)
            header = struct.unpack_from('<16I', packet)
            self.assertEqual(header[2:4], (count, len(packet)))
            self.assertEqual(header[8], 0x01234567)
            offset = 64
            for block in range(count):
                block_header = struct.unpack_from('<8I', packet, offset)
                self.assertEqual(block_header[:4], (block, PARAMETER_BYTES, block, block + 1))
                offset += 32
                self.assertEqual(packet[offset:offset + PARAMETER_BYTES], payloads[block])
                offset += PARAMETER_BYTES
                if block == 0:
                    self.assertEqual(packet[offset:offset + IMAGE_BYTES], activation)
                    offset += IMAGE_BYTES
            self.assertEqual(offset, len(packet))
            self.assertEqual(len(packet), 510824 if count == 1 else 3245600)


if __name__ == '__main__':
    unittest.main()
