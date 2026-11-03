"""Phase 0 bake-off: run test prompts through several fal.ai pipelines.

Each pipeline turns one item from docs/test_prompts.json into an
equirectangular 2:1 panorama. Results are saved as
web/public/bakeoff/<pipeline>/<id>.jpg plus <id>.json metadata.

Usage:
    python gen/bakeoff.py --pipelines all --ids p001          # one test item
    python gen/bakeoff.py --pipelines flux1_lora,gpt_image2   # all items
    python gen/bakeoff.py --dry-run                           # show plan + cost, no API calls

Reads FAL_KEY from the environment (never from a file in the repo).
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
PROMPTS = ROOT / "docs" / "test_prompts.json"
OUT_DIR = ROOT / "web" / "public" / "bakeoff"
MAX_SIZE = (4096, 2048)
JPEG_QUALITY = 85

# Panorama size requested from text-to-image models (2:1).
PANO_W, PANO_H = 2048, 1024


# ---------------------------------------------------------------------------
# Pipelines
# ---------------------------------------------------------------------------

@dataclass
class Result:
    image_url: str
    calls: list[dict]          # every fal call made: endpoint + arguments
    cost_usd: float            # estimate from fal's published prices
    extra: dict


@dataclass
class Pipeline:
    name: str
    description: str
    est_cost: float            # per item, for --dry-run
    run: Callable[[dict], Result]


def _fal():
    import fal_client  # imported lazily so --dry-run works without a key
    if not os.environ.get("FAL_KEY"):
        sys.exit("FAL_KEY is not set in the environment.")
    return fal_client


def _call(endpoint: str, arguments: dict) -> dict:
    return _fal().subscribe(endpoint, arguments=arguments, with_logs=False)


def _mp(w: int, h: int) -> float:
    return w * h / 1_000_000


# A: FLUX.1 [dev] + equirectangular LoRA (MultiTrickFox v3).
FLUX1_LORA_URL = (
    "https://huggingface.co/MultiTrickFox/Flux-LoRA-Equirectangular-v3/"
    "resolve/main/equirectangular_flux_lora_v3_000003072.safetensors"
)


def run_flux1_lora(item: dict) -> Result:
    endpoint = "fal-ai/flux-lora"
    args = {
        "prompt": "equirectangular 360 degree panorama, " + item["prompt_360"],
        "image_size": {"width": PANO_W, "height": PANO_H},
        "loras": [{"path": FLUX1_LORA_URL, "scale": 1.0}],
        "guidance_scale": 2.5,          # model card: 2.5 for realistic scenes
        "num_inference_steps": 28,
        "seed": item["seed"],
        "output_format": "jpeg",
        "enable_safety_checker": True,
    }
    out = _call(endpoint, args)
    img = out["images"][0]
    # fal may return a smaller image than requested; it bills the actual size.
    w, h = img.get("width") or PANO_W, img.get("height") or PANO_H
    return Result(img["url"], [{"endpoint": endpoint, "arguments": args}],
                  round(_mp(w, h) * 0.035, 4), {"seed": out.get("seed")})


# B: FLUX.2 [klein] 9B + 360 panorama LoRA (crafiq).
KLEIN_LORA = "crafiq/flux-2-klein-9b-360-panorama-lora"


def run_klein_lora(item: dict) -> Result:
    endpoint = "fal-ai/flux-2/klein/9b/lora"
    args = {
        "prompt": "Equirectangular 360 panorama, " + item["prompt_360"],
        "image_size": {"width": PANO_W, "height": PANO_H},
        "loras": [{"path": KLEIN_LORA, "scale": 1.0}],
        "num_inference_steps": 8,       # max for this distilled endpoint
        "seed": item["seed"],
        "output_format": "jpeg",
        "enable_safety_checker": True,
    }
    out = _call(endpoint, args)
    return Result(out["images"][0]["url"], [{"endpoint": endpoint, "arguments": args}],
                  round(_mp(PANO_W, PANO_H) * 0.015, 4), {"seed": out.get("seed")})


# C: GPT Image 2, asked directly for an equirectangular panorama.
def run_gpt_image2(item: dict) -> Result:
    endpoint = "openai/gpt-image-2"
    prompt = (
        item["prompt_360"]
        + " The image must be a single full spherical equirectangular projection: "
        "360 degrees horizontally and 180 degrees vertically, with the left and right "
        "edges joining seamlessly. Straight lines bend as in a real equirectangular "
        "photo. No borders, no text overlays."
    )
    args = {
        "prompt": prompt,
        "image_size": {"width": PANO_W, "height": PANO_H},
        "quality": "medium",
        "output_format": "jpeg",
    }
    out = _call(endpoint, args)
    # Token-priced; medium at ~2 MP is roughly $0.05-0.06. Refined once billed.
    return Result(out["images"][0]["url"], [{"endpoint": endpoint, "arguments": args}],
                  0.06, {})


# D: forward street photo (FLUX.2 klein), then Hunyuan World image-to-panorama.
def run_forward_hunyuan(item: dict) -> Result:
    e1 = "fal-ai/flux-2/klein/9b/lora"
    fw, fh = 1344, 768
    a1 = {
        "prompt": item["prompt_forward"],
        "image_size": {"width": fw, "height": fh},
        "num_inference_steps": 8,
        "seed": item["seed"],
        "output_format": "jpeg",
        "enable_safety_checker": True,
    }
    o1 = _call(e1, a1)
    forward_url = o1["images"][0]["url"]

    e2 = "fal-ai/hunyuan_world"
    a2 = {"image_url": forward_url, "prompt": item["prompt_360"], "enable_safety_checker": True}
    o2 = _call(e2, a2)
    return Result(o2["image"]["url"],
                  [{"endpoint": e1, "arguments": a1}, {"endpoint": e2, "arguments": a2}],
                  round(_mp(fw, fh) * 0.015 + 0.15, 4), {"forward_image_url": forward_url})


PIPELINES = {
    p.name: p for p in [
        Pipeline("flux1_lora", "FLUX.1 [dev] + Equirectangular LoRA v3", 0.073, run_flux1_lora),
        Pipeline("klein_lora", "FLUX.2 [klein] 9B + 360 panorama LoRA", 0.032, run_klein_lora),
        Pipeline("gpt_image2", "GPT Image 2 (medium), prompted for equirectangular", 0.06, run_gpt_image2),
        Pipeline("forward_hunyuan", "FLUX.2 [klein] forward photo -> Hunyuan World panorama", 0.166, run_forward_hunyuan),
    ]
}


# ---------------------------------------------------------------------------
# Post-processing and checks
# ---------------------------------------------------------------------------

def download(url: str) -> Image.Image:
    with urllib.request.urlopen(url, timeout=120) as r:
        return Image.open(io.BytesIO(r.read())).convert("RGB")


def seam_score(img: Image.Image) -> float:
    """Mean absolute difference (0-255) between the left and right edge columns.

    Low (< ~10) suggests the panorama wraps cleanly; high values mean a visible seam.
    """
    w, h = img.size
    left = img.crop((0, 0, 1, h)).tobytes()
    right = img.crop((w - 1, 0, w, h)).tobytes()
    return round(sum(abs(a - b) for a, b in zip(left, right)) / len(left), 2)


def save(pipeline: Pipeline, item: dict, res: Result, img: Image.Image, seconds: float) -> dict:
    raw_size = img.size
    img.thumbnail(MAX_SIZE, Image.LANCZOS)
    folder = OUT_DIR / pipeline.name
    folder.mkdir(parents=True, exist_ok=True)
    img.save(folder / f"{item['id']}.jpg", "JPEG", quality=JPEG_QUALITY, optimize=True)

    meta = {
        "id": item["id"],
        "pipeline": pipeline.name,
        "pipeline_description": pipeline.description,
        "calls": res.calls,
        "prompt": item["prompt_360"],
        "seed": item["seed"],
        "attributes": item["attributes"],
        "cost_estimate_usd": res.cost_usd,
        "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "seconds": round(seconds, 1),
        "raw_size": list(raw_size),
        "saved_size": list(img.size),
        "aspect_ok": abs(raw_size[0] / raw_size[1] - 2.0) < 0.02,
        "seam_score": seam_score(img),
        **res.extra,
    }
    (folder / f"{item['id']}.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n")
    return meta


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pipelines", default="all", help="comma list or 'all'")
    ap.add_argument("--ids", default="all", help="comma list of prompt ids or 'all'")
    ap.add_argument("--skip-existing", action="store_true", help="skip items already generated")
    ap.add_argument("--dry-run", action="store_true", help="print plan and cost estimate only")
    args = ap.parse_args(argv)

    items = json.loads(PROMPTS.read_text())["items"]
    if args.ids != "all":
        wanted = set(args.ids.split(","))
        items = [i for i in items if i["id"] in wanted]
    names = list(PIPELINES) if args.pipelines == "all" else args.pipelines.split(",")
    unknown = [n for n in names if n not in PIPELINES]
    if unknown:
        ap.error(f"unknown pipelines: {unknown}. Choose from {list(PIPELINES)}")

    jobs = [(PIPELINES[n], it) for n in names for it in items
            if not (args.skip_existing and (OUT_DIR / n / f"{it['id']}.jpg").exists())]
    est = sum(p.est_cost for p, _ in jobs)
    print(f"{len(jobs)} job(s), estimated cost ${est:.2f}")
    if args.dry_run:
        for p, it in jobs:
            print(f"  {p.name:16s} {it['id']}  ~${p.est_cost:.3f}")
        return 0

    total, failures = 0.0, []
    for p, it in jobs:
        t0 = time.time()
        try:
            res = p.run(it)
            img = download(res.image_url)
            meta = save(p, it, res, img, time.time() - t0)
            total += res.cost_usd
            print(f"OK   {p.name:16s} {it['id']}  {meta['raw_size'][0]}x{meta['raw_size'][1]}"
                  f"  seam={meta['seam_score']}  ~${res.cost_usd:.3f}  {meta['seconds']}s")
        except Exception as exc:  # keep going; report at the end
            failures.append((p.name, it["id"], repr(exc)[:300]))
            print(f"FAIL {p.name:16s} {it['id']}  {repr(exc)[:300]}")
    print(f"\nEstimated spend this run: ${total:.2f}")
    if failures:
        print(f"{len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
