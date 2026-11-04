# Decisions log

Every model, pipeline and design decision, with the reason. Newest at the bottom.

## 2026-11-03 — Prompt generator design
- **Decision:** `gen/prompt_gen.py` builds each prompt from independent random attributes: setting, structures, road, two roadside details, vegetation, weather, time of day, season and an optional surreal twist.
- **Why:** this keeps scenes fully random, with no world bible or fixed countries, while still letting us stratify test sets and trace every image back to its ingredients.
- Open-country settings (desert, tundra, steppe, ...) use their own structures and roadside lists, and some settings restrict vegetation. This avoids accidental clashes like shop chairs on a tundra road or cacti in a pine forest. Surreal twists are still intended and stay separate.
- Surreal twists are written in the same flat, factual tone as the rest of the prompt, so the image stays a plain street-camera shot.
- The 360 prompt asks for the camera car's roof and mount to be visible at the bottom (nadir), following the owner's preference. Faces and number plates are not blurred.
- `--stratify` spreads items evenly over settings, weather and time of day, and uses an exact surreal count (`round(n * weird)`).
- Test set: `python gen/prompt_gen.py --n 10 --seed 42 --stratify --out docs/test_prompts.json` (10 prompts, 3 surreal).

## 2026-11-03 — Phase 0 budget
- **Decision:** bake-off budget is **$20 total**, including test runs, for about 10 prompts × 3–4 pipelines.
- **Why:** set by the project owner. Final choice is made by eye from a side-by-side comparison.

## 2026-11-03 — Bake-off pipelines
- **Decision:** compare four pipelines on the 10 test prompts, all at 2048×1024 requested:
  - **A** `fal-ai/flux-lora`: FLUX.1 [dev] + MultiTrickFox Equirectangular LoRA v3, scale 1.0, guidance 2.5
  - **B** `fal-ai/flux-2/klein/9b/lora`: FLUX.2 [klein] 9B + crafiq 360 panorama LoRA, 8 steps
  - **C** `openai/gpt-image-2`, quality medium, prompted for an equirectangular projection
  - **D** `openai/gpt-image-2`, quality high, added at the owner's request
- **Why:** three different approaches (specialist LoRA on an older base, specialist LoRA on a newer base, strong general model), plus a quality check on the general model.
- **Dropped:** forward photo → `fal-ai/hunyuan_world`. In the p009 test it looked the least photographic (render-like cobbles, odd car shape, washed-out sky), it cost the most (~$0.17 each) and it was slowest (~2.5 min). In the full run it hung without producing an image, so the owner chose to drop it.
- **Note:** `fal-ai/flux-lora` returned 1536×768 instead of 2048×1024.

## 2026-11-03 — Bake-off results (owner to pick by eye)
| | Pipeline | Est. cost (10 images) | Median seam score | Avg time | Notes |
|---|---|---|---|---|---|
| A | FLUX.1 + LoRA | $0.45 | 14.8 | 8 s | 1536×768 only. Car often missing. Ignored 2 of 3 surreal twists. Visible seams. |
| B | FLUX.2 Klein + LoRA | $0.32 | 23.6 | 9 s | Very natural. Car always visible but looks bonnet-mounted. Seams sometimes visible. Partly follows surreal prompts. |
| C | GPT Image 2 medium | ~$0.60 | 5.2 | 25 s | Most convincing street-camera look. Roof camera visible. Seamless. Follows all 3 surreal twists. |
| D | GPT Image 2 high | ~$2.50 | 5.5 | 65 s | Similar to C with somewhat more detail, at about 4× the cost. |

Seam score is the mean absolute difference between the left and right edge columns (0–255). Lower is better.
Total bake-off spend is estimated at about $4.30, including the test round and the dropped Hunyuan runs. GPT prices are estimates; fal's usage page has the exact figures.

## 2026-11-04 — Production pipeline: GPT Image 2 (high) at 3840×1920 + SeedVR 2× upscale
- **Decision:** every new place uses `openai/gpt-image-2`, quality **high**, at **3840×1920** (the model's largest 2:1 size), PNG output. Then `fal-ai/seedvr/upscale/image` ×2 brings it to **7680×3840**, saved as JPEG quality 92.
- **Why:** the owner judged GPT Image 2 high "by far the best" in the bake-off, but the 2048×1024 images looked soft in the viewer. A resolution test on p005 compared:
  - A: before, 2048, ~$0.25
  - B: 3840 native, ~$0.88
  - C: 3840 + SeedVR, ~$0.91
  - D: 3840 + Topaz, ~$1.04
  - E: medium 3840 + SeedVR, ~$0.25

  The owner picked **C**. E was much cheaper but had visibly simpler texture.
- **Seam handling:** before upscaling, 128 px from each edge are copied onto the opposite side, then cropped off afterwards, so the left/right join stays continuous (seam score ≈ 4–7).
- **Cost:** about $0.91 per place (estimate; GPT is token-priced).

## 2026-11-04 — Phase 1 is a local app (exception to "no backend")
- **Decision:** Phase 1 is a local Windows app (`Phantom Atlas.bat` → `app/server.py`). It generates a new random place on demand and shows it in the 360° viewer. Places are saved to `gallery/` (git-ignored).
- **Why:** on-demand generation needs the fal.ai key, and a GitHub Pages site is public, so the key can't live there. A server bound to 127.0.0.1 keeps the key on the owner's computer. The owner approved this exception to the "no backend" rule.
- **Safety:** the server only listens on 127.0.0.1, rejects cross-site POSTs, runs one generation at a time, and the page asks for confirmation with the estimated cost before every paid generation.
