"""UTF-8 English descriptions with stable IDs and Chinese display labels."""
import json
from pathlib import Path


def validate_prompts(prompts):
    if not isinstance(prompts, list) or not prompts:
        raise ValueError("prompts must be a nonempty list")
    seen, result = set(), []
    for item in prompts:
        if not isinstance(item, dict) or set(item) != {"id", "text", "label"}:
            raise ValueError("each prompt requires exactly id, text, label")
        if any(not isinstance(item[k], str) or not item[k].strip() for k in item):
            raise ValueError("prompt strings must be nonempty")
        if item["id"] in seen:
            raise ValueError("duplicate prompt ID")
        if not item["text"].isascii() or not any(c.isalpha() for c in item["text"]):
            raise ValueError("text must be an English ASCII description")
        seen.add(item["id"])
        result.append(dict(item))
    return result


def load_prompts(path):
    return validate_prompts(json.loads(Path(path).read_text(encoding="utf-8")))
