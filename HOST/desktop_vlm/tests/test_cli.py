import json
from desktop_vlm import cli


def test_doctor_does_not_claim_model(capsys):
    assert cli.main(["doctor"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["model_inference"] == "NOT_RUN"


def test_missing_model_fails_nonzero(tmp_path, capsys):
    assert cli.main(["match", "--official-repo", str(tmp_path), "--weights", str(tmp_path / "no.pt"), "--image", "no.jpg", "--cache", "no.npz"]) == 2
    assert "error" in capsys.readouterr().err


def test_explicit_synthetic_cli_contract(tmp_path, encoder, prompts, monkeypatch, capsys):
    # This mock is confined to contract tests. It is never a runtime fallback.
    monkeypatch.setattr(cli, "MobileCLIPEncoder", lambda **_: encoder)
    prompt_path = tmp_path / "prompts.json"
    prompt_path.write_text(json.dumps(prompts, ensure_ascii=False), encoding="utf-8")
    image = tmp_path / "cup.jpg"
    image.write_bytes(b"synthetic-test-input")
    common = ["--official-repo", "fixture", "--weights", "fixture"]
    cache = tmp_path / "cache.npz"
    assert cli.main(["cache-text", *common, "--prompts", str(prompt_path), "--output", str(cache)]) == 0
    capsys.readouterr()
    output = tmp_path / "result.json"
    assert cli.main(["match", *common, "--image", str(image), "--cache", str(cache), "--json", str(output)]) == 0
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["backend"] == "synthetic-test-only"
    assert result["results"][0]["label"] == "杯子"
    assert result["results"][0]["cosine"] == 1
    assert all(v >= 0 for v in result["timing_ms"].values())
