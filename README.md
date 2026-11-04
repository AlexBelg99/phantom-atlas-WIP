# Phantom Atlas

**Street view for a world that doesn't exist.**

Phantom Atlas drops you into a random street-level 360° panorama of a place that isn't real. Every scene is AI-generated in the style of a car-mounted street camera: an ordinary documentary snapshot of a road somewhere. Some places are quietly normal. Some are deliberately surreal.

> Work in progress. Currently in **Phase 0: model bake-off**.

## How it works

1. **Prompt generator** (`gen/prompt_gen.py`) builds a random place from independent ingredients: setting, buildings, road, roadside details, plants, weather, time of day, season, and sometimes a surreal twist. There is no fixed world map or invented countries; every place is a one-off.
2. **Image generation** (`gen/`, via [fal.ai](https://fal.ai)) turns each prompt into an equirectangular 360° panorama (2:1, seamless left–right edges, horizon level, camera car visible below).
3. **Viewer**: the local app (`app/`) shows each place in a 360° viewer. You can look around and zoom, but not move. The `web/` site on GitHub Pages shows the bake-off comparison.

## Roadmap

| Phase | Goal | Status |
|---|---|---|
| 0 | **Model bake-off**: 10 test prompts through 4 pipelines, compared side by side | Done: GPT Image 2 (high) at 3840×1920 + SeedVR 2× upscale |
| 1 | **Local app**: press "New place", get a brand-new random panorama in a 360° viewer | In progress |
| 2 | Later ideas (only when asked) | — |

Out of scope for now: moving between panoramas, maps, guessing or scoring, an online backend.

## Using the app on Windows

### One-time setup
1. **Install Python** from [python.org/downloads](https://www.python.org/downloads/). In the installer, tick **"Add python.exe to PATH"**.
2. **Download this project** with [GitHub Desktop](https://desktop.github.com/): *File → Clone repository → phantom-atlas-WIP*. You can then get updates later with **Fetch origin → Pull**.
3. **Double-click `Phantom Atlas.bat`** in the project folder. The first time, it:
   - sets things up (about a minute)
   - opens a file called `.env` in Notepad. Replace `your-fal-api-key-here` with your fal.ai key, save, and close Notepad.
4. **Double-click `Phantom Atlas.bat` again.** Your browser opens the app.

`.env` stays on your computer and is blocked from git, so the key is never uploaded.

### Every day
- Double-click **`Phantom Atlas.bat`**. A black window opens; keep it open while you use the app, and close it to stop.
- **New place** generates a fresh random panorama. It takes about 1–2 minutes and costs about **$0.91**; the app asks before spending.
- **Random from gallery** and **Gallery** revisit places you already generated, for free.
- Every place is saved in the `gallery` folder as a 7680×3840 JPEG plus a small `.json` with its prompt and details.

**Windows says "Windows protected your PC"?** Click **More info → Run anyway**. It's a plain text script you can open in Notepad to check.

## Repo layout

```
gen/    Python generation scripts (prompt generator, bake-off runner, production pipeline)
app/    Local app: small server (127.0.0.1 only) and its page
gallery/  Your generated places (created by the app, never committed)
web/    Viewer frontend (Vite + TypeScript); images it shows live in web/public/
docs/   test_prompts.json, decisions.md (log of every model/pipeline decision)
```

## For developers

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app/server.py --fake        # the app in test mode: no API calls, no cost
python gen/pipeline.py             # generate one place from the command line (costs ~$0.91)
python gen/prompt_gen.py --n 10 --seed 42 --stratify --out docs/test_prompts.json
```

Generation reads `FAL_KEY` from the environment, or from a `.env` file in the project folder. **Never commit a real key.**

## Notes

- All imagery is AI-generated. No Google Street View imagery or branding is used.
- Decisions and the reasons behind them are logged in [`docs/decisions.md`](docs/decisions.md).
