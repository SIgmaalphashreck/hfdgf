"""SquallowTweaks - Themes (Qt-frei, daher einzeln testbar).

Ein Theme besteht aus wenigen Basisfarben; alle uebrigen Flaechen-/Rahmenfarben werden daraus abgeleitet.
Jedes Theme hat zusaetzlich einen eigenen Hintergrund-Effekt (`fx`), der in fx.py gezeichnet wird.
Die Auswahl wird in ui_settings.json gespeichert (getrennt von tweak_state.json, die Tweak-Logik bleibt unberuehrt).
"""
from __future__ import annotations

import colorsys
import json
import os
import re
from dataclasses import dataclass, fields
from pathlib import Path

HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
DEFAULT_THEME = "purple"
DEFAULT_CUSTOM = "#8B7CF6"


# ---------------------------------------------------------------------------
# Farb-Helfer (reine Strings, kein Qt)
# ---------------------------------------------------------------------------
def to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def to_hex(r: float, g: float, b: float) -> str:
    return "#{:02X}{:02X}{:02X}".format(*(max(0, min(255, int(round(v)))) for v in (r, g, b)))


def mix(a: str, b: str, t: float) -> str:
    """Mischt a -> b; t=0 ergibt a, t=1 ergibt b."""
    t = max(0.0, min(1.0, t))
    ra, rb = to_rgb(a), to_rgb(b)
    return to_hex(*(ra[i] + (rb[i] - ra[i]) * t for i in range(3)))


def luminance(h: str) -> float:
    def ch(v: int) -> float:
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = to_rgb(h)
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def shift_hue(h: str, degrees: float, sat: float | None = None, val: float | None = None) -> str:
    r, g, b = (c / 255 for c in to_rgb(h))
    hh, ss, vv = colorsys.rgb_to_hsv(r, g, b)
    hh = (hh + degrees / 360.0) % 1.0
    if sat is not None:
        ss = sat
    if val is not None:
        vv = val
    return to_hex(*(c * 255 for c in colorsys.hsv_to_rgb(hh, ss, vv)))


def valid_hex(value) -> bool:
    return isinstance(value, str) and bool(HEX_RE.match(value))


# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------
@dataclass
class Palette:
    key: str
    name: str
    fx: str
    light: bool
    bg: str
    sidebar: str
    card: str
    card2: str
    border: str
    border_hi: str
    text: str
    muted: str
    dim: str
    accent: str
    accent2: str
    accent3: str
    on_accent: str
    btn_a: str
    btn_a_h: str
    btn_b: str
    btn_b_h: str
    ghost_hover: str
    chip_on: str
    nav_a: str
    nav_b: str
    nav_hover: str
    hero: str
    hero_hover: str
    hero_border: str
    track: str
    grid: str
    handle: str
    handle_hover: str
    input_focus: str
    tip_bg: str
    tip_border: str
    toggle_off: str
    toggle_off_h: str
    disabled: str
    card_alpha: int
    sidebar_alpha: int

    def apply(self, other: "Palette") -> None:
        """Uebernimmt alle Werte in-place, damit Referenzen auf das globale PAL gueltig bleiben."""
        for f in fields(Palette):
            setattr(self, f.name, getattr(other, f.name))


