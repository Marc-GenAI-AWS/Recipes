"""Held-out sky-layer brief sampler (Phase 1).

A sky brief conditions the sky-dome *technique/character* — cloud type, sun
treatment, extra atmosphere — not the per-state palette (that comes from the
host's uniforms). Diversity here is the single biggest lever (a sky trained only
on clear noon won't do overcast dusk). Seeded, so the eval set is reproducible.
"""
from __future__ import annotations

import random

CLOUDS = [
    "a clear high-altitude sky, almost cloudless",
    "scattered fair-weather cumulus drifting on the wind",
    "towering cumulus congestus building over the peaks",
    "a low stratus overcast with a soft luminous base",
    "high wispy cirrus streaks catching the sun",
    "broken cloud with bright sun-breaks between",
    "a heavy storm shelf shutting the upper sky",
    "dawn fog banks burning off into a thin haze",
]
SUNS = [
    "a crisp small sun disc with a tight warm glow",
    "a diffuse sun smeared through haze, no hard disc",
    "a bright hard sun with a lens-like bloom halo",
    "no visible disc — only a broad directional sky glow",
    "a low sun with a wide soft halo ring",
]
EXTRAS = [
    "crepuscular rays fanning faintly from the sun's direction",
    "a subtle sun halo ring",
    "wind-torn ragged cloud edges",
    "two cloud decks at different depths for parallax",
    "a scatter of stars where the sky darkens (read uStars)",
    "gentle dithering so the gradient never bands",
    "a warm horizon glow band separate from the zenith",
]
MOODS = [
    "crisp", "brooding", "serene", "vast", "cold", "golden", "windswept",
    "hazy", "luminous", "austere", "restless", "tender",
]


def sample(n: int, seed: int = 1) -> list[dict]:
    rng = random.Random(seed)
    out = []
    for i in range(n):
        b = {
            "id": f"sky-{i:03d}",
            "clouds": rng.choice(CLOUDS),
            "sun": rng.choice(SUNS),
            "extras": rng.sample(EXTRAS, rng.randint(0, 2)),
            "mood": ", ".join(rng.sample(MOODS, rng.randint(2, 3))),
        }
        out.append(b)
    return out


def brief_text(b: dict) -> str:
    parts = [f"Clouds: {b['clouds']}.", f"Sun: {b['sun']}."]
    if b["extras"]:
        parts.append("Also: " + "; ".join(b["extras"]) + ".")
    parts.append(f"Mood: {b['mood']}.")
    return " ".join(parts)


if __name__ == "__main__":
    import sys
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    for b in sample(n):
        print(b["id"], "—", brief_text(b))
