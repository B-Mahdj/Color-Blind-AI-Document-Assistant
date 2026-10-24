"""Simulation and conservative color checks; these are not certification scores."""

import re

import numpy as np
from daltonlens import simulate
from PIL import Image

_SIMULATOR = simulate.Simulator_Vienot1999()


def parse_hex(value: str) -> tuple[float, float, float]:
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        raise ValueError("Colors must be six-digit hexadecimal RGB values.")
    return tuple(int(value[i:i + 2], 16) / 255 for i in (1, 3, 5))


def hex_color(rgb) -> str:
    return "#" + "".join(f"{round(min(1, max(0, c)) * 255):02X}" for c in rgb)


def simulated_image(image: Image.Image) -> Image.Image:
    pixels = np.asarray(image.convert("RGB"), dtype=np.uint8)
    result = _SIMULATOR.simulate_cvd(pixels, simulate.Deficiency.PROTAN, severity=1.0)
    return Image.fromarray(result)


def simulated_rgb(rgb) -> np.ndarray:
    pixel = np.asarray([[np.round(np.asarray(rgb) * 255)]], dtype=np.uint8)
    return _SIMULATOR.simulate_cvd(pixel, simulate.Deficiency.PROTAN, severity=1.0)[0, 0] / 255.0


def separation(first, second) -> float:
    # shortcut: simulated RGB distance is only a ranking heuristic, not a perception threshold.
    return float(np.linalg.norm(simulated_rgb(first) - simulated_rgb(second)))


def luminance(rgb) -> float:
    rgb = np.asarray(rgb, dtype=float)
    linear = np.where(rgb <= .04045, rgb / 12.92, ((rgb + .055) / 1.055) ** 2.4)
    return float(linear @ np.array([.2126, .7152, .0722]))


def contrast(first, second) -> float:
    light, dark = sorted((luminance(first), luminance(second)), reverse=True)
    return (light + .05) / (dark + .05)


def color_metrics(pairs: list[tuple]) -> dict:
    pairs = list(dict.fromkeys((tuple(before), tuple(after)) for before, after in pairs))
    if len(pairs) < 2:
        return {"minimum_separation_before": None, "minimum_separation_after": None}
    old, new = [], []
    for i, (before, after) in enumerate(pairs):
        for other_before, other_after in pairs[i + 1:]:
            if hex_color(before) != hex_color(other_before):
                old.append(separation(before, other_before))
                new.append(separation(after, other_after))
    return {
        "minimum_separation_before": round(min(old), 4) if old else None,
        "minimum_separation_after": round(min(new), 4) if new else None,
    }
