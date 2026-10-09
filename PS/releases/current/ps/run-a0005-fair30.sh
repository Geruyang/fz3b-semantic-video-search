#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
OUT=${1:-"$ROOT/results/fair30-$(date -u +%Y%m%dT%H%M%SZ)"}
export LD_LIBRARY_PATH="$ROOT/runtime-libs/onnxruntime-linux-aarch64-1.16.3/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$ROOT/runtime-current:$ROOT/runtime-compat"
export ORT_PARTITION_ALLOW_SPINNING=0
export ORT_PARTITION_PREALLOC_OUTPUTS=0

exec python3 -B "$ROOT/runtime-current/benchmark_cnn_pipeline_v10_live.py" \
  --bundle-root "$ROOT/release" \
  --expected-bundle-sha256 3f52238b2a35d23f6f07c4cc9263ff8d4330c5aa27a6ed91640c4a45a8d45a2d \
  --deployment-manifest "$ROOT/deployment/manifest.json" \
  --expected-deployment-sha256 6e01472fae50fcab672bf8a6097648630618b8b304c860f0703472cd6ec1d2f3 \
  --runner "$ROOT/bin/ort_partition_runner_v3" \
  --ps-client mixed \
  --native-lib "$ROOT/bin/libcnn_v10_native_quant.so" \
  --pl-chain-manifest "$ROOT/deployment/files/manifest.json" \
  --expected-pl-chain-manifest-sha256 4a32c9373e783ac572a5d3374b316181a4d52ae9a92ec45f8b13d763ef028690 \
  --pl-chain-runtime a0005 \
  --ps-schedule split \
  --threads 3 \
  --ps-front-threads 1 \
  --ps-suffix-threads 3 \
  --max-in-flight 4 \
  --warmup-pairs 3 \
  --measured-pairs 30 \
  --timeout-s 300 \
  --device /dev/network10_v10_signed40 \
  --input-tensor "$ROOT/inputs/image-00-input.f32" \
  --input-tensor "$ROOT/inputs/image-01-input.f32" \
  --expected-feature-sha256 4121608b7bb27060d5babe05dd6ae723d191b4405a0852d55adde876f4ef16b3 \
  --expected-feature-sha256 7654afe2d025731f18d23268c2109aba3445b2708a8e9ef1a2e49ed84c369adb \
  --reference-feature "$ROOT/references/image-00-feature.f32" \
  --reference-feature "$ROOT/references/image-01-feature.f32" \
  --suffix-candidate "$ROOT/suffix11-selection/selection-manifest.json" \
  --output-dir "$OUT"

