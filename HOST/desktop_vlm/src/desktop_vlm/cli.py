"""Explicit local model/cache/gallery command line for research experiments."""
import argparse
import importlib.metadata
import json
from pathlib import Path
import platform
import sys
from time import perf_counter

from .cache import build_text_cache, load_text_cache, sha256_file
from .gallery import build_gallery, load_gallery, query_gallery
from .matching import cosine_scores, rank_scores
from .model import MobileCLIPEncoder
from .prompts import load_prompts


def doctor():
    packages = {}
    for name in ("numpy", "Pillow", "torch", "torchvision", "timm", "open-clip-torch", "pytest"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    return {"python": platform.python_version(), "executable": sys.executable, "packages": packages, "model_inference": "NOT_RUN", "board": "NOT_RUN", "note": "Package presence is an inventory, not true model validation."}


def parser():
    root = argparse.ArgumentParser(description="MobileCLIP-S1 local research experiment; explicit checkout and weights")
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor")
    for name in ("cache-text", "match", "gallery-build", "gallery-query"):
        cmd = commands.add_parser(name)
        cmd.add_argument("--official-repo", required=True)
        cmd.add_argument("--weights", required=True)
        cmd.add_argument("--model", default="mobileclip_s1", choices=["mobileclip_s1"])
        cmd.add_argument("--device", default="cpu")
        cmd.add_argument("--cpu-threads", type=int, default=4)
        cmd.add_argument("--json", dest="json_output", metavar="PATH", help="save UTF-8 JSON; '-' prints JSON to stdout")
        if name == "cache-text":
            cmd.add_argument("--prompts", required=True)
            cmd.add_argument("--output", required=True)
        elif name == "match":
            cmd.add_argument("--image", required=True)
            cmd.add_argument("--cache", required=True)
            cmd.add_argument("--prompts", help="optionally require this exact prompt order/content")
            cmd.add_argument("--top-k", type=int, default=5)
        elif name == "gallery-build":
            cmd.add_argument("--images", required=True)
            cmd.add_argument("--output", required=True)
        else:
            cmd.add_argument("--image", required=True)
            cmd.add_argument("--gallery", required=True)
            cmd.add_argument("--top-k", type=int, default=5)
            cmd.add_argument("--exclude-same-image", action="store_true")
    return root


def _emit(result, destination=None):
    payload = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)
    if destination and destination != "-":
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload + "\n", encoding="utf-8")
    if destination == "-" or "results" not in result:
        print(payload)
    else:
        print("排名\t标签\tcosine")
        for i, entry in enumerate(result["results"], 1):
            print(f"{i}\t{entry['label']}\t{entry['cosine']:.6f}")
        print(f"backend={result['backend']} elapsed_ms={result['timing_ms']['total']:.3f}")


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "doctor":
            _emit(doctor())
            return 0
        started = perf_counter()
        encoder = MobileCLIPEncoder(official_repo=args.official_repo, weights=args.weights, device=args.device, model_name=args.model, cpu_threads=args.cpu_threads)
        loaded = perf_counter()
        identity = encoder.identity()
        result = {"command": args.command, "backend": identity["backend"], "model": identity, "research_experiment": True, "score_kind": "cosine (not calibrated probability)", "timing_ms": {"model_load": (loaded - started) * 1000}}
        if args.command == "cache-text":
            result["cache_id"] = build_text_cache(encoder, load_prompts(args.prompts), args.output)
        elif args.command == "match":
            cache = load_text_cache(args.cache, identity, load_prompts(args.prompts) if args.prompts else None)
            result["cache_id"] = cache["cache_id"]
            features = encoder.encode_images([args.image])
            scores = cosine_scores(features, cache["features"])[0]
            result["image_sha256"] = sha256_file(args.image)
            result["results"] = [{**cache["prompts"][i], "cosine": float(scores[i])} for i in rank_scores(scores, args.top_k)]
        elif args.command == "gallery-build":
            directory = Path(args.images)
            if not directory.is_dir():
                raise ValueError("gallery images must be an existing directory")
            paths = sorted(p for p in directory.iterdir() if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"})
            result["gallery_id"] = build_gallery(encoder, [{"item_id": p.stem, "label": p.stem, "path": p} for p in paths], args.output)
            result["items"] = len(paths)
        else:
            gallery = load_gallery(args.gallery, identity)
            result["gallery_id"] = gallery["gallery_id"]
            result["image_sha256"] = sha256_file(args.image)
            result["exclude_same_image"] = args.exclude_same_image
            result["results"] = query_gallery(encoder, args.image, gallery, args.top_k, args.exclude_same_image)
        finished = perf_counter()
        result["timing_ms"]["operation"] = (finished - loaded) * 1000
        result["timing_ms"]["total"] = (finished - started) * 1000
        result["timing_scope"] = "single host CLI call; load and operation separate; not warmed P50/P95 or board FPS"
        _emit(result, args.json_output)
        return 0
    except Exception as exc:
        print(f"desktop-vlm error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
