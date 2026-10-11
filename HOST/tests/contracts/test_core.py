import importlib
import importlib.util
import json
import struct
import unittest
import zlib

import numpy as np


class CoreContract(unittest.TestCase):
    def module(self, name):
        self.assertIsNotNone(importlib.util.find_spec('vision_app.' + name), name + ' implementation missing')
        return importlib.import_module('vision_app.' + name)

    def test_protocol_fragmentation_and_noise(self):
        p = self.module('protocol')
        data = p.encode_message(p.JSON, {'request_id': 'one', 'op': 'status'})
        decoder = p.Decoder()
        out = []
        for b in b'console noise\r\n' + data:
            out += decoder.feed(bytes([b]))
        self.assertEqual(len(out), 1)
        self.assertEqual(json.loads(out[0][1]), {'request_id': 'one', 'op': 'status'})

    def test_protocol_crc_and_length_recover(self):
        p = self.module('protocol')
        good = p.encode_message(p.JSON, {'ok': True})
        bad = bytearray(good)
        bad[-1] ^= 1
        oversized = p.HEADER.pack(p.MAGIC, 1, p.JSON, 0, p.MAX_PAYLOAD + 1, 0)
        decoder = p.Decoder()
        out = decoder.feed(bytes(bad) + oversized + good)
        self.assertEqual(len(out), 1)
        self.assertGreaterEqual(decoder.errors, 2)
        self.assertLessEqual(len(decoder.buffer), p.MAX_PAYLOAD + p.HEADER.size)

    def test_jpeg_frame_identity(self):
        p = self.module('protocol')
        meta, jpeg = p.unpack_image(p.pack_image({'frame_id': 9, 'query_revision': 3}, b'\xff\xd8data\xff\xd9'))
        self.assertEqual(meta['frame_id'], 9)
        self.assertEqual(jpeg, b'\xff\xd8data\xff\xd9')
        with self.assertRaises(ValueError):
            p.unpack_image(struct.pack('<I', 1000) + b'short')

    def test_latest_slot_drops_old_frames(self):
        s = self.module('state')
        slot = s.LatestSlot()
        for i in range(100):
            slot.publish({'frame_id': i})
        version, value = slot.get_after(0, timeout=.01)
        self.assertEqual(version, 100)
        self.assertEqual(value['frame_id'], 99)
        self.assertIsNone(slot.get_after(version, timeout=.001))

    def test_atomic_queries_and_cosine(self):
        s = self.module('state')
        queries = s.Candidates()
        a = np.zeros((2, 512), dtype=np.float32)
        a[0, 0], a[1, 1] = 1, 1
        items = [{'id': 'a', 'label': 'cup', 'text': 'a cup'}, {'id': 'b', 'label': 'bottle', 'text': 'a bottle'}]
        queries.replace(items, a, 1, {'contract_id': 'test'})
        result = queries.match(a[0] * 5, threshold=.2)
        self.assertEqual(result['best']['id'], 'a')
        self.assertAlmostEqual(result['best']['score'], 1)
        self.assertEqual(result['query_revision'], 1)
        with self.assertRaises(ValueError):
            queries.replace(items, a, 1, {'contract_id': 'test'})
        with self.assertRaises(ValueError):
            queries.replace(items, a * float('nan'), 2, {'contract_id': 'test'})
        self.assertEqual(queries.match(a[1])['query_revision'], 1)
        with self.assertRaises(ValueError):
            queries.match(np.zeros(512))

    def test_serial_fragments_reassemble_and_bound_memory(self):
        p = self.module('protocol')
        blob = p.pack_image({'frame_id': 5}, b'jpeg' * 1600)
        parts = list(p.fragment_image(blob, 5, 1024))
        assembler = p.ImageAssembler()
        result = None
        for part in parts:
            result = assembler.feed(part)
        self.assertEqual(result, blob)
        with self.assertRaises(ValueError):
            assembler.feed(p.CHUNK_HEADER.pack(8, p.MAX_PAYLOAD + 1, 0) + b'x')


if __name__ == '__main__':
    unittest.main()
