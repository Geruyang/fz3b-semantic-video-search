import importlib.util
import tempfile
from pathlib import Path
import unittest
import json
import base64
import numpy as np


class ServiceContract(unittest.TestCase):
    def test_cpu_rejects_unlisted_and_displays_current(self):
        from vision_app.board_agent import CpuPolicy
        with tempfile.TemporaryDirectory() as d:
            for key, value in {'scaling_cur_freq': '1066666', 'scaling_available_frequencies': '299999 399999 599999 1199999', 'scaling_governor': 'userspace', 'affected_cpus': '0 1 2 3', 'scaling_min_freq': '299999', 'scaling_max_freq': '1199999'}.items():
                Path(d, key).write_text(value)
            cpu = CpuPolicy(d)
            self.assertEqual(cpu.status()['current_khz'], 1066666)
            for invalid in (1066666, True, 1200000, -1, '599999'):
                with self.assertRaises(ValueError):
                    cpu.set_frequency(invalid)
            self.assertFalse(Path(d, 'scaling_setspeed').exists())

    def test_prompt_input_contract(self):
        from vision_app.text_encoder import parse_prompts
        self.assertEqual(parse_prompts('杯子')[0]['text'], 'a photo of a cup')
        self.assertEqual(parse_prompts('桌上的杯子 | a cup on a desk')[0]['label'], '桌上的杯子')
        for bad in ('', '|a cup', '一只红色的杯子'):
            with self.assertRaises(ValueError):
                parse_prompts(bad)

    def test_transport_keeps_preview_independent_of_results(self):
        self.assertIsNotNone(importlib.util.find_spec('vision_app.transports'), 'transport implementation missing')
        from vision_app.transports import ReceiverState
        from vision_app.protocol import PREVIEW, JSON, pack_image, json_bytes
        state = ReceiverState()
        state.accept(JSON, json_bytes({'type': 'result', 'frame_id': 1, 'query_revision': 1}))
        for i in range(100):
            state.accept(PREVIEW, pack_image({'frame_id': i}, b'jpeg'))
        self.assertEqual(state.preview[0]['frame_id'], 99)
        self.assertEqual(state.last_result['frame_id'], 1)
        self.assertEqual(state.preview_count, 100)

    def test_compact_query_transport_is_lossless_float32(self):
        from vision_app.transports import Link
        from vision_app.protocol import Decoder
        values = np.random.default_rng(123).normal(size=(6, 512)).astype(np.float32)
        link = Link(lambda x: None, lambda x: None)
        link.send({'op': 'queries', 'features': values.tolist()})
        wire = link.outgoing.get_nowait()
        message = json.loads(Decoder().feed(wire)[0][1])
        restored = np.frombuffer(base64.b64decode(message['features_f32_b64'], validate=True), dtype='<f4').reshape(6, 512)
        np.testing.assert_array_equal(restored, values)
        self.assertLess(len(wire), 17000)

    def test_board_rejects_wrong_feature_extent_and_identity(self):
        from vision_app.board_agent import Agent
        from vision_app.contract import load_contract
        import threading
        contract = load_contract('vision_app/semantic-contract.json')
        agent = Agent.__new__(Agent)
        agent.contract = contract
        from vision_app.state import Candidates
        agent.queries = Candidates()
        identity = {k: contract[k] for k in ('contract_id', 'weight_sha256', 'normalization', 'bpe_sha256')}
        items = [{'id': 'cup', 'label': '杯子', 'text': 'a cup'}]
        bad = {'op': 'queries', 'items': items, 'identity': identity, 'revision': 1, 'features_f32_b64': base64.b64encode(b'short').decode()}
        with self.assertRaises(ValueError):
            agent.handle(bad)
        values = np.zeros((1, 512), dtype='<f4')
        values[0, 0] = 1
        good = dict(bad, features_f32_b64=base64.b64encode(values.tobytes()).decode())
        self.assertEqual(agent.handle(good)['count'], 1)
        with self.assertRaises(ValueError):
            agent.handle(dict(good, identity=dict(identity, bpe_sha256='0' * 64), revision=2))

    def test_start_during_drain_is_explicitly_rejected(self):
        from vision_app.board_agent import Agent
        import threading
        agent = Agent.__new__(Agent)
        agent.lock = threading.RLock()
        agent.inference_thread = type('DrainingThread', (), {'is_alive': lambda self: True})()
        agent.inference_enabled = False
        agent.inference_state = 'DRAINING'
        with self.assertRaisesRegex(ValueError, 'draining'):
            agent.handle({'op': 'start'})

    def test_unqualified_r5_never_opens_device_memory(self):
        from unittest.mock import patch
        from vision_app.r5_bridge import R5Bridge
        with patch('vision_app.r5_bridge.acquire_owner'), patch('vision_app.r5_bridge.glob.glob', return_value=[]), patch('vision_app.r5_bridge.ctypes.CDLL') as library:
            with self.assertRaisesRegex(RuntimeError, 'not qualified'):
                R5Bridge()
            library.assert_not_called()


    def test_default_cpu_is_1p2ghz_and_r5_validates_first(self):
        from vision_app.board_agent import Agent
        from types import SimpleNamespace
        calls = []
        agent = Agent.__new__(Agent)
        agent.config = {}
        agent.r5 = SimpleNamespace(request=lambda core, opcode, value: calls.append(('r5', core, opcode, value)))
        agent.cpu = SimpleNamespace(set_frequency=lambda value: calls.append(('cpu', value)))
        agent.apply_boot_defaults()
        self.assertEqual(calls, [('r5', 0, 10, 1199999), ('cpu', 1199999)])

    def test_frequency_drains_before_control_and_resumes_after_verification(self):
        agent,calls=self.frequency_agent()
        result=agent.handle({'op':'cpu_frequency','khz':800000})
        self.assertEqual(calls,['drain','r5','cpu','resume'])
        self.assertTrue(result['inference_resumed'])
        self.assertFalse(agent.frequency_changing)

    def test_failed_frequency_does_not_resume_inference(self):
        agent,calls=self.frequency_agent()
        def fail(khz):
            calls.append('cpu')
            raise RuntimeError('hardware verification failed')
        agent.cpu.set_frequency=fail
        with self.assertRaisesRegex(RuntimeError,'verification'):
            agent.handle({'op':'cpu_frequency','khz':800000})
        self.assertEqual(calls,['drain','r5','cpu'])
        self.assertFalse(agent.inference_enabled)
        self.assertFalse(agent.frequency_changing)

    def test_failed_runtime_cleanup_blocks_even_when_thread_has_ended(self):
        agent,calls=self.frequency_agent()
        agent.inference_thread.alive=False
        agent.inference_state='FAILED'
        agent.inference_error='runtime cleanup was not verified'
        with self.assertRaisesRegex(RuntimeError,'cleanup'):
            agent.handle({'op':'cpu_frequency','khz':600000})
        self.assertEqual(calls,[])

    def frequency_agent(self):
        import threading
        from types import SimpleNamespace
        from vision_app.board_agent import Agent
        agent=Agent.__new__(Agent)
        calls=[]
        agent.lock=threading.RLock()
        agent.stop=threading.Event()
        agent.inference_enabled=True
        agent.inference_state='RUNNING'
        agent.inference_error=None
        class Task:
            alive=True
            def is_alive(self):return self.alive
            def join(self,timeout):
                assert not agent.inference_enabled
                calls.append('drain');self.alive=False;agent.inference_state='STOPPED'
        agent.inference_thread=Task()
        agent.r5=SimpleNamespace(request=lambda *args:calls.append('r5'))
        agent.cpu=SimpleNamespace(set_frequency=lambda khz:calls.append('cpu') or {'verified':True})
        agent.spawn=lambda fn:calls.append('resume') or Task()
        return agent,calls


if __name__ == '__main__':
    unittest.main()
