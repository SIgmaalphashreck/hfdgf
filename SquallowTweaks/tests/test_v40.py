"""Redesign: Themes (Persistenz, Kontrast), Hardware-Parser, Tweak-Katalog unveraendert. Qt-frei."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import hwinfo  # noqa: E402
import themes  # noqa: E402
from _tl import tl  # noqa: E402


class ThemeTests(unittest.TestCase):
    def test_all_themes_present_and_valid(self):
        self.assertEqual(set(themes.ORDER), set(themes.THEMES))
        self.assertEqual(len(themes.ORDER), 11)
        fxs = [themes.THEMES[k].fx for k in themes.ORDER]
        self.assertEqual(len(set(fxs)), len(fxs), "jedes Theme braucht einen eigenen Effekt")
        for k, p in themes.THEMES.items():
            for f in ("bg", "card", "text", "accent", "accent2", "accent3", "border", "muted"):
                self.assertTrue(themes.valid_hex(getattr(p, f)), (k, f))
            self.assertGreaterEqual(themes.contrast(p.text, p.bg), 7, k)
            self.assertGreaterEqual(themes.contrast(p.text, p.card), 7, k)
            self.assertGreaterEqual(themes.contrast(p.on_accent, p.accent), 4.5, k)
            self.assertIn(p.fx, themes.FX_FPS)

    def test_purple_is_original_look(self):
        p = themes.THEMES["purple"]
        self.assertEqual((p.bg, p.card, p.accent, p.accent2), ("#0A0A10", "#13131D", "#8B7CF6", "#B89CFF"))

    def test_persistence_roundtrip_and_corruption(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "ui.json"
            s = themes.SettingsStore(f)
            self.assertEqual(s["theme"], "purple")
            s["theme"] = "green"
            s["custom_accent"] = "#112233"
            s["effects"] = False
            s2 = themes.SettingsStore(f)
            self.assertEqual((s2["theme"], s2["custom_accent"], s2["effects"]), ("green", "#112233", False))
            self.assertEqual(s2.palette().key, "green")
            f.write_text("{kaputt", encoding="utf-8")
            self.assertEqual(themes.SettingsStore(f)["theme"], "purple")
            f.write_text(json.dumps({"theme": "nope", "custom_accent": "rot", "effects": 3}), encoding="utf-8")
            s3 = themes.SettingsStore(f)
            self.assertEqual((s3["theme"], s3["custom_accent"], s3["effects"]), ("purple", "#8B7CF6", True))

    def test_custom_and_chromatic(self):
        self.assertTrue(themes.valid_hex(themes.custom_palette("#000000").accent))
        self.assertNotEqual(themes.custom_palette("#000000").accent, "#000000")
        self.assertEqual(themes.resolve("custom", "#FF0000").accent, "#FF0000")
        self.assertNotEqual(themes.chromatic_at(0).accent, themes.chromatic_at(120).accent)
        live = themes.make_palette("x", "X", bg="#000000", card="#111111", accent="#FF0000", accent2="#FF8888",
                                   accent3="#880000", fx="glass")
        pal = themes.THEMES["blue"]
        before = id(pal)
        pal.apply(live)
        self.assertEqual(pal.accent, "#FF0000")
        self.assertEqual(id(pal), before)
        pal.apply(themes._build()["blue"])


class HwTests(unittest.TestCase):
    def test_cpu_name_from_registry(self):
        self.assertEqual(hwinfo.cpu_name(lambda p, n: "11th Gen  Intel(R) Core(TM) i7-11800H @ 2.30GHz\x00"),
                         "11th Gen Intel(R) Core(TM) i7-11800H @ 2.30GHz")
        def boom(p, n):
            raise OSError
        self.assertIsNone(hwinfo.cpu_name(boom))

    def test_gpu_prefers_dedicated(self):
        vals = {"0000": {"DriverDesc": "Intel(R) UHD Graphics", "HardwareInformation.qwMemorySize": 1 << 30},
                "0001": {"DriverDesc": "NVIDIA GeForce RTX 3060 Laptop GPU", "HardwareInformation.qwMemorySize": (6 << 30).to_bytes(8, "little"), "DriverVersion": "31.0.15"},
                "0002": {"DriverDesc": "Microsoft Basic Display Adapter"}}
        def read(path, name):
            return vals[path.rsplit("\\", 1)[1]][name]
        ad = hwinfo.gpu_adapters(read, lambda p: ["0000", "0001", "0002", "Properties"])
        self.assertEqual([a["name"] for a in ad], ["NVIDIA GeForce RTX 3060 Laptop GPU", "Intel(R) UHD Graphics"])
        self.assertEqual(ad[0]["vram"], 6 << 30)

    def test_parse_lhm(self):
        js = json.dumps({"src": "LibreHardwareMonitor", "hw": [
            {"n": "Core #1", "i": "/intelcpu/0/temperature/0", "v": 50}, {"n": "CPU Package", "i": "/intelcpu/0/temperature/4", "v": 61.0},
            {"n": "GPU Core", "i": "/gpu-nvidia/0/temperature/0", "v": 47}, {"n": "Bad", "i": "/intelcpu/0/temperature/9", "v": 0}]})
        r = hwinfo.parse_temps(js)
        self.assertEqual(r["cpu"], (61.0, "LibreHardwareMonitor"))
        self.assertEqual(r["gpu"], (47.0, "LibreHardwareMonitor"))

    def test_parse_acpi_and_garbage(self):
        r = hwinfo.parse_temps(json.dumps({"acpi": [{"n": "TZ0", "v": 27.8}, {"n": "TZ1", "v": 45.2}]}))
        self.assertEqual(r["cpu"], (45.2, "ACPI"))
        self.assertIsNone(r["gpu"])
        for bad in ("", "x", "[]", json.dumps({"acpi": [{"n": "a", "v": -273.15}, {"n": "b", "v": 900}]})):
            self.assertEqual(hwinfo.parse_temps(bad), {"cpu": None, "gpu": None})

    def test_monitor_snapshot_never_invents(self):
        m = hwinfo.HwMonitor(runner=lambda a, t: (1, "fehler"), cpu_reader=lambda p, n: (_ for _ in ()).throw(OSError()),
                             gpu_reader=lambda p, n: (_ for _ in ()).throw(OSError()), gpu_subkeys=lambda p: [])
        snap = m.snapshot()
        self.assertIsNone(snap["cpu_name"])
        self.assertIsNone(snap["gpu_name"])
        self.assertIsNone(snap["cpu_temp"])
        self.assertIsNone(snap["gpu_temp"])


class CatalogUnchanged(unittest.TestCase):
    def test_catalog_matches_snapshot(self):
        snap = Path("/home/claude/orig/catalog_snapshot.json")
        if not snap.exists():
            self.skipTest("kein Vorher-Snapshot")
        now = {t.id: [t.id, t.name, t.kind, repr(t.values)] for t in tl.build_catalog()}
        for row in json.loads(snap.read_text()):       # alle urspruenglichen Tweaks unveraendert; neue sind nur dazugekommen
            self.assertEqual(now[row[0]], row)


if __name__ == "__main__":
    unittest.main()


class NewTweaksRoundtrip(unittest.TestCase):
    """Neue Registry-Tweaks: anwenden -> aktiv -> zurueck auf den Ursprung (fehlende Werte werden wieder geloescht)."""

    def test_apply_and_undo(self):
        with tempfile.TemporaryDirectory() as d:
            reg = tl.MemoryBackend()
            engine = tl.TweakEngine(reg, Path(d) / "s.json", runner=lambda a: (0, ""), admin_check=lambda: True)
            by = {t.id: t for t in tl.build_catalog()}
            for tid in ("fn_cpu_prio", "gamebar_off", "hags_on", "mpo_off", "mitigations_off"):
                t = by[tid]
                before = [reg.read(v.path, v.name) for v in t.values]
                self.assertTrue(engine.apply(t).ok, tid)
                self.assertEqual(engine.status(t)[0], tl.STATUS_ACTIVE, tid)
                self.assertTrue(engine.undo(t).ok, tid)
                self.assertEqual([reg.read(v.path, v.name) for v in t.values], before, tid)
                self.assertNotEqual(engine.status(t)[0], tl.STATUS_ACTIVE, tid)

    def test_maxfps_profile_is_larger_and_covers_laptops(self):
        with tempfile.TemporaryDirectory() as d:
            engine = tl.TweakEngine(tl.MemoryBackend(), Path(d) / "s.json", runner=lambda a: (0, ""), admin_check=lambda: True)
            cat = tl.build_catalog()
            ctx = {"desktop": False, "fortnite_config": False, "fortnite_running": False, "admin": True}
            comp, _ = tl.select_for_profile(cat, engine, ctx, "competitive")
            mx, _ = tl.select_for_profile(cat, engine, ctx, "maxfps")
            self.assertGreater(len(mx), len(comp))
            self.assertIn("power_ultimate", {t.id for t in mx})      # Notebook: trotzdem enthalten (desktop-gated)
            self.assertNotIn("power_ultimate", {t.id for t in comp})
            self.assertNotIn("mitigations_off", {t.id for t in mx})  # Sicherheits-Kompromisse bleiben manuell
            self.assertNotIn("hags_on", {t.id for t in mx})
