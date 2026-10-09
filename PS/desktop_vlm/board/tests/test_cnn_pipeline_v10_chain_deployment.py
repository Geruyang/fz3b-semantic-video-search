import copy
import json
import pathlib
import tempfile
import unittest

from desktop_vlm.board.cnn_pipeline_v10_deployment import load_v10_platform_deployment
from desktop_vlm.board.cnn_pipeline_v10_chain_deployment import (
    SCHEMA, IDENTITY, TARGET, CHAIN_CONTRACT, EXTRA_GATES, load_v10_chain_deployment)
from desktop_vlm.board.tests.test_cnn_pipeline_v10_deployment import (
    V10PlatformDeploymentTests, sha)


class ChainDeploymentTests(unittest.TestCase):
    def package(self, root):
        path, unused, release = V10PlatformDeploymentTests()._package(root)
        manifest = json.loads(path.read_text())
        raw = b'{"test_fixture": "combined chain parameter manifest"}\n'
        (root/'p3.json').write_bytes(raw)
        p3_sha = sha(raw)
        manifest.update(schema=SCHEMA, identity=IDENTITY, target=TARGET,
                        chain_contract=copy.deepcopy(CHAIN_CONTRACT),
                        chain_parameter_manifest_sha256=p3_sha)
        manifest['files']['chain_parameter_manifest'] = {
            'path': 'p3.json', 'bytes': len(raw), 'sha256': p3_sha}
        manifest['gates'].update({key: True for key in EXTRA_GATES})
        return path, release, p3_sha, manifest

    @staticmethod
    def save(path, manifest):
        raw = json.dumps(manifest, sort_keys=True).encode('utf-8')
        path.write_bytes(raw)
        return sha(raw)

    def test_new_abi_requires_explicit_loader_and_parameter_binding(self):
        with tempfile.TemporaryDirectory() as folder:
            path, release, p3_sha, manifest = self.package(pathlib.Path(folder))
            digest = self.save(path, manifest)
            loaded = load_v10_chain_deployment(path, digest, release, p3_sha)
            self.assertEqual(loaded['manifest']['identity']['core_abi'], '0x000A0002')
            with self.assertRaisesRegex(ValueError, 'identity'):
                load_v10_platform_deployment(path, digest, release)
            with self.assertRaisesRegex(ValueError, 'binding'):
                load_v10_chain_deployment(path, digest, release, '0'*64)
            (path.parent/'p3.json').write_bytes(b'changed parameters')
            with self.assertRaisesRegex(ValueError, 'extent or SHA'):
                load_v10_chain_deployment(path, digest, release, p3_sha)

    def test_wrong_layout_identity_target_or_missing_gate_rejected(self):
        edits = (
            lambda m: m['chain_contract']['p3'].update(output_offset_words=32768),
            lambda m: m['chain_contract']['p3'].update(blocks=True),
            lambda m: m['identity'].update(core_abi='0x000A0001'),
            lambda m: m['target'].update(device='/dev/network10_v10'),
            lambda m: m['gates'].update(p3_rtl_integer_exact=False),
        )
        for edit in edits:
            with self.subTest(edit=edit), tempfile.TemporaryDirectory() as folder:
                path, release, p3_sha, source = self.package(pathlib.Path(folder))
                manifest = copy.deepcopy(source)
                edit(manifest)
                digest = self.save(path, manifest)
                with self.assertRaises(ValueError):
                    load_v10_chain_deployment(path, digest, release, p3_sha)


if __name__ == '__main__':
    unittest.main()
