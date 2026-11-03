# Phantom Atlas

**Street view for a world that doesn't exist.**

Phantom Atlas drops you into a random street-level 360° panorama of a place that isn't real. Every scene is AI-generated in the style of a car-mounted street camera: an ordinary documentary snapshot of a road somewhere. Some places are quietly normal. Some are deliberately surreal.

> Work in progress. Currently in **Phase 0: model bake-off**.

## How it works

1. **Prompt generator** (`gen/prompt_gen.py`) builds a random place from independent ingredients: setting, buildings, road, roadside details, plants, weather, time of day, season, and sometimes a surreal twist. There is no fixed world map or invented countries; every place is a one-off.
2. **Image generation** (`gen/`, via [fal.ai](https://fal.ai)) turns each prompt into an equirectangular 360° panorama (2:1, seamless left–right edges, horizon level, camera car visible below).
3. **Viewer** (`web/`) shows one random panorama at a time. You can look around and zoom, but not move. It deploys to GitHub Pages.

## Roadmap

| Phase | Goal | Status |
|---|---|---|
| 0 | **Model bake-off**: run the same 10 test prompts through 3–4 generation pipelines, compare side by side, pick one | In progress |
| 1 | **Random viewer**: a static site that shows a random pre-generated panorama | Planned |
| 2 | Later ideas (only when asked) | — |

Out of scope for now: moving between panoramas, maps, guessing or scoring, a backend.

## Repo layout

```
gen/    Python generation scripts (prompt generator, bake-off runner, post-processing)
web/    Viewer frontend (Vite + TypeScript); images it shows live in web/public/
docs/   test_prompts.json, decisions.md (log of every model/pipeline decision)
```

## Running locally (optional)

Development normally happens in Claude Code cloud sessions, but everything also runs on your own machine:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python gen/prompt_gen.py --n 10 --seed 42 --stratify --out docs/test_prompts.json
```

Image generation needs a fal.ai API key in the `FAL_KEY` environment variable. Locally you can copy `.env.example` to `.env` and fill it in. **Never commit a real key.**

## Notes

- All imagery is AI-generated. No Google Street View imagery or branding is used.
- Decisions and the reasons behind them are logged in [`docs/decisions.md`](docs/decisions.md).
