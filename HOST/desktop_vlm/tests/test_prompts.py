from pathlib import Path
import pytest
from desktop_vlm.prompts import load_prompts, validate_prompts


def test_default_desktop_classes():
    data = load_prompts(Path(__file__).parents[1] / "configs" / "prompts.en-zh.json")
    assert [p["label"] for p in data] == ["杯子", "遥控器", "螺丝刀", "钳子", "食品包装", "瓶子", "键盘", "手机"]
    assert len({p["id"] for p in data}) == 8


def test_order_duplicate_and_missing(prompts):
    assert validate_prompts(prompts) == prompts
    with pytest.raises(ValueError):
        validate_prompts([prompts[0], prompts[0]])
    with pytest.raises(ValueError):
        validate_prompts([{"id": "x", "text": "", "label": "空"}])
    with pytest.raises(ValueError):
        validate_prompts([{"id": "x", "text": "中文", "label": "杯子"}])
