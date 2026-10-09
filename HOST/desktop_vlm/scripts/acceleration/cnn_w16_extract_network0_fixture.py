"""Extract network0/profile2/block0 real FP32-source W16 kernel fixture."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HOST = ROOT / "artifacts/board-debug-20261005/acceleration/host"
N0 = HOST / "network0-w16-preflight-001"
BASE = HOST / "root-stage0-preflight-001"
OUT = HOST / "network0-w16-profile2-block0-fixture-001"


def sha(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda:f.read(1<<20),b""): h.update(chunk)
    return h.hexdigest()


def copy_meta(src, root, rel, shape, dtype="<i2"):
    raw=Path(src).read_bytes()
    dst=root/rel; dst.parent.mkdir(parents=True,exist_ok=True); dst.write_bytes(raw)
    return {"path":rel,"dtype":dtype,"shape":list(shape),"bytes":len(raw),"sha256":sha(dst)}


def main():
    if OUT.exists(): raise FileExistsError(str(OUT))
    nm=json.loads((N0/"manifest.json").read_text())
    bm=json.loads((BASE/"manifest.json").read_text())
    sm=json.loads((BASE/"manifest.json").read_text())
    sample=next(x for x in nm["results"] if x["sample_id"]=="image-00")
    params_src=N0/nm["params"]["blocks"][0]["path"]
    input_src=N0/sample["profile2_input_hcw"]["path"]
    expected_src=N0/sample["blocks"][0]["output_hcw"]["path"]
    OUT.mkdir(parents=True)
    param=copy_meta(params_src,OUT,"params-profile2-block0.bin",[195088],"|u1")
    inp=copy_meta(input_src,OUT,"image-00/input-hcw.i16le",[64,64,64])
    out=copy_meta(expected_src,OUT,"image-00/expected-add-hcw.i16le",[64,64,64])
    scales=bm["parameters"][0]["scales"]
    report={"schema_version":1,"status":"HOST_REAL_FP32_SOURCE_W16_PROFILE2_BLOCK0_NOT_PL",
      "abi":{"magic":"FZV5","version":0x00050000,"flags":0},
      "profile":2,"block_index":0,"block_count":1,
      "source":{"network0_w16_manifest_sha256":sha(N0/"manifest.json"),
        "model_sha256":nm["source"]["model_sha256"],
        "network0_input_provenance":"stem/stage0 FP32 trace quantized with frozen HOST network0 input scale",
        "weight_source":"FP32 source ONNX per-output symmetric INT16 quantization",
        "sample_id":"image-00"},
      "parameter_file":{"path":param["path"],"bytes":param["bytes"],"sha256":param["sha256"],
        "stride_bytes":195088,"parameter_words_128b":12193},
      "activation_layout":{"dtype":"<i2","serialization":"HCW","slots":2,"slot_bytes":524288,
        "input":inp,"expected_output":out},
      "calibration_scales":scales,
      "claims":{"host_only":True,"pl_execution":False,"valid_for_bit_exact_kernel_check":True,
        "quality":"single block fixture only; use network0 W16 preflight for 4-block quality"}}
    report["files"]={p.relative_to(OUT).as_posix():{"bytes":p.stat().st_size,"sha256":sha(p)}
      for p in sorted(OUT.rglob("*")) if p.is_file() and p.name!="manifest.json"}
    mf=OUT/"manifest.json";mf.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"manifest":str(mf),"manifest_sha256":sha(mf),
      "params":str(OUT/param["path"]),"params_sha256":param["sha256"],"params_bytes":param["bytes"],
      "input":str(OUT/inp["path"]),"input_sha256":inp["sha256"],"input_bytes":inp["bytes"],
      "expected":str(OUT/out["path"]),"expected_sha256":out["sha256"],"expected_bytes":out["bytes"],
      "parameter_words_128b":12193},indent=2))


if __name__=="__main__":main()
