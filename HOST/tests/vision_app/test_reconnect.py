import json
import unittest
from types import SimpleNamespace
from vision_app.protocol import Decoder, JSON, encode_message


class Reconnect(unittest.TestCase):
    def test_authenticated_hello_abandons_incomplete_query(self):
        validator = lambda value: value.get('op') == 'hello' and value.get('token') == 'test'
        decoder = Decoder(reset_validator=validator)
        query = encode_message(JSON, {'op': 'queries', 'features_f32_b64': 'A' * 699000})
        self.assertEqual(decoder.feed(query[:1000]), [])
        hello = encode_message(JSON, {'op': 'hello', 'token': 'test'})
        result = []
        for byte in hello:
            result += decoder.feed(bytes([byte]))
        self.assertEqual([json.loads(p) for kind, p in result], [{'op': 'hello', 'token': 'test'}])
        self.assertLess(len(decoder.buffer), 4)
        self.assertEqual(len(decoder.feed(encode_message(JSON, {'op': 'status'}))), 1)

    def test_invalid_hello_cannot_abandon_query(self):
        decoder = Decoder(reset_validator=lambda value: value.get('token') == 'test')
        query = encode_message(JSON, {'op': 'queries', 'features_f32_b64': 'A' * 699000})
        decoder.feed(query[:1000])
        self.assertEqual(decoder.feed(encode_message(JSON, {'op': 'hello', 'token': 'wrong'})), [])
        self.assertGreater(len(decoder.buffer), 1000)

    def test_query_cache_requires_same_acknowledged_revision(self):
        from vision_app.client import Window
        from vision_app.text_encoder import parse_prompts
        calls = []
        items = parse_prompts('a cup')
        fake = SimpleNamespace(link=True, prompts=SimpleNamespace(toPlainText=lambda: 'a cup'),
                               last_encoded={'items': items, 'revision': 3}, accepted_revision=2,
                               encode=lambda: calls.append('encode'), request=lambda x: calls.append(x['op']))
        Window.start_inference(fake)
        self.assertEqual(calls, ['encode'])
        self.assertTrue(fake.pending_start)

    def test_stop_cancels_pending_start(self):
        from vision_app.client import Window
        calls = []
        fake = SimpleNamespace(pending_start=True, request=lambda x: calls.append(x['op']))
        Window.stop_inference(fake)
        self.assertFalse(fake.pending_start)
        self.assertEqual(calls, ['stop'])

    def test_failed_ack_retains_request_identity(self):
        from vision_app.board_agent import Agent
        agent = Agent.__new__(Agent)
        answer = agent.reply({'op': 'unsupported', 'request_id': 'failed-one'})
        self.assertFalse(answer['ok'])
        self.assertEqual(answer['request_id'], 'failed-one')
        self.assertEqual(answer['op'], 'unsupported')

    def test_labels_have_same_limit_as_board(self):
        from vision_app.text_encoder import parse_prompts
        with self.assertRaises(ValueError):
            parse_prompts('x' * 1001 + '|a cup')

    def test_edit_during_encoding_reencodes_before_start(self):
        from vision_app.client import Window
        from vision_app.text_encoder import parse_prompts
        calls = []
        fake = SimpleNamespace(pending_start=True, accepted_revision=3,
                               last_encoded={'items': parse_prompts('a cup'), 'revision': 3},
                               prompts=SimpleNamespace(toPlainText=lambda: 'a bottle'),
                               encode=lambda: calls.append('encode'), request=lambda x: calls.append(x['op']))
        Window.resume_pending_start(fake)
        self.assertEqual(calls, ['encode'])
        self.assertTrue(fake.pending_start)


if __name__ == '__main__':
    unittest.main()
