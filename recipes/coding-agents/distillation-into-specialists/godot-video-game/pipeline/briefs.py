"""Brief sampler: structured, diverse briefs per segment.

    python3 pipeline/briefs.py sky --n 24 --seed 1 --out pipeline/runs/sky1/briefs.jsonl

Diversity is the biggest lever for the specialist, so the sampler covers the
brief space evenly (time of day x weather) rather than sampling uniformly at
random, and then adds palette and mood words.
"""
import argparse
import itertools
import json
import random
from pathlib import Path

from common import CONTRACT_VERSION, write_jsonl

TIMES = {
    "dawn": {"elev": (3, 12), "words": ["pink-gold horizon", "cool violet zenith", "long soft shadows"]},
    "morning": {"elev": (25, 40), "words": ["clean light", "pale blue", "crisp shadows"]},
    "noon": {"elev": (55, 75), "words": ["hard white sun", "deep saturated blue zenith", "short shadows"]},
    "afternoon": {"elev": (30, 45), "words": ["warm neutral light", "slightly hazy horizon"]},
    "golden hour": {"elev": (6, 15), "words": ["orange sun", "amber highlights", "very long shadows", "warm haze"]},
    "dusk": {"elev": (-2, 4), "words": ["magenta and orange band at the horizon", "indigo zenith", "sun just at the horizon"]},
    "night": {"elev": (-20, -8), "words": ["moonlit", "deep navy zenith", "cool blue fill", "faint horizon glow"]},
}
WEATHER = {
    "clear": {"cover": (0.0, 0.15), "haze": (0.05, 0.25)},
    "scattered clouds": {"cover": (0.25, 0.45), "haze": (0.1, 0.35)},
    "broken clouds": {"cover": (0.5, 0.7), "haze": (0.2, 0.5)},
    "overcast": {"cover": (0.85, 1.0), "haze": (0.4, 0.8)},
    "hazy": {"cover": (0.05, 0.3), "haze": (0.7, 1.0)},
}
MOODS = ["postcard", "cinematic", "documentary", "dreamy", "gritty", "serene", "stormy-light", "tropical"]
WORLDS = ["beach", "street"]


def sample_sky(n: int, seed: int, times=None, weather=None):
    rng = random.Random(seed)
    combos = [(t, w) for t, w in itertools.product(TIMES.keys(), WEATHER.keys())
              if (not times or t in times) and (not weather or w in weather)]
    rng.shuffle(combos)
    out = []
    for i in range(n):
        tod, wx = combos[i % len(combos)]
        t, w = TIMES[tod], WEATHER[wx]
        elev = round(rng.uniform(*t["elev"]), 1)
        cover = round(rng.uniform(*w["cover"]), 2)
        haze = round(rng.uniform(*w["haze"]), 2)
        azimuth = rng.choice([30, 60, 90, 120, 150, 210, 240, 270, 300, 330])
        world = rng.choice(WORLDS)
        words = rng.sample(t["words"], k=min(2, len(t["words"])))
        mood = rng.choice(MOODS)
        brief = {
            "id": f"sky-{seed:02d}-{i:03d}",
            "segment": "sky",
            "contract": CONTRACT_VERSION,
            "world": world,
            "time_of_day": tod,
            "weather": wx,
            "sun_elevation_deg": elev,
            "sun_azimuth_deg": azimuth,
            "cloud_cover": cover,
            "haze": haze,
            "wind_strength": round(rng.uniform(0.3, 2.0), 2),
            "palette_words": words,
            "mood": mood,
            "text": (f"A {mood} {tod} sky over the {world} scene, {wx}. Sun elevation {elev} degrees, "
                     f"azimuth {azimuth} degrees. Cloud cover {cover:.2f}, haze {haze:.2f}. "
                     f"Palette: {', '.join(words)}."),
        }
        out.append(brief)
    return out


DENSITY = ["sparse", "normal", "dense"]
VEG_MIX = {"beach": ["tall fan palms only", "mostly tall fan palms with a few coconut palms", "coconut palms dominant", "palms with dense hedges behind the deck"],
           "street": ["leafy trees only", "mostly leafy trees with some fan palms", "half palms half leafy trees", "palm-lined with sparse trees", "leafy trees with continuous hedges"]}
VEG_SIZE = ["young", "mature", "giant"]
VEG_HEDGES = ["no hedges", "some hedges", "continuous hedges"]
VEG_WORDS = ["lush", "dry and sun-bleached", "manicured", "wild and overgrown", "tidy municipal planting", "resort planting"]


