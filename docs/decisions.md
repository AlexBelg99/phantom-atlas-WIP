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
