import hashlib
import importlib.util
import json
import pathlib
import tempfile
import unittest


REPO = pathlib.Path(__file__).resolve().parents[3]
BUILDER = REPO / 'desktop_vlm/scripts/acceleration/build_cnn_v10_p3_deployment.py'
EXPECTED_DEBUG_PROFILE = {
    'debug_profile': 'release-guard-only',
    'guard_ila_count': 1,
    'pipeline_ila_count': 0,
    'trace_pack_present': False,
    'mmio_trace_count': 12,
}


def _load_builder():
    spec = importlib.util.spec_from_file_location('p3_deployment_builder_test', str(BUILDER))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class P3DeploymentDebugProfileTest(unittest.TestCase):
    def setUp(self):
        self.builder = _load_builder()
        self.temp = tempfile.TemporaryDirectory(dir=str(REPO))
        self.root = pathlib.Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def _record(self, receipt):
        path = self.root / 'full-platform.json'
        raw = (json.dumps(receipt, sort_keys=True) + '\n').encode('utf-8')
        path.write_bytes(raw)
        return {
            'source_path': path.relative_to(REPO).as_posix(),
            'package_path': 'receipts/full-platform.json',
            'sha256': hashlib.sha256(raw).hexdigest(),
        }

    def test_frozen_debug_profile_contract(self):
        self.assertEqual(getattr(self.builder, 'DEBUG_PROFILE', None),
                         EXPECTED_DEBUG_PROFILE)

    def test_accepts_exact_profile_bound_by_build_receipt(self):
        validator = getattr(self.builder, '_validate_debug_profile_binding', None)
        self.assertTrue(callable(validator))
        receipt = dict(EXPECTED_DEBUG_PROFILE)
        receipt['pass'] = True
        record = self._record(receipt)
        validator(EXPECTED_DEBUG_PROFILE, record)

    def test_rejects_missing_build_receipt_fields(self):
        validator = getattr(self.builder, '_validate_debug_profile_binding', None)
        self.assertTrue(callable(validator))
        receipt = {'debug_profile': 'release-guard-only'}
        with self.assertRaisesRegex(ValueError, 'final build receipt debug profile mismatch'):
            validator(EXPECTED_DEBUG_PROFILE, self._record(receipt))

    def test_rejects_conflicting_build_receipt_fields(self):
        validator = getattr(self.builder, '_validate_debug_profile_binding', None)
        self.assertTrue(callable(validator))
        receipt = dict(EXPECTED_DEBUG_PROFILE)
        receipt['pipeline_ila_count'] = 1
        with self.assertRaisesRegex(ValueError, 'final build receipt debug profile mismatch'):
            validator(EXPECTED_DEBUG_PROFILE, self._record(receipt))

    def test_rejects_spec_profile_different_from_frozen_contract(self):
        validator = getattr(self.builder, '_validate_debug_profile_binding', None)
        self.assertTrue(callable(validator))
        wrong = dict(EXPECTED_DEBUG_PROFILE)
        wrong['trace_pack_present'] = True
        with self.assertRaisesRegex(ValueError, 'deployment debug profile mismatch'):
            validator(wrong, self._record(EXPECTED_DEBUG_PROFILE))


if __name__ == '__main__':
    unittest.main()
