"""Build web/public/bakeoff/index.json from the per-image metadata files.

The comparison page reads this one file instead of listing folders.

Usage:
    python gen/build_index.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BAKEOFF = ROOT / "web" / "public" / "bakeoff"
PROMPTS = ROOT / "docs" / "test_prompts.json"

# Display order and short labels for the comparison page.
PIPELINES = [
    ("flux1_lora", "A", "FLUX.1 + 360 LoRA"),
    ("klein_lora", "B", "FLUX.2 Klein + 360 LoRA"),
    ("gpt_image2", "C", "GPT Image 2 (medium)"),
    ("gpt_image2_high", "D", "GPT Image 2 (high)"),
    ("forward_hunyuan", "E", "Photo → Hunyuan World"),
]


def main() -> None:
    items = json.loads(PROMPTS.read_text())["items"]
    pipelines, totals = [], {}
    for name, letter, label in PIPELINES:
        folder = BAKEOFF / name
        if not folder.is_dir():
            continue
        metas = [json.loads(p.read_text()) for p in sorted(folder.glob("*.json"))]
        totals[name] = round(sum(m["cost_estimate_usd"] for m in metas), 3)
        desc = metas[0]["pipeline_description"] if metas else label
        endpoints = [c["endpoint"] for c in metas[0]["calls"]] if metas else []
        pipelines.append({"name": name, "letter": letter, "label": label,
                          "description": desc, "endpoints": endpoints,
                          "count": len(metas), "cost_total_usd": totals[name]})

    out_items = []
    for it in items:
        results = {}
        for p in pipelines:
            meta_path = BAKEOFF / p["name"] / f"{it['id']}.json"
            if not meta_path.exists():
                continue
            m = json.loads(meta_path.read_text())
            results[p["name"]] = {
                "file": f"bakeoff/{p['name']}/{it['id']}.jpg",
                "cost_usd": m["cost_estimate_usd"],
                "seam_score": m["seam_score"],
                "seconds": m["seconds"],
                "raw_size": m["raw_size"],
            }
        a = it["attributes"]
        out_items.append({
            "id": it["id"],
            "setting": a["setting"],
            "surreal": a["surreal"],
            "summary": f"{a['setting_desc']}; {a['structures']}; {a['weather']}",
            "prompt": it["prompt_360"],
            "results": results,
        })

    index = {"pipelines": pipelines, "items": out_items,
             "total_cost_usd": round(sum(totals.values()), 2)}
    (BAKEOFF / "index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n")
    n = sum(len(i["results"]) for i in out_items)
    print(f"Wrote index with {n} images, est. total ${index['total_cost_usd']:.2f}")


if __name__ == "__main__":
    main()