def make_palette(key: str, name: str, *, bg: str, card: str, accent: str, accent2: str, accent3: str, fx: str,
                 light: bool = False, card_alpha: int = 255, sidebar_alpha: int = 255) -> Palette:
    if light:
        text = "#14141F"
        sidebar = mix(bg, "#FFFFFF", 0.55)
        card2 = mix(card, accent, 0.07)
        border = mix(card, text, 0.12)
        muted = mix(text, bg, 0.42)
        dim = mix(text, bg, 0.58)
    else:
        text = mix("#FFFFFF", accent, 0.05)
        sidebar = mix(bg, card, 0.45)
        card2 = mix(card, accent, 0.11)
        border = mix(card, text, 0.10)
        muted = mix(text, bg, 0.45)
        dim = mix(text, bg, 0.64)
    on_accent = max(("#0B0B12", "#FFFFFF"), key=lambda c: contrast(c, accent))     # besser lesbare Schrift auf Akzentflaechen
    black = "#000000"
    return Palette(
        key=key, name=name, fx=fx, light=light, bg=bg, sidebar=sidebar, card=card, card2=card2, border=border,
        border_hi=mix(border, accent, 0.55), text=text, muted=muted, dim=dim, accent=accent, accent2=accent2,
        accent3=accent3, on_accent=on_accent,
        btn_a=mix(accent, black, 0.10), btn_a_h=accent, btn_b=mix(accent2, black, 0.08), btn_b_h=accent2,
        ghost_hover=mix(card2, accent, 0.16), chip_on=mix(card, accent, 0.26),
        nav_a=mix(card, accent, 0.32 if not light else 0.18), nav_b=mix(card, accent, 0.12 if not light else 0.07),
        nav_hover=mix(card, accent, 0.18 if not light else 0.10),
        hero=mix(card, accent, 0.14 if not light else 0.06), hero_hover=mix(card, accent, 0.20 if not light else 0.10),
        hero_border=mix(border, accent, 0.40),
        track=mix(card, text, 0.08) if light else mix(card, bg, 0.45), grid=mix(bg, text, 0.07 if not light else 0.10),
        handle=mix(bg, text, 0.16), handle_hover=mix(bg, accent, 0.55),
        input_focus=mix(card, accent, 0.06), tip_bg=card2, tip_border=mix(card2, accent, 0.35),
        toggle_off=mix(card2, text, 0.10), toggle_off_h=mix(card2, text, 0.18),
        disabled=mix(card, text, 0.12), card_alpha=card_alpha, sidebar_alpha=sidebar_alpha)


def _chromatic(hue: float) -> Palette:
    """Chromatic: gleiche dunkle Basis, Akzentfarben laufen langsam durch den Farbkreis."""
    a = shift_hue("#FF4D8D", hue, sat=0.72, val=1.0)
    return make_palette("chromatic", "Chromatic", bg="#09090E", card="#131319", accent=a,
                        accent2=shift_hue(a, 38, sat=0.55, val=1.0), accent3=shift_hue(a, 85, sat=0.75, val=1.0),
                        fx="chroma", card_alpha=244, sidebar_alpha=236)


def chromatic_at(hue: float) -> Palette:
    return _chromatic(hue % 360.0)


def custom_palette(accent: str) -> Palette:
    accent = accent if valid_hex(accent) else DEFAULT_CUSTOM
    if luminance(accent) < 0.05:          # fast schwarz waere auf dunklem Grund unsichtbar
        accent = mix(accent, "#FFFFFF", 0.45)
    return make_palette("custom", "Custom", bg="#0A0A10", card="#13131D", accent=accent,
                        accent2=mix(accent, "#FFFFFF", 0.35), accent3=shift_hue(accent, 40, sat=0.65, val=0.95),
                        fx="glow", card_alpha=248, sidebar_alpha=240)


