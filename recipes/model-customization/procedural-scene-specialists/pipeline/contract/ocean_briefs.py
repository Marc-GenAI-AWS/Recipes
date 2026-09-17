"""Held-out ocean-layer brief sampler (seastate host).

An ocean brief conditions the water's *character* — sea state, wave shape, colour, foam, surface light — not the per-state
palette (that comes from the host's presets/uniforms). Seeded, so the eval set is reproducible; seed 1 is held out.
"""
from __future__ import annotations

import random

SEA_STATE = [
    "a near-glassy calm with only a long low swell",
    "a light breeze chop over a gentle swell",
    "a moderate sea with clear wave trains",
    "a rough sea with steep short-period waves",
    "a heavy gale sea, big breaking crests",
    "a confused cross-sea from two swell directions",
]
WAVES = [
    "long smooth rollers with rounded crests",
    "sharp choppy peaks with visible facets",
    "wind-driven waves leaning downwind",
    "broad low swells with fine ripples riding on them",
    "steep crests that curl and break at the top",
]
WATER = [
    "deep ink-blue water with teal in the thin crests",
    "cold slate-grey water, almost colourless",
    "dark green-black water with a peaty cast",
    "tropical blue shading to turquoise where the light passes through",
    "storm-grey water streaked with paler upwelling",
]
FOAM = [
    "white caps scattered on the biggest crests",
    "long wind-blown foam streaks lying downwind",
    "heavy breaking foam with a lingering trail",
    "almost no foam — only a faint lace on the crests",
    "patchy foam gathering in the troughs",
]
LIGHT = [
    "a hard specular glitter path under the sun",
    "a broad soft sheen with no distinct sun path",
    "backlit crests glowing where the light passes through the water",
    "flat overcast light with a dull satin surface",
    "low-angle light raking across the wave faces",
]
MOODS = [
    "vast", "menacing", "serene", "cold", "restless", "luminous",
    "bleak", "glittering", "heavy", "clean",
]


def sample(n: int, seed: int = 1) -> list[dict]:
    rng = random.Random(seed)
    return [{
        "id": f"ocean-{i:03d}",
        "sea_state": rng.choice(SEA_STATE),
        "waves": rng.choice(WAVES),
        "water": rng.choice(WATER),
        "foam": rng.choice(FOAM),
        "light": rng.choice(LIGHT),
        "mood": ", ".join(rng.sample(MOODS, 2)),
    } for i in range(n)]


def brief_text(b: dict) -> str:
    return (f"Sea: {b['sea_state']}. Waves: {b['waves']}. Water: {b['water']}. "
            f"Foam: {b['foam']}. Light: {b['light']}. Mood: {b['mood']}.")
