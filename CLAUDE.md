# Project: Phantom Atlas (working title)
A random street-level panorama viewer for a world that doesn't exist. Each panorama is an AI-generated 360° image in the style of a car-mounted street camera. Every scene is randomly generated; some are deliberately surreal.

## Current phase
Phase 0 (model bake-off) is done: GPT Image 2 high at 3840x1920 + SeedVR 2x upscale (see docs/decisions.md).
Phase 1: a local Windows app ("Phantom Atlas.bat" -> app/server.py) that generates a new random place on demand and shows it in the 360° viewer. The GitHub Pages site stays as the bake-off comparison / public gallery.

## Hard rules
- No Move: one static panorama at a time (look around and zoom only). Do not build movement or linked panoramas.
- Fully random scenes: do not create a world bible or fixed fictional countries.
- No guessing, maps, or scoring yet. Do not build them unless asked.
- Surreal content is intended. Don't "fix" weird prompts to be realistic; keep the plain street-camera style.

## How we work (GitHub + Claude Code cloud sessions)
- The owner runs the local app on Windows. Test app changes with `python app/server.py --fake` (no API calls) before spending money.
- The repo lives on GitHub. Claude works in cloud sessions, on a branch, and opens a pull request for each piece of work. I review and merge.
- FAL_KEY is an environment variable on the cloud environment. Read it from os.environ; never write it into a file. (.env is only a fallback for running locally.)
- I can't open files on the cloud VM, so anything I need to look at must be committed: generated images go in /web/public, and the /web site deploys to GitHub Pages from main.
- In the PR description, list what was generated, the API cost, and anything that failed.

## Stack
- Generation scripts: Python 3.11+ in /gen, calling fal.ai (fal-client)
- Frontend: Vite + TypeScript in /web, panorama viewer: Pannellum (or Photo Sphere Viewer); built and deployed to GitHub Pages by a GitHub Actions workflow
- Data: bake-off images in /web/public/bakeoff/<pipeline>/<id>.jpg (+ metadata JSON)
- Local app: app/server.py (Python stdlib http.server, 127.0.0.1 only) + app/static/index.html (Photo Sphere Viewer from jsDelivr); production pipeline in gen/pipeline.py
- Local app output goes to /gallery (git-ignored, 7680x3840 JPEG q92). Never commit gallery images.
- Keep committed images reasonably small: JPEG, quality ~85, max 4096x2048

## Repo layout
- /gen — prompt_gen.py (random prompt generator), bakeoff.py, pipeline.py (production pipeline), build_index.py
- /app — local app server and page; "Phantom Atlas.bat" at the repo root launches it on Windows
- /web — viewer frontend (and the images it shows, under /web/public)
- /docs — test_prompts.json, decisions.md

## Prompt generator
- `python gen/prompt_gen.py --n 10 --seed 42 --stratify --out docs/test_prompts.json`
- `--weird 0..1` = chance a place is surreal (default 0.3)
- Each item: id, seed, attributes, prompt_360, prompt_forward, negative_prompt
- Change attribute lists in prompt_gen.py rather than hand-editing prompts.

## Panorama spec
- Equirectangular, 2:1 (e.g. 2048x1024 or larger), left/right edges must match
- Camera ~2.5 m high, centered on a road, horizon level at vertical center
- Look: ordinary documentary snapshot, natural colors, mild compression; not cinematic
- Every image has a metadata JSON: id, pipeline, model/endpoint, prompt, seed, attributes, cost estimate, date

## Conventions
- Small, reviewable changes. Explain the plan before large changes.
- Before spending API money on a batch, run one item first and show me the result.
- Log every model/pipeline decision in /docs/decisions.md with the reason.
- Never commit .env or API keys. Scratch output can go in /gen/out (ignored); images I need to see go in /web/public.
- When checking generated images, open them and look; report seam/horizon/warping problems.

## Do not
- Use or download Google Street View imagery or Google branding.
- Add an online backend or database until Phase 2 asks for one. (Exception: the local app server, which only listens on 127.0.0.1.)
- Expose the fal key to a browser or a public site.
