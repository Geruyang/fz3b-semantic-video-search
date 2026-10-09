"""Host-only official S1 encoder, with preserved source verification."""
import importlib
import os
import sys
import numpy as np
from .contract import verify_source
from .state import normalized

PRESETS = [
    ('杯子', 'a photo of a cup'), ('瓶子', 'a photo of a bottle'),
    ('手机', 'a photo of a mobile phone'), ('键盘', 'a photo of a keyboard'),
    ('遥控器', 'a photo of a remote control'), ('螺丝刀', 'a photo of a screwdriver'),
    ('钳子', 'a photo of pliers'), ('食品包装', 'a photo of packaged food'),
    ('桌面', 'a photo of a desk with objects'), ('厨房', 'a photo of a kitchen'),
    ('办公室', 'a photo of an office'), ('房间', 'a photo of an indoor room'),
    ('卧室', 'a photo of a bedroom'),
    ('街道', 'a photo of a street'), ('植物', 'a photo of a plant'),
    ('人', 'a photo of a person'), ('猫', 'a photo of a cat'), ('狗', 'a photo of a dog'),
]


def parse_prompts(text,allow_chinese=False):
    rows = [r.strip() for r in text.splitlines() if r.strip()]
    if not 0 < len(rows) <= 256:
        raise ValueError('请输入 1–256 行描述')
    mapping = dict(PRESETS)
    items = []
    for index, row in enumerate(rows):
        label, prompt = (row.split('|', 1) if '|' in row else (row, mapping.get(row, row)))
        label, prompt = label.strip(), prompt.strip()
        if not label or not prompt or len(label) > 1000 or len(prompt) > 1000:
            raise ValueError('标签/描述不能为空，单条最多 1000 字符')
        if not allow_chinese and any('\u4e00' <= c <= '\u9fff' for c in prompt):
            raise ValueError('该 S1 的中文描述未验证，请用“中文标签 | English description”；常见物品可直接输入中文名称')
        items.append({'id': str(index), 'label': label, 'text': prompt})
    return items


class TextEncoder:
    def __init__(self, contract, model_root):
        model_root = os.path.abspath(model_root)
        verify_source(contract, model_root)
        repo = os.path.join(model_root, 'official-mobileclip')
        sys.path.insert(0, repo)
        import torch
        import open_clip.tokenizer as tokenizer_module
        official = importlib.import_module('mobileclip')
        if os.path.abspath(official.__file__) != os.path.join(repo, 'mobileclip', '__init__.py'):
            raise ValueError('another MobileCLIP checkout is imported')
        torch.set_num_threads(4)
        model, _, _ = official.create_model_and_transforms('mobileclip_s1', pretrained=None, reparameterize=False, device='cpu')
        state = torch.load(os.path.join(model_root, 'mobileclip_s1.pt'), map_location='cpu', weights_only=True)
        model.load_state_dict(state, strict=True)
        del state
        # Use exactly the existing official model path; do not modify/retrain weights.
        self.model = official.reparameterize_model(model).eval()
        self.tokenizer = official.get_tokenizer('mobileclip_s1')
        self.torch = torch
        self.identity = {'contract_id': contract['contract_id'], 'weight_sha256': contract['weight_sha256'], 'source_revision': contract['source_revision'], 'normalization': contract['normalization'], 'tokenizer_context': 77}
        from .contract import sha_file
        self.identity['bpe_sha256'] = sha_file(tokenizer_module.default_bpe())
        if self.identity['bpe_sha256'] != contract['bpe_sha256']:
            raise ValueError('tokenizer BPE differs from semantic contract')

    def encode(self, items):
        with self.torch.inference_mode():
            values = self.model.encode_text(self.tokenizer([i.get('translated_text',i['text']) for i in items])).detach().cpu().float().numpy()
        return normalized(values), dict(self.identity)