def vegetation_brief(bid: str, world: str, density: str, species_mix: str, size: str, hedges: str, look: str) -> dict:
    """A vegetation brief exactly as the specialist was trained on it (key order and text template);
    used by the sampler and by the director."""
    return {"id": bid, "segment": "vegetation", "contract": CONTRACT_VERSION, "world": world,
            "density": density, "species_mix": species_mix, "size": size, "hedges": hedges, "look": look,
            "text": f"{look.capitalize()} vegetation on the {world}: {density} density, {species_mix}, {size} plants, {hedges}."}


def sample_vegetation(n: int, seed: int, times=None, weather=None):
    rng = random.Random(seed + 100)
    out = []
    for i in range(n):
        world = WORLDS[i % 2]
        density = DENSITY[(i // 2) % 3]
        mix = rng.choice(VEG_MIX[world])
        size = rng.choice(VEG_SIZE)
        hedges = rng.choice(VEG_HEDGES)
        word = rng.choice(VEG_WORDS)
        out.append(vegetation_brief(f"veg-{seed:02d}-{i:03d}", world, density, mix, size, hedges, word))
    return out


PROPS_BEACH_PALETTES = ["white frames with blue and teal fabrics, pastel umbrellas", "white frames with red and yellow fabrics, striped umbrellas",
                        "natural wood frames with cream fabrics, plain white umbrellas", "mixed bright fabrics, rainbow umbrellas"]
PROPS_STREET_PALETTES = ["grey lamps, dark green bins, red hydrants", "black lamps, blue bins, yellow hydrants", "weathered wooden poles, grey bins, red hydrants"]


PROPS_UMBRELLAS = ["few umbrellas", "umbrellas on about a third of the loungers", "umbrellas on most loungers"]
PROPS_CLUTTER = ["little clutter", "some clutter (buckets, coolers, balls, bags)", "lots of clutter"]
PROPS_TOWELS = ["mostly loungers", "loungers with some towels", "many towels among the loungers"]
PROPS_ITEMS = ["lamps and bins only", "lamps, bins and hydrants", "lamps, bins, hydrants, a bench and a mailbox",
               "lamps, power poles with wires, bins, hydrants, a stop sign"]
PROPS_SPACING = ["lamps every 12 m", "lamps every 18 m", "lamps every 24 m"]


def props_brief(bid: str, world: str, density: str, palette: str, **f) -> dict:
    """A props brief exactly as the specialist was trained on it (key order and text template);
    used by the sampler and by the director."""
    if world == "beach":
        text = f"Beach furniture, {density} density: {f['towels']}, {f['umbrellas']}, {f['clutter']}; {palette}."
        extra = {"umbrellas": f["umbrellas"], "clutter": f["clutter"], "towels": f["towels"]}
    else:
        text = f"Street furniture, {density} density: {f['items']}, {f['spacing']}; {palette}."
        extra = {"items": f["items"], "spacing": f["spacing"]}
    row = {"id": bid, "segment": "props", "contract": CONTRACT_VERSION, "world": world,
           "density": density, "palette": palette, "text": text}
    row.update(extra)
    return row


def sample_props(n: int, seed: int, times=None, weather=None):
    rng = random.Random(seed + 200)
    out = []
    for i in range(n):
        world = WORLDS[i % 2]
        density = DENSITY[(i // 2) % 3]
        bid = f"props-{seed:02d}-{i:03d}"
        if world == "beach":
            # drawn in the original order so a given seed produces the same briefs as before
            umbrellas = rng.choice(PROPS_UMBRELLAS)
            clutter = rng.choice(PROPS_CLUTTER)
            towels = rng.choice(PROPS_TOWELS)
            palette = rng.choice(PROPS_BEACH_PALETTES)
            out.append(props_brief(bid, world, density, palette, umbrellas=umbrellas, clutter=clutter, towels=towels))
        else:
            items = rng.choice(PROPS_ITEMS)
            spacing = rng.choice(PROPS_SPACING)
            palette = rng.choice(PROPS_STREET_PALETTES)
            out.append(props_brief(bid, world, density, palette, items=items, spacing=spacing))
    return out


SAND_TONES = ["dark warm tan", "golden", "pale white coral sand", "grey volcanic", "pinkish shell sand"]
ROAD_TONES = ["fresh black asphalt", "worn grey asphalt", "brownish sun-baked asphalt", "patched and faded asphalt"]


SAND_WET = ["narrow wet band", "wide wet band", "wide wet band with a strong mirror sheet"]
SAND_SHELLS = ["few shells", "shells and pebbles along the tide line", "dense shell drift"]
SAND_GRAIN = ["fine grain", "coarse grain with ripples", "smooth packed sand"]
ROAD_MARKINGS = ["double yellow centre line and white edge lines", "single dashed white centre line", "no centre line, white edge lines only"]
ROAD_KERBS = ["plain concrete kerbs", "red-painted kerbs by the crossing", "granite grey kerbs"]
ROAD_SIDEWALKS = ["short sidewalk slabs with cracks", "long clean slabs", "weathered slabs with many joints"]
ROAD_LAWNS = ["lush green lawns", "dry yellow-green lawns", "dark mown lawns with stripes"]


def ground_brief(bid: str, world: str, **f) -> dict:
    """A ground brief exactly as the specialist was trained on it (key order and text template);
    beach fields tone, wet_band, shells, grain; street fields tone, markings, kerb, sidewalk, lawn."""
    row = {"id": bid, "segment": "ground", "contract": CONTRACT_VERSION, "world": world}
    if world == "beach":
        row["text"] = f"Beach sand: {f['tone']}, {f['grain']}, {f['wet_band']}, {f['shells']}."
        keys = ["tone", "wet_band", "shells", "grain"]
    else:
        row["text"] = f"Street ground: {f['tone']}, {f['markings']}, {f['kerb']}, {f['sidewalk']}, {f['lawn']}."
        keys = ["tone", "markings", "kerb", "sidewalk", "lawn"]
    row.update({k: f[k] for k in keys})
    return row


def sample_ground(n: int, seed: int, times=None, weather=None):
    rng = random.Random(seed + 300)
    out = []
    for i in range(n):
        world = WORLDS[i % 2]
        bid = f"ground-{seed:02d}-{i:03d}"
        if world == "beach":
            tone = rng.choice(SAND_TONES)
            wet = rng.choice(SAND_WET)
            shells = rng.choice(SAND_SHELLS)
            grain = rng.choice(SAND_GRAIN)
            out.append(ground_brief(bid, world, tone=tone, wet_band=wet, shells=shells, grain=grain))
        else:
            tone = rng.choice(ROAD_TONES)
            markings = rng.choice(ROAD_MARKINGS)
            kerb = rng.choice(ROAD_KERBS)
            walk = rng.choice(ROAD_SIDEWALKS)
            lawn = rng.choice(ROAD_LAWNS)
            out.append(ground_brief(bid, world, tone=tone, markings=markings, kerb=kerb, sidewalk=walk, lawn=lawn))
    return out


def sample_water(n: int, seed: int, times=None, weather=None):
    rng = random.Random(seed + 400)
    out = []
    for i in range(n):
        state = ["calm", "gentle", "choppy"][i % 3]
        colour = rng.choice(["turquoise tropical", "deep navy", "grey-green temperate", "milky jade", "clear aquamarine"])
        foam = rng.choice(["little foam", "lacy foam band at the edge", "heavy foam and breakers"])
        clarity = rng.choice(["sand visible far out", "sand visible only at the edge", "murky"])
        out.append({"id": f"water-{seed:02d}-{i:03d}", "segment": "water", "contract": CONTRACT_VERSION, "world": "beach",
                    "sea_state": state, "colour": colour, "foam": foam, "clarity": clarity,
                    "text": f"The sea: {state}, {colour} water, {foam}, {clarity}."})
    return out


SAMPLERS = {"sky": sample_sky, "vegetation": sample_vegetation, "props": sample_props, "ground": sample_ground, "water": sample_water}

# The words each specialist was trained on, for the director to choose from.
VOCAB = {
    "vegetation": {"density": DENSITY, "species_mix": VEG_MIX, "size": VEG_SIZE, "hedges": VEG_HEDGES, "look": VEG_WORDS},
    "ground": {"beach": {"tone": SAND_TONES, "wet_band": SAND_WET, "shells": SAND_SHELLS, "grain": SAND_GRAIN},
               "street": {"tone": ROAD_TONES, "markings": ROAD_MARKINGS, "kerb": ROAD_KERBS, "sidewalk": ROAD_SIDEWALKS,
                          "lawn": ROAD_LAWNS}},
    "props": {"beach": {"density": DENSITY, "palette": PROPS_BEACH_PALETTES, "towels": PROPS_TOWELS,
                        "umbrellas": PROPS_UMBRELLAS, "clutter": PROPS_CLUTTER},
              "street": {"density": DENSITY, "palette": PROPS_STREET_PALETTES, "items": PROPS_ITEMS,
                         "spacing": PROPS_SPACING}},
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("segment", choices=SAMPLERS.keys())
    ap.add_argument("--n", type=int, default=24)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", required=True)
    ap.add_argument("--times", help="comma list to restrict time of day, e.g. night,dusk")
    ap.add_argument("--weather", help="comma list to restrict weather, e.g. overcast,broken clouds")
    a = ap.parse_args()
    rows = SAMPLERS[a.segment](a.n, a.seed, a.times.split(",") if a.times else None, a.weather.split(",") if a.weather else None)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(a.out, rows)
    print(f"wrote {len(rows)} {a.segment} briefs to {a.out}")
    for r in rows[:3]:
        print(" ", r["text"])


if __name__ == "__main__":
    main()
