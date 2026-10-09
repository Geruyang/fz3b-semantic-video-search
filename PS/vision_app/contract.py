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
    import open_clip.tokenizer as tokenizer_module
    root = os.path.join(project_root, 'releases', 'current')
    source = json.load(open(os.path.join(root, 'model-source', 'preservation-manifest.json'), encoding='utf-8'))
    files = {}
    weight = None
    for item in source['files']:
        path = item['path'].replace('\\', '/')
        if path == 'model-source/mobileclip_s1.pt':
            weight = item['sha256']
        if path.startswith('model-source/official-mobileclip/mobileclip/') and path.endswith(('.py', '.json')):
            files[path[len('model-source/'):]] = item['sha256']
    ps = os.path.join(root, 'ps')
    contract = {'schema': 1, 'model': 'mobileclip_s1', 'dimension': 512, 'weight_sha256': weight,
                'source_revision': source['upstream_mobileclip_commit'], 'source_files': files,
                'image_backend': 'A0005/direct_wc/split/suffix11',
                'combined_manifest_sha256': sha_file(os.path.join(ps, 'deployment', 'files', 'manifest.json')),
                'bundle_sha256': sha_file(os.path.join(ps, 'release', 'manifest.json')),
                'deployment_sha256': sha_file(os.path.join(ps, 'deployment', 'manifest.json')),
                'suffix_selection_sha256': sha_file(os.path.join(ps, 'suffix11-selection', 'selection-manifest.json')),
                'bpe_sha256': sha_file(tokenizer_module.default_bpe()),
                'preprocess': {'rgb': True, 'resize_short_side': 256, 'crop': [256, 256], 'bilinear': True, 'scale': 'float32/255', 'mean': None, 'std': None},
                'normalization': 'l2-float32-v1'}
    contract['contract_id'] = hashlib.sha256(json.dumps(contract, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
    with open(target, 'w', encoding='utf-8') as f:
        json.dump(contract, f, ensure_ascii=False, indent=2)
    return contract
