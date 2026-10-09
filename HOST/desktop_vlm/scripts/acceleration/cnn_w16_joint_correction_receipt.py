"""Freeze corrections to labels/provenance in immutable W16 joint manifest 001."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HOST = ROOT / "artifacts/board-debug-20261005/acceleration/host"
JOINT = HOST / "network-w16-joint-oracle-001"
N2 = HOST / "network2-int-oracle-board-ps-001"
V4 = HOST / "v4-joint-feature-preflight-001"
N0 = HOST / "network0-w16-preflight-001"
OUT = HOST / "network-w16-joint-correction-001"


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    if OUT.exists():
        raise FileExistsError(f"refusing to overwrite {OUT}")
    jm = json.loads((JOINT / "manifest.json").read_text(encoding="utf-8"))
    n2m = json.loads((N2 / "manifest.json").read_text(encoding="utf-8"))
    v4m = json.loads((V4 / "manifest.json").read_text(encoding="utf-8"))
    n0m = json.loads((N0 / "manifest.json").read_text(encoding="utf-8"))
    old = {x["sample_id"]: x for x in v4m["samples"]}
    n2r = {x["sample_id"]: x for x in n2m["results"]}
    rows = []
    for item in jm["results"]:
        sid = item["sample_id"]
        old_rank = old[sid]["ranking"]["joint_int"]
        legacy_rank = n2r[sid]["reference_ranking"]
        rows.append({"sample_id": sid,
                     "w16_ranking": item["ranking"],
                     "pure_ps_ranking": item["pure_ps_ranking"],
                     "legacy_n2_board_ps_suffix_reference_ranking": legacy_rank,
                     "actual_v4_joint_int_ranking_from_v4_preflight_001": old_rank,
                     "w16_matches_pure_ps": item["ranking_matches_pure_ps"],
                     "w16_matches_legacy_n2_reference": item["ranking"] == legacy_rank,
                     "w16_matches_actual_v4_joint_int": item["ranking"] == old_rank,
                     "v4_old_matches_pure_ps": old[sid]["ranking"]["joint_full_order_matches_pure_ps"]})
    report = {
        "schema_version": 1,
        "status": "HOST_W16_JOINT_LABEL_CORRECTION_RECEIPT_NOT_PL",
        "immutable_sources": {"w16_joint_manifest_sha256": sha(JOINT / "manifest.json"),
                               "n2_oracle_manifest_sha256": sha(N2 / "manifest.json"),
                               "v4_joint_preflight_manifest_sha256": sha(V4 / "manifest.json"),
                               "network0_w16_manifest_sha256": sha(N0 / "manifest.json")},
        "correction": {
            "joint001_erroneous_fields": ["results[].v4_joint_reference_ranking",
                                          "results[].ranking_matches_v4_joint_reference"],
            "actual_field_source": "The implementation compares against network2-int-oracle-board-ps-001/results[].reference_ranking, which is marked suffix_reference_kind=SAME_RUN_BOARD_PS_SUFFIX_FEATURE; this is the legacy N2 board-PS suffix reference, not the v4 full joint INT reference.",
            "correct_source_manifest_sha256": sha(V4 / "manifest.json"),
            "actual_v4_ranking_field": "samples[].ranking.joint_int",
            "corrected_rows": rows,
            "interpretation": "The real full W16 joint artifact matches pure FP32 PS rankings on all three images. It differs from the actual former v4 full joint INT image-02 ranking, as expected from the precision change. No claim of matching the v4 INT reference is made by this receipt.",
        },
        "profile2_correction": {
            "old_joint001_label": "LAYOUT_ONLY_NO_MATCHING_MOBILECLIP_STAGE_IN_THIS_JOINT_CHAIN",
            "correct_role": "network0 four-block chain (C64, W64, 4 blocks)",
            "evidence": "The frozen root-stage0-preflight-001 graph describes network0 blocks 0..3 with matching C64x64x64 boundaries.",
            "separate_real_w16_evaluation": "network0-w16-preflight-001",
            "network0_manifest_sha256": sha(N0 / "manifest.json"),
            "network0_status": n0m["status"],
        },
        "files": {},
    }
    OUT.mkdir(parents=True)
    path = OUT / "manifest.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"manifest": str(path), "sha256": sha(path), "correction_rows": rows}, indent=2))


if __name__ == "__main__":
    main()