def _build() -> dict[str, Palette]:
    t = {}
    t["black"] = make_palette("black", "Black", bg="#08080B", card="#121216", accent="#C7CCD8", accent2="#FFFFFF",
                              accent3="#7B8296", fx="glass", card_alpha=232, sidebar_alpha=228)
    t["white"] = make_palette("white", "White", bg="#E9ECF3", card="#FFFFFF", accent="#4F5BFF", accent2="#7B86FF",
                              accent3="#9B7BFF", fx="bloom", light=True, card_alpha=246, sidebar_alpha=225)
    t["pink"] = make_palette("pink", "Pink", bg="#0E0811", card="#1A0F1E", accent="#FF3FA4", accent2="#FF7AC6",
                             accent3="#C04BFF", fx="neon", card_alpha=240, sidebar_alpha=232)
    # Purple = bisheriges Squallow-Design (identische Farbwerte wie vor dem Redesign)
    t["purple"] = make_palette("purple", "Purple", bg="#0A0A10", card="#13131D", accent="#8B7CF6", accent2="#B89CFF",
                               accent3="#5EEAD4", fx="energy", card_alpha=244, sidebar_alpha=236)
    t["green"] = make_palette("green", "Green", bg="#040A06", card="#0B150E", accent="#22E06B", accent2="#7DFF9E",
                              accent3="#00B88A", fx="matrix", card_alpha=238, sidebar_alpha=228)
    t["blue"] = make_palette("blue", "Blue", bg="#060B14", card="#0C1626", accent="#3D8BFF", accent2="#7DB7FF",
                             accent3="#38D6FF", fx="holo", card_alpha=240, sidebar_alpha=232)
    t["red"] = make_palette("red", "Red", bg="#0D0707", card="#181010", accent="#FF3B3B", accent2="#FF7A6B",
                            accent3="#FF8A3D", fx="pulse", card_alpha=242, sidebar_alpha=234)
    t["cyan"] = make_palette("cyan", "Cyan", bg="#050D10", card="#0A171C", accent="#1FE0F0", accent2="#7DF3FF",
                             accent3="#3A8DFF", fx="electric", card_alpha=240, sidebar_alpha=232)
    t["midnight"] = make_palette("midnight", "Midnight", bg="#04050D", card="#0B0D1D", accent="#7C8BFF",
                                 accent2="#B4BDFF", accent3="#C084FC", fx="galaxy", card_alpha=232, sidebar_alpha=222)
    t["chromatic"] = _chromatic(0.0)
    t["custom"] = custom_palette(DEFAULT_CUSTOM)
    return t


THEMES: dict[str, Palette] = _build()
ORDER = ("black", "white", "pink", "purple", "green", "blue", "red", "cyan", "midnight", "chromatic", "custom")

# Zeichenrate je Effekt (Bilder/Sekunde). Langsame Effekte brauchen nur wenige Bilder -> geringe CPU-Last.
FX_FPS = {"glass": 8, "bloom": 10, "neon": 15, "energy": 20, "matrix": 15, "holo": 15, "pulse": 15, "electric": 15,
          "galaxy": 10, "chroma": 12, "glow": 10}


def resolve(key: str, custom_accent: str = DEFAULT_CUSTOM) -> Palette:
    if key == "custom":
        return custom_palette(custom_accent)
    return THEMES.get(key) or THEMES[DEFAULT_THEME]


# Globales, lebendes Palette-Objekt: Widgets lesen beim Zeichnen PAL.<feld>
PAL: Palette = make_palette("purple", "Purple", bg="#0A0A10", card="#13131D", accent="#8B7CF6", accent2="#B89CFF",
                            accent3="#5EEAD4", fx="energy", card_alpha=244, sidebar_alpha=236)


# ---------------------------------------------------------------------------
# Einstellungen speichern
# ---------------------------------------------------------------------------
def default_path() -> Path:
    base = os.environ.get("LOCALAPPDATA", str(Path.home() / ".local" / "share"))
    return Path(base) / "SquallowTweaks" / "ui_settings.json"


DEFAULTS = {"theme": DEFAULT_THEME, "custom_accent": DEFAULT_CUSTOM, "effects": True}


class SettingsStore:
    """Kleine JSON-Datei; fehlerhafte oder fehlende Dateien fuehren zu Standardwerten (nie zu einem Absturz)."""

    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else default_path()
        self.data = self._load()

    def _load(self) -> dict:
        data = dict(DEFAULTS)
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                if raw.get("theme") in THEMES:
                    data["theme"] = raw["theme"]
                if valid_hex(raw.get("custom_accent")):
                    data["custom_accent"] = raw["custom_accent"].upper()
                if isinstance(raw.get("effects"), bool):
                    data["effects"] = raw["effects"]
        except Exception:  # noqa: BLE001
            pass
        return data

    def save(self) -> bool:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.data, indent=1), encoding="utf-8")
            os.replace(tmp, self.path)
            return True
        except Exception:  # noqa: BLE001
            return False

    def __getitem__(self, k):
        return self.data[k]

    def __setitem__(self, k, v):
        self.data[k] = v
        self.save()

    def palette(self) -> Palette:
        return resolve(self.data["theme"], self.data["custom_accent"])
