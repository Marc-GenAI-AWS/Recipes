"""Held-out vegetation-layer brief sampler (segment 4: the Grass field).

Conditions the TECHNIQUE of the instanced grass — blade character, density
distribution, wind response, tip treatment — never the palette (uGrassA/B) or the
terrain (groundH is frozen). Seeded so eval/train/CaR/RL sets are disjoint by seed.
"""
from __future__ import annotations

import random

CHARACTER = [
    "native prairie bunchgrass, thin curved blades",
    "tall seed-head grass with heavy drooping tips",
    "short grazed turf blades, stiff and upright",
    "mixed sedge and grass of uneven heights",
    "dry late-summer grass, wiry and pale at the tips",
]
DENSITY = [
    "dense in the near meadow, thinning toward the far basin",
    "clumped in drifts with bare gaps between",
    "an even carpet across the whole basin",
    "thickest in the hollows, sparse on the rises",
]
WIND = [
    "gentle continuous sway",
    "gust fronts that visibly ripple across the field",
    "stiff dry stems that barely move",
    "long rolling waves traveling east",
]
TIPS = [
    "sun-bleached tips",
    "tips that glow when backlit by the light corridor",
    "no tip highlight, uniform color",
    "darker roots grading to bright tips",
]
MOODS = ["pastoral", "wild", "golden", "restless", "tender", "vast", "quiet", "windswept"]


def sample(n: int, seed: int = 1) -> list[dict]:
    rng = random.Random(seed)
    return [{
        "id": f"vegetation-{i:03d}",
        "character": rng.choice(CHARACTER),
        "density": rng.choice(DENSITY),
        "wind": rng.choice(WIND),
        "tips": rng.choice(TIPS),
        "mood": ", ".join(rng.sample(MOODS, 2)),
    } for i in range(n)]


def brief_text(b: dict) -> str:
    return (f"Grass: {b['character']}. Density: {b['density']}. Wind: {b['wind']}. "
            f"Tips: {b['tips']}. Mood: {b['mood']}.")
