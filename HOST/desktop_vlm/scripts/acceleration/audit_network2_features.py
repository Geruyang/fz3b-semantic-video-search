"""Independently check retained Network2 features; never contact the board."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


ORACLE_SHA = "cd226e0922d7ffb8149ee8cca2eecc877416b52d1dc8d9dec2b02fa658b83522"
PARAMETER_SHA = "5d48cd42136199834ce2e59b00a2d441af7ca5d7cf7515a9c72706de0bad5b62"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(blob):
    return hashlib.sha256(blob).hexdigest()


def read_array(root, record, shape):
    path = (root / record["path"]).resolve()
    require(path.is_relative_to(root.resolve()), "reference escapes oracle directory")
    blob = path.read_bytes()
    require(record["dtype"] == "<f4" and record["shape"] == list(shape),
            "reference dtype/shape mismatch")
    require(len(blob) == record["bytes"] == int(np.prod(shape)) * 4,
            "reference byte count mismatch")
    require(digest(blob) == record["sha256"], "reference SHA mismatch")
    result = np.frombuffer(blob, dtype="<f4").reshape(shape).astype(np.float64)
    require(np.isfinite(result).all(), "reference contains nonfinite values")
    return result


def load_oracle(root):
    root = Path(root)
    blob = (root / "manifest.json").read_bytes()
    require(digest(blob) == ORACLE_SHA, "oracle manifest identity mismatch")
    manifest = json.loads(blob)
    require(manifest["artifact_completeness"] == "FULL_CASCADE"
            and manifest["block_count"] == 12, "oracle scope mismatch")
    references = {}
    for row in manifest["results"]:
        references[row["sample_id"]] = {
            "quantized": read_array(root, row["quantized_feature_file"], (1, 512))[0],
            "pure_ps": read_array(root, row["reference_feature_file"], (1, 512))[0],
        }
    require(set(references) == {"image-00", "image-01", "image-02"}, "oracle sample set")
    text = read_array(root, manifest["text_feature_reference"], (8, 512))
    norms = np.linalg.norm(text, axis=1, keepdims=True)
    require((norms > 0).all(), "zero text embedding")
    return references, text / norms


def metrics(actual, reference):
    denominator = float(np.linalg.norm(actual) * np.linalg.norm(reference))
    require(denominator > 0, "zero feature vector")
    difference = actual - reference
    return {"max_abs": float(np.max(np.abs(difference))),
            "rms_abs": float(np.sqrt(np.mean(difference * difference))),
            "cosine": float(np.dot(actual, reference) / denominator)}


def rank(feature, text):
    # Normalizing image features cannot change this within-image rank.
    return np.argsort(-(text @ feature), kind="stable").astype(int).tolist()


def audit_records(records, references, text):
    require(len(records) == 30, "expected exactly 30 measured feature records")
    checked = []
    for index, record in enumerate(records):
        sample = "image-%02d" % (index % 3)
        require(record["frame_id"] == index and record["sample_id"] == sample,
                "feature frame/sample order mismatch")
        values = record.get("feature_f32")
        require(isinstance(values, list) and len(values) == 512,
                "retained feature_f32 must be a flat 512-value list")
        require(all(isinstance(value, (int, float)) and not isinstance(value, bool)
                    for value in values), "feature values must be numbers")
        actual32 = np.asarray(values, dtype="<f4")
        require(np.isfinite(actual32).all(), "retained feature is nonfinite")
        require(digest(actual32.tobytes()) == record["feature_sha256"],
                "retained feature SHA mismatch")
        actual = actual32.astype(np.float64)
        reference = references[sample]
        quant = metrics(actual, reference["quantized"])
        require(quant["max_abs"] <= 1e-6 and quant["cosine"] >= .99999,
                "feature differs from quantized oracle")
        actual_rank = rank(actual, text)
        require(actual_rank == rank(reference["quantized"], text),
                "feature rank differs from quantized oracle")
        checked.append({"frame_id": index, "sample_id": sample,
                        "vs_quantized": quant,
                        "vs_pure_ps": metrics(actual, reference["pure_ps"]),
                        "rank_indices": actual_rank,
                        "pure_ps_rank_matches": actual_rank == rank(reference["pure_ps"], text)})
    return checked


def audit_board_report(report, references, text):
    require(report.get("execution") == "board" and report.get("pl_execution") is True,
            "requires real board report; host contract data cannot pass this entry")
    require(report.get("status") == "PASS" and report.get("compare_eligible") is True,
            "requires successful compare-eligible report")
    require(report["validation"]["parameter_manifest_sha256"] == PARAMETER_SHA,
            "parameter identity mismatch")
    checked = audit_records(report["records"], references, text)
    return {"status": "PASS_INDEPENDENT_RETAINED_FEATURE_AUDIT", "frames": len(checked),
            "oracle_manifest_sha256": ORACLE_SHA, "records": checked,
            "scope": "Recomputes saved float32 feature SHA, numerical error and eight-way rank independently of runtime validation. This is not a DMA/timing audit, proof of report provenance, or independent recognition-accuracy dataset."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("oracle_dir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    blob = args.report.read_bytes()
    references, text = load_oracle(args.oracle_dir)
    result = audit_board_report(json.loads(blob), references, text)
    result["report_sha256"] = digest(blob)
    result["checker_sha256"] = digest(Path(__file__).read_bytes())
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "records"}))


if __name__ == "__main__":
    main()
