"""Random prompt generator for Phantom Atlas.

Builds street-level panorama prompts by sampling independent attributes
(setting, architecture, road, weather, ...). Places are fully random: there is
no world bible and no fixed fictional countries. A fraction of places get a
surreal twist, which is described in the same flat documentary tone as
everything else.

Usage:
    python gen/prompt_gen.py --n 10 --seed 42 --stratify --out docs/test_prompts.json
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Attribute lists. Edit these rather than hand-editing generated prompts.
# ---------------------------------------------------------------------------

# Each setting has a name (used for stratification) and a description.
SETTINGS = [
    ("dense_city", "a busy downtown street lined with mid-rise buildings"),
    ("old_town", "a narrow street in an old town centre"),
    ("suburb", "a quiet residential suburban street"),
    ("small_town", "the main street of a small town"),
    ("village", "a rural village lane"),
    ("farmland", "a straight road through open farmland"),
    ("industrial", "a road through an industrial area with warehouses and yards"),
    ("highway", "the shoulder of a multi-lane highway"),
    ("desert", "a two-lane road crossing a dry desert"),
    ("mountain", "a winding mountain road with a steep slope on one side"),
    ("forest", "a road through a dense forest"),
    ("coastal", "a coastal road with the sea visible beside it"),
    ("tropical", "a road through a humid tropical town with lush vegetation"),
    ("tundra", "a remote road across flat, treeless tundra"),
    ("steppe", "a long road across a grassy steppe with distant hills"),
    ("wetland", "a raised road through marshland and reed beds"),
]

ARCHITECTURE = [
    "whitewashed concrete houses with coloured shutters",
    "red brick terraced houses",
    "pastel-painted stucco buildings with flat roofs",
    "grey prefabricated apartment blocks",
    "timber houses on stilts",
    "mud-brick and adobe buildings",
    "corrugated metal sheds and shacks",
    "glass and steel office buildings",
    "stone cottages with slate roofs",
    "two-storey shophouses with hand-painted signs",
    "wooden houses painted in faded bright colours",
    "half-finished concrete buildings with exposed rebar",
    "low bungalows behind chain-link fences",
    "tiled-roof houses with small courtyards",
]

# Used for open-country settings where buildings are sparse.
SPARSE_STRUCTURES = [
    "a lone farmhouse in the distance",
    "a few scattered sheds",
    "a roadside petrol station",
    "a small bus shelter",
    "power lines on wooden poles",
    "a rusted water tank on a tower",
    "a fenced compound far off",
    "no buildings in sight",
]

# Settings where generic vegetation would contradict the place (cacti on the
# tundra). Surreal twists are separate, so this only removes accidental clashes.
VEGETATION_BY_SETTING = {
    "desert": ["dry scrub and tumbleweeds", "cacti", "a few dusty palm trees"],
    "tundra": ["moss and lichen", "low grey-green shrubs"],
    "forest": ["tall pine trees", "birch trees", "dense broadleaf trees"],
    "tropical": ["palm trees", "banana plants and bamboo", "flowering bushes"],
}

OPEN_SETTINGS = {"farmland", "highway", "desert", "mountain", "forest", "tundra", "steppe", "wetland"}

ROADS = [
    "a cracked asphalt road with faded white centre lines",
    "a fresh black asphalt road with yellow edge lines",
    "a gravel road",
    "a dirt road with tyre ruts",
    "a cobblestone road",
    "a concrete road with expansion joints",
    "a patched asphalt road with potholes",
    "a red-tinted asphalt road with dashed lines",
]

ROADSIDE = [
    "utility poles with sagging wires",
    "parked cars along the kerb",
    "a few pedestrians on the pavement",
    "street signs in an unfamiliar script",
    "plastic chairs outside a shop",
    "a row of rubbish bins",
    "roadside billboards with faded posters",
    "motorbikes parked on the pavement",
    "a low stone wall",
    "a small roadside shrine",
    "traffic cones and a temporary barrier",
    "laundry hanging between buildings",
]

# Roadside details for open-country settings (no kerbs or shopfronts).
ROADSIDE_OPEN = [
    "a dented metal guardrail",
    "wooden fence posts with wire",
    "a faded speed limit sign",
    "kilometre marker posts",
    "a parked pickup truck on the verge",
    "a small roadside shrine",
    "a few grazing animals",
    "a drainage ditch beside the road",
    "reflector posts along the edge",
    "an abandoned car on the verge",
]

VEGETATION = [
    "palm trees",
    "tall pine trees",
    "dry scrub and tumbleweeds",
    "neatly trimmed hedges",
    "overgrown weeds along the verge",
    "birch trees",
    "banana plants and bamboo",
    "cacti",
    "bare deciduous trees",
    "patchy lawn grass",
    "moss and lichen",
    "flowering bushes",
]

WEATHER = [
    "clear sky",
    "overcast sky",
    "light rain with wet road surfaces",
    "fog",
    "scattered clouds",
    "hazy sky",
    "light snow on the ground",
    "dusty air",
]

TIME_OF_DAY = [
    "morning",
    "midday",
    "afternoon",
    "late afternoon with long shadows",
    "early evening",
]

SEASON = ["spring", "summer", "autumn", "winter", "dry season", "wet season"]

# Surreal twists: stated plainly, as if they were ordinary facts of the place.
SURREAL = [
    "the sky is a solid pale green",
    "every building is upside down, resting on its roof",
    "a giant teacup the size of a house sits in a field beside the road",
    "the road continues straight up into the sky in the distance",
    "the trees are made of stacked concrete blocks",
    "an enormous stone hand rises out of the ground beside the road",
    "the sea hangs above the horizon like a second sky",
    "all the houses are perfectly identical and evenly spaced",
    "a staircase leads up from the pavement and stops in mid-air",
    "the ground is covered in a thin layer of salt-white sand that looks like snow in warm weather",
    "hundreds of clocks are mounted on the utility poles",
    "the buildings are made of brightly coloured glass bricks",
    "a ship is stranded in the middle of the street",
    "the moon is enormous and fills a quarter of the daytime sky",
    "doors are set into the trunks of the trees",
    "the road surface is made of wooden planks",
    "a second, smaller copy of the street hangs upside down in the sky",
    "huge smooth white spheres rest in the fields",
    "the shadows point in different directions",
    "giant chess pieces stand along the roadside",
]

CAMERA_360 = (
    "360 degree equirectangular panorama, street-level photo taken from a camera "
    "mounted on the roof of a car, about 2.5 metres above the road, the car is "
    "centred on the road, level horizon at the vertical centre of the image, the "
    "car roof and camera mount visible at the bottom of the panorama"
)

CAMERA_FORWARD = (
    "street-level photo taken from a camera on the roof of a car, looking straight "
    "down the road, camera about 2.5 metres above the road, level horizon"
)

STYLE = (
    "ordinary documentary snapshot, natural colours, slightly flat lighting, "
    "mild JPEG compression, everyday photo, not cinematic"
)

NEGATIVE = (
    "cinematic, dramatic lighting, HDR, oversaturated, painting, illustration, "
    "3d render, cartoon, fisheye circle, black borders, vignette, tilted horizon, "
    "text watermark, logo, Google, blurry, low detail, distorted"
)


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def sample_place(rng: random.Random, setting: tuple[str, str], weather: str,
                 time_of_day: str, surreal: bool) -> dict:
    key, setting_desc = setting
    attrs = {
        "setting": key,
        "setting_desc": setting_desc,
        "road": rng.choice(ROADS),
        "roadside": rng.sample(ROADSIDE_OPEN if key in OPEN_SETTINGS else ROADSIDE, 2),
        "vegetation": rng.choice(VEGETATION_BY_SETTING.get(key, VEGETATION)),
        "weather": weather,
        "time_of_day": time_of_day,
        "season": rng.choice(SEASON),
        "surreal": None,
    }
    if key in OPEN_SETTINGS:
        attrs["structures"] = rng.choice(SPARSE_STRUCTURES)
    else:
        attrs["structures"] = rng.choice(ARCHITECTURE)
    if surreal:
        attrs["surreal"] = rng.choice(SURREAL)
    return attrs


def describe(attrs: dict) -> str:
    parts = [
        f"{attrs['setting_desc']}, {attrs['road']}",
        attrs["structures"],
        f"{attrs['roadside'][0]}, {attrs['roadside'][1]}",
        attrs["vegetation"],
        f"{attrs['time_of_day']}, {attrs['season']}, {attrs['weather']}",
    ]
    text = "; ".join(parts)
    if attrs["surreal"]:
        text += f"; {attrs['surreal']}"
    return text


def build_item(index: int, master_seed: int, attrs: dict, rng: random.Random) -> dict:
    scene = describe(attrs)
    return {
        "id": f"p{index + 1:03d}",
        # Per-item seed for the image model, derived from the master seed.
        "seed": rng.randrange(0, 2**31 - 1),
        "attributes": attrs,
        "prompt_360": f"{CAMERA_360}. {scene}. {STYLE}.",
        "prompt_forward": f"{CAMERA_FORWARD}. {scene}. {STYLE}.",
        "negative_prompt": NEGATIVE,
    }


def generate(n: int, seed: int, weird: float, stratify: bool) -> list[dict]:
    rng = random.Random(seed)

    if stratify:
        # Spread items across settings, weather and time of day, and use an
        # exact surreal count (round(n * weird)) instead of a coin flip each.
        settings = _spread(rng, SETTINGS, n)
        weathers = _spread(rng, WEATHER, n)
        times = _spread(rng, TIME_OF_DAY, n)
        n_surreal = round(n * weird)
        surreal_flags = [True] * n_surreal + [False] * (n - n_surreal)
        rng.shuffle(surreal_flags)
    else:
        settings = [rng.choice(SETTINGS) for _ in range(n)]
        weathers = [rng.choice(WEATHER) for _ in range(n)]
        times = [rng.choice(TIME_OF_DAY) for _ in range(n)]
        surreal_flags = [rng.random() < weird for _ in range(n)]

    items = []
    for i in range(n):
        attrs = sample_place(rng, settings[i], weathers[i], times[i], surreal_flags[i])
        items.append(build_item(i, seed, attrs, rng))
    return items


def _spread(rng: random.Random, options: list, n: int) -> list:
    """Return n picks that use every option as evenly as possible."""
    picks: list = []
    while len(picks) < n:
        batch = list(options)
        rng.shuffle(batch)
        picks.extend(batch)
    return picks[:n]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--n", type=int, default=10, help="number of prompts")
    parser.add_argument("--seed", type=int, default=None, help="master random seed")
    parser.add_argument("--weird", type=float, default=0.3,
                        help="chance (0..1) that a place is surreal")
    parser.add_argument("--stratify", action="store_true",
                        help="spread prompts evenly across settings/weather/time "
                             "and use an exact surreal count")
    parser.add_argument("--out", type=Path, default=None,
                        help="output JSON path (default: print to stdout)")
    args = parser.parse_args(argv)

    if not 0.0 <= args.weird <= 1.0:
        parser.error("--weird must be between 0 and 1")
    if args.n < 1:
        parser.error("--n must be at least 1")

    seed = args.seed if args.seed is not None else random.randrange(2**31)
    items = generate(args.n, seed, args.weird, args.stratify)
    payload = {
        "generator": "gen/prompt_gen.py",
        "master_seed": seed,
        "weird": args.weird,
        "stratify": args.stratify,
        "items": items,
    }
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"Wrote {len(items)} prompts to {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
