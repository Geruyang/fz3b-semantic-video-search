"""Add relative-L2 quality metrics to the frozen network0 W16 result."""
import hashlib
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
HOST = ROOT / "artifacts/board-debug-20261005/acceleration/host"
N0 = HOST / "network0-w16-preflight-001"
BASE = HOST / "root-stage0-preflight-001"
OUT = HOST / "network0-w16-quality-addendum-001"


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    if OUT.exists():
        raise FileExistsError(f"refusing to overwrite {OUT}")
    n0m = json.loads((N0 / "manifest.json").read_text(encoding="utf-8"))
    basem = json.loads((BASE / "manifest.json").read_text(encoding="utf-8"))
    base_by_id = {x["sample_id"]: x for x in basem["samples"]}
    rows = []
    for item in n0m["results"]:
        sid = item["sample_id"]
        a = np.fromfile(N0 / item["feature"]["path"], dtype="<f4").astype(np.float64)
        ref_path = BASE / base_by_id[sid]["fp32_feature"]["path"]
        b = np.fromfile(ref_path, dtype="<f4").astype(np.float64)
        d = a - b
        rows.append({"sample_id": sid,
                     "w16_feature_sha256": sha(N0 / item["feature"]["path"]),
                     "pure_fp32_ps_feature_sha256": sha(ref_path),
                     "cosine": float(np.dot(a,b) / (np.linalg.norm(a)*np.linalg.norm(b))),
                     "max_abs": float(np.max(np.abs(d))),
                     "relative_l2": float(np.linalg.norm(d) / np.linalg.norm(b)),
                     "rms_abs": float(np.sqrt(np.mean(d*d))),
                     "ranking": item["ranking"],
                     "pure_fp32_ranking": item["pure_fp32_ranking"],
                     "full_ranking_matches": item["full_ranking_matches_pure_fp32"]})
    OUT.mkdir(parents=True)
    report = {"schema_version": 1, "status": "HOST_NETWORK0_W16_QUALITY_METRIC_ADDENDUM_NOT_PL",
              "network0_manifest_sha256": sha(N0 / "manifest.json"),
              "root_stage0_reference_manifest_sha256": sha(BASE / "manifest.json"),
              "scope": "network0 first four blocks W16 integer, remaining stages FP32; three frozen images",
              "results": rows,
              "checks": {"all_rankings_match": all(x["full_ranking_matches"] for x in rows),
                         "pl_execution": False}}
    path = OUT / "manifest.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"manifest": str(path), "sha256": sha(path), "results": rows}, indent=2))


if __name__ == "__main__":
    main()
