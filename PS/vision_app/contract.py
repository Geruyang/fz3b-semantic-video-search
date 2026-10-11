"""Bind preserved source/text space and the effective A0005 image backend."""
import hashlib
import json
import os


def sha_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for part in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(part)
    return h.hexdigest()


def load_contract(path):
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    identity = dict(data)
    expected = identity.pop('contract_id')
    actual = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
    if expected != actual or data['dimension'] != 512 or data['model'] != 'mobileclip_s1':
        raise ValueError('semantic contract invalid')
    return data


def verify_source(contract, model_root):
    for relative, expected in contract['source_files'].items():
        target = os.path.abspath(os.path.join(model_root, relative))
        if os.path.commonpath([target, os.path.abspath(model_root)]) != os.path.abspath(model_root) or sha_file(target) != expected:
            raise ValueError('preserved official source differs: ' + relative)
    if sha_file(os.path.join(model_root, 'mobileclip_s1.pt')) != contract['weight_sha256']:
        raise ValueError('S1 weight SHA mismatch')


def generate(project_root, target):
    """Recheck the final packaged model assets and unchanged PS numerical contract."""
    import open_clip.tokenizer as tokenizer_module
    root = os.path.abspath(project_root)
    model_root = os.path.join(root, 'deliverables', 'vision-console', 'FZ3BVisionConsole', 'models')
    recorded = load_contract(os.path.join(root, 'releases', 'final', 'HOST', 'vision_app', 'semantic-contract.json'))
    verify_source(recorded, model_root)
    ps = os.path.join(root, 'releases', 'final', 'resources', 'ps')
    contract = dict(recorded)
    contract.pop('contract_id')
    contract.update(weight_sha256=sha_file(os.path.join(model_root, 'mobileclip_s1.pt')),
                    source_files={path: sha_file(os.path.join(model_root, path)) for path in recorded['source_files']},
                    combined_manifest_sha256=sha_file(os.path.join(ps, 'contracts', 'files', 'manifest.json')),
                    bundle_sha256=sha_file(os.path.join(ps, 'release', 'manifest.json')),
                    deployment_sha256=sha_file(os.path.join(ps, 'contracts', 'ps-model-contract.json')),
                    suffix_selection_sha256=sha_file(os.path.join(ps, 'suffix11-selection', 'selection-manifest.json')),
                    bpe_sha256=sha_file(tokenizer_module.default_bpe()))
    contract['contract_id'] = hashlib.sha256(json.dumps(contract, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
    with open(target, 'w', encoding='utf-8') as stream:
        json.dump(contract, stream, ensure_ascii=False, indent=2)
    return contract
