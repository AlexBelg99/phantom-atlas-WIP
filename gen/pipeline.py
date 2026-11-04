"""Production pipeline: one random prompt -> one finished 360° panorama.

Chosen in the Phase 0 bake-off (see docs/decisions.md):
  1. GPT Image 2 (high) at 3840x1920, the model's largest 2:1 size
  2. SeedVR 2x upscale to 7680x3840, with wrap padding so the left/right seam stays clean
  3. Save as JPEG (quality 92) plus a metadata JSON

Used by the local app (app/server.py). Can also be run directly:
    python gen/pipeline.py              # generate one random place into gallery/
    python gen/pipeline.py --fake       # no API calls; reuses a bake-off image (for testing)
"""

from __future__ import annotations

import argparse
import io
import json
import os
import random
import tempfile
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from PIL import Image

import prompt_gen

ROOT = Path(__file__).resolve().parent.parent
GALLERY = ROOT / "gallery"

GEN_ENDPOINT = "openai/gpt-image-2"
UPSCALE_ENDPOINT = "fal-ai/seedvr/upscale/image"
GEN_SIZE = (3840, 1920)
WRAP_PAD = 128                 # pixels copied from the opposite edge before upscaling
JPEG_QUALITY = 92

# Cost estimates in USD (fal bills GPT Image 2 by tokens, so these are approximate).
GEN_COST = {"high": 0.88, "medium": 0.22}
UPSCALE_COST = 0.03

PROMPT_SUFFIX = (
    " The image must be a single full spherical equirectangular projection: 360 degrees "
    "horizontally and 180 degrees vertically, with the left and right edges joining "
    "seamlessly. Straight lines bend as in a real equirectangular photo. "
    "No borders, no text overlays."
)

Progress = Callable[[str], None]


def load_env_file() -> None:
    """Read FAL_KEY (and other settings) from a .env file if not already set."""
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and v and k not in os.environ:
            os.environ[k] = v


def has_key() -> bool:
    k = os.environ.get("FAL_KEY", "")
    return bool(k) and "your-fal-api-key" not in k


def estimated_cost(quality: str) -> float:
    return round(GEN_COST[quality] + UPSCALE_COST, 2)


def random_prompt(weird: float = 0.3) -> dict:
    seed = random.randrange(2**31)
    item = prompt_gen.generate(1, seed, weird, stratify=False)[0]
    item["master_seed"] = seed
    return item


def _download(url: str) -> Image.Image:
    with urllib.request.urlopen(url, timeout=300) as r:
        return Image.open(io.BytesIO(r.read())).convert("RGB")


def _wrap_pad(img: Image.Image, pad: int) -> Image.Image:
    w, h = img.size
    out = Image.new("RGB", (w + 2 * pad, h))
    out.paste(img.crop((w - pad, 0, w, h)), (0, 0))
    out.paste(img, (pad, 0))
    out.paste(img.crop((0, 0, pad, h)), (w + pad, 0))
    return out


def seam_score(img: Image.Image) -> float:
    w, h = img.size
    left = img.crop((0, 0, 1, h)).tobytes()
    right = img.crop((w - 1, 0, w, h)).tobytes()
    return round(sum(abs(a - b) for a, b in zip(left, right)) / len(left), 2)


def generate_place(quality: str = "high", weird: float = 0.3, fake: bool = False,
                   progress: Progress = lambda s: None,
                   on_prompt: Callable[[dict], None] = lambda item: None) -> dict:
    """Generate one place into gallery/ and return its metadata."""
    item = random_prompt(weird)
    on_prompt(item)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    place_id = f"{stamp}-{item['seed'] % 100000:05d}"
    GALLERY.mkdir(exist_ok=True)
    t0 = time.time()
    calls = []

    if fake:
        progress("Test mode: reusing a bake-off image (no API calls)")
        src = sorted((ROOT / "web" / "public" / "bakeoff" / "gpt_image2_high").glob("*.jpg"))
        final = Image.open(random.choice(src)).convert("RGB")
        time.sleep(2)
        cost = 0.0
    else:
        import fal_client
        if not has_key():
            raise RuntimeError("No fal.ai API key found. Put FAL_KEY=... in the .env file.")

        progress("Painting the panorama (about 1–2 minutes)")
        args = {"prompt": item["prompt_360"] + PROMPT_SUFFIX,
                "image_size": {"width": GEN_SIZE[0], "height": GEN_SIZE[1]},
                "quality": quality, "output_format": "png"}
        out = fal_client.subscribe(GEN_ENDPOINT, arguments=args)
        calls.append({"endpoint": GEN_ENDPOINT, "arguments": args})
        base = _download(out["images"][0]["url"])

        progress("Sharpening (upscaling to 7680×3840)")
        padded = _wrap_pad(base, WRAP_PAD)
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "padded.png"
            padded.save(p)
            url = fal_client.upload_file(str(p))
        up_args = {"upscale_mode": "factor", "upscale_factor": 2, "output_format": "png"}
        up = fal_client.subscribe(UPSCALE_ENDPOINT, arguments={"image_url": url, **up_args})
        calls.append({"endpoint": UPSCALE_ENDPOINT, "arguments": up_args})
        big = _download((up.get("image") or up["images"][0])["url"])
        f = big.size[0] / padded.size[0]
        final = big.crop((round(WRAP_PAD * f), 0, big.size[0] - round(WRAP_PAD * f), big.size[1]))
        cost = estimated_cost(quality)

    progress("Saving")
    jpg = GALLERY / f"{place_id}.jpg"
    final.save(jpg, "JPEG", quality=JPEG_QUALITY, optimize=True)
    a = item["attributes"]
    meta = {
        "id": place_id,
        "file": jpg.name,
        "fake": fake,
        "pipeline": "gpt-image-2-" + quality + "+seedvr2x",
        "calls": calls,
        "prompt": item["prompt_360"],
        "seed": item["seed"],
        "attributes": a,
        "summary": f"{a['setting_desc']}; {a['structures']}; {a['weather']}",
        "surreal": a["surreal"],
        "cost_estimate_usd": cost,
        "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "seconds": round(time.time() - t0, 1),
        "size": list(final.size),
        "seam_score": seam_score(final),
    }
    (GALLERY / f"{place_id}.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n",
                                             encoding="utf-8")
    return meta


def list_gallery() -> list[dict]:
    if not GALLERY.is_dir():
        return []
    places = []
    for p in sorted(GALLERY.glob("*.json"), reverse=True):
        try:
            m = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if (GALLERY / m.get("file", "")).exists():
            places.append(m)
    return places


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--quality", choices=sorted(GEN_COST), default="high")
    ap.add_argument("--weird", type=float, default=0.3)
    ap.add_argument("--fake", action="store_true", help="no API calls (testing)")
    args = ap.parse_args()
    load_env_file()
    meta = generate_place(args.quality, args.weird, args.fake, progress=print)
    print(f"Saved gallery/{meta['file']}  ~${meta['cost_estimate_usd']:.2f}  seam={meta['seam_score']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
