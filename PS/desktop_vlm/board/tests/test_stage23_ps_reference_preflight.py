import argparse
import json
import sys
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import stage23_ps_reference_preflight as preflight


def test_pipeline_thread_split_and_legacy_default():
    args = argparse.Namespace(threads=4)
    assert preflight._thread_counts(args) == (4, 4)
    args.prefix_threads, args.suffix_threads = 1, 3
    assert preflight._thread_counts(args) == (1, 3)
    args.prefix_threads = 0
    with pytest.raises(ValueError):
        preflight._thread_counts(args)


def test_partial_runner_start_failure_closes_started_client(tmp_path):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (runtime / "manifest.json").write_text(json.dumps({
        "prefix": {"path": "prefix.onnx"},
        "models": {"stage2_suffix": {"path": "s2.onnx"},
                   "stage3_suffix": {"path": "s3.onnx"}},
    }))
    args = argparse.Namespace(
        input=["a", "b", "c"], output_dir=str(tmp_path / "result"),
        runtime_dir=str(runtime), stage2_dir="s2", stage3_dir="s3",
        runner="runner", threads=4, prefix_threads=1, suffix_threads=3)
    started_client = mock.Mock()
    with mock.patch.object(preflight, "Stage23DmaProtocol"), \
         mock.patch.object(preflight, "_sha_file", return_value="a" * 64), \
         mock.patch.object(preflight, "_contract", return_value={}), \
         mock.patch.object(preflight, "OrtPartitionClient", side_effect=[
             started_client, RuntimeError("suffix launch failed")]) as factory:
        with pytest.raises(RuntimeError, match="suffix launch failed"):
            preflight.run(args)
    started_client.close.assert_called_once_with()
    assert factory.call_args_list[0].args[0][-1] == "1"
    assert factory.call_args_list[1].args[0][-1] == "3"
    report = json.loads((tmp_path / "result/result.json").read_text())
    assert report["status"] == "FAILED"
    assert report["threads"]["prefix_intra"] == 1
    assert report["threads"]["suffix_intra"] == 3
    assert report["thresholds"]["feature_max_abs_lte"] == 1e-6
    assert report["dma_opened"] is False
