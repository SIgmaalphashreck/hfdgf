"""SquallowTweaks - Seiten Teil 1: Gemeinsames, Dashboard, Tweaks, Fortnite, Benchmark."""
from __future__ import annotations

import time
import webbrowser
from collections import deque

import psutil
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QApplication, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QProgressBar, QVBoxLayout, QWidget)

import catalog
import engine as eng
import fnmon
import netlab
import service as svc
from themes import PAL
from ui_common import (BUS, CYAN, GREEN, PINK, RED, YELLOW, AnimButton, Card, Chips, DiscordCard, HeroStat, HwCard, IconButton,
                       LineChart, OrbBanner, RingGauge, StatTile, TempMonitorCard, Toggle, TweakRow, label, pill)


def page_layout(widget: QWidget, title: str, subtitle: str = "") -> QVBoxLayout:
    lay = QVBoxLayout(widget)
    lay.setContentsMargins(32, 26, 32, 24)
    lay.setSpacing(14)
    head = QVBoxLayout()
    head.setSpacing(2)
    head.addWidget(label(title, "h1"))
    if subtitle:
        head.addWidget(label(subtitle, "muted"))
    lay.addLayout(head)
    return lay


class BasePage(QWidget):
    navigate = Signal(str)


# ===========================================================================
TEMP_TIPS = {"ACPI": "Quelle: ACPI-Thermalzone des Mainboards (Firmware-Sensor, kann vom CPU-Kern abweichen).",
             "LibreHardwareMonitor": "Quelle: LibreHardwareMonitor", "OpenHardwareMonitor": "Quelle: OpenHardwareMonitor",
             "psutil": "Quelle: Betriebssystem-Sensor"}
TEMP_MISSING_TIP = ("Windows stellt ohne Sensor-Treiber keine verlässliche Temperatur bereit. "
                    "Läuft LibreHardwareMonitor im Hintergrund, erscheint der Wert hier automatisch.")


def fmt_temp(value, src):
    """(Text, Tooltip). Ohne gelesenen Wert gibt es keinen Text -> die Karte zeigt 'Nicht verfügbar'."""
    if value is None:
        return None, TEMP_MISSING_TIP
    text = f"{value:.0f} °C" + (" · ACPI" if src == "ACPI" else "")
    return text, TEMP_TIPS.get(src or "", "")


def fmt_uptime(seconds: float) -> str:
    seconds = max(0, int(seconds))
    d, rest = divmod(seconds, 86400)
    h, rest = divmod(rest, 3600)
    return (f"{d}d " if d else "") + f"{h}h {rest // 60:02d}m"


class DashboardPage(BasePage):
    """Dashboard nach dem Vorbild-Screenshot: Top-Leiste, Hero mit Kennzahlen, Live-Karten, Discord-Karte, Temperatur-Monitor."""
    search_requested = Signal(str)

    CHECKS = (("Energieplan Höchstleistung", ("power_ultimate", "power_high"), "any"), ("CPU-Takt dauerhaft oben", ("ps_min_cpu",), "all"),
              ("Fortnite-Grafik auf Leistung", ("fn_graphics_perf",), "all"), ("Vollbild & Latenz", ("fn_fullscreen", "fso_global"), "all"),
              ("LAN-Adapter stabil", ("net_adapter_stable",), "all"), ("Game DVR aus", ("game_dvr",), "all"))

    def __init__(self, service: svc.Service):
        super().__init__()
        self.service = service
        self.mode = "Live"
        self.hist = {"cpu": deque(maxlen=60), "gpu": deque(maxlen=60), "ram": deque(maxlen=60)}
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 20, 28, 24)
        lay.setSpacing(16)

        # --- Top-Leiste: Suche links, Settings-Button + Max-FPS-Button oben rechts
        bar = QHBoxLayout()
        bar.setSpacing(10)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Tweaks suchen …")
        self.search.setFixedWidth(340)
        self.search.setFixedHeight(42)
        self.search.returnPressed.connect(lambda: self.search_requested.emit(self.search.text()))
        bar.addWidget(self.search)
        bar.addStretch(1)
        self.settings_btn = IconButton("gear", "Einstellungen öffnen")
        self.settings_btn.clicked.connect(lambda: self.navigate.emit("Einstellungen"))
        bar.addWidget(self.settings_btn)
        self.max_btn = AnimButton("Max-FPS-Optimierung", "accent")
        self.max_btn.setToolTip("Wendet alle passenden Tweaks für maximale FPS an (Profil Max FPS).")
        self.max_btn.clicked.connect(lambda: self.auto("maxfps"))
        bar.addWidget(self.max_btn)
        lay.addLayout(bar)

        # --- Hero: Begruessung links, drei Kennzahlen rechts
        hero = OrbBanner()
        h = QHBoxLayout(hero)
        h.setContentsMargins(30, 24, 24, 24)
        h.setSpacing(28)
        col = QVBoxLayout()
        col.setSpacing(6)
        badge = QHBoxLayout()
        badge.addWidget(pill("ADMIN-MODUS" if service.admin else "OHNE ADMIN", GREEN if service.admin else RED))
        badge.addStretch(1)
        col.addLayout(badge)
        self.headline = label("Willkommen bei SquallowTweaks", "h1")
        self.headline.setStyleSheet("font-size:32px;font-weight:800;")
        col.addWidget(self.headline)
        self.subline = label("Messe dein System …", "muted", True)
        col.addWidget(self.subline)
        col.addSpacing(10)
        btns = QHBoxLayout()
        btns.setSpacing(10)
        auto = AnimButton("Ein-Klick-Optimierung", "accent")
        auto.clicked.connect(lambda: self.auto("competitive"))
        btns.addWidget(auto)
        scan = AnimButton("System-Scan", "ghost")
        scan.setToolTip("Liest den Zustand aller Tweaks neu aus.")
        scan.clicked.connect(self.scan)
        btns.addWidget(scan)
        btns.addStretch(1)
        col.addLayout(btns)
        col.addStretch(1)
        h.addLayout(col, 1)
        stats = QVBoxLayout()
        stats.setSpacing(10)
        self.stat_applied = HeroStat("bolt", "APPLIED TWEAKS", "@accent2", bar=True)
        self.stat_uptime = HeroStat("clock", "BETRIEBSZEIT", "@accent2")
        self.stat_score = HeroStat("check", "OPTIMIERUNGS-SCORE", "@accent2")
        for w in (self.stat_applied, self.stat_uptime, self.stat_score):
            stats.addWidget(w)
        wrap = QWidget()
        wrap.setFixedWidth(290)
        wrap.setLayout(stats)
        h.addWidget(wrap)
        lay.addWidget(hero)

        # --- Live-Systemwerte (Live / Durchschnitt / Spitze)
        head = QHBoxLayout()
        head.addWidget(label("Live-Systemwerte", "h2"))
        head.addStretch(1)
        self.modes = Chips(["Live", "Ø", "Spitze"], "Live")
        self.modes.changed.connect(self._set_mode)
        head.addWidget(self.modes)
        lay.addLayout(head)
        mid = QHBoxLayout()
        mid.setSpacing(14)
        self.cpu_card = HwCard("CPU", "cpu", ("Kerne / Threads", "Takt", "Temperatur"), "@accent2")
        self.gpu_card = HwCard("GPU", "gpu", ("VRAM", "Treiber", "Temperatur"), CYAN)
        self.ram_card = HwCard("Arbeitsspeicher", "ram", ("Genutzt", "Frei", "Gesamt"), PINK)
        cards = QHBoxLayout()
        cards.setSpacing(14)
        for c in (self.cpu_card, self.gpu_card, self.ram_card):
            cards.addWidget(c, 1)
        mid.addLayout(cards, 3)
        self.discord = DiscordCard()
        mid.addWidget(self.discord, 1)
        lay.addLayout(mid)

        # --- Temperatur-Monitor + Fortnite-Bereitschaft
        low = QHBoxLayout()
        low.setSpacing(14)
        self.monitor = TempMonitorCard(TEMP_MISSING_TIP)
        low.addWidget(self.monitor, 3)
        ready = Card()
        rv = QVBoxLayout(ready)
        rv.setContentsMargins(20, 16, 20, 16)
        rv.setSpacing(8)
        rv.addWidget(label("Fortnite-Bereitschaft", "h2"))
        self.check_labels = []
        for text, _ids, _mode in self.CHECKS:
            l = label("", "muted")
            rv.addWidget(l)
            self.check_labels.append(l)
        rv.addStretch(1)
        fix = AnimButton("Alles beheben", "ghost")
        fix.clicked.connect(lambda: self.auto("competitive"))
        rv.addWidget(fix)
        low.addWidget(ready, 2)
        lay.addLayout(low)

        # --- Netzwerk / Ping / Hintergrundlast / Laufwerk
        tiles = QHBoxLayout()
        tiles.setSpacing(14)
        self.ping = StatTile("Ping (Cloudflare)", GREEN)
        self.net = StatTile("Netzwerk", CYAN)
        self.top = StatTile("Hintergrundlast", YELLOW)
        self.disk = StatTile("Laufwerk", "@accent2")
        for t in (self.ping, self.net, self.top, self.disk):
            tiles.addWidget(t, 1)
        lay.addLayout(tiles)
        lay.addStretch(1)
        service.states_changed.connect(self.refresh_state)
        BUS.changed.connect(self.refresh_state)
        self.refresh_state()

    # ---- Aktionen
    def auto(self, profile: str = "competitive"):
        self.navigate.emit("Tweaks")
        self.service.auto(profile)

    def scan(self):
        self.subline.setText("System wird geprüft …")
        self.service.refresh_states()

    def _set_mode(self, name: str):
        self.mode = name

    def _shown(self, key: str, cur):
        """Live = aktueller Wert, Ø/Spitze = ueber die letzten 60 Messungen."""
        h = self.hist[key]
        if cur is not None:
            h.append(cur)
        if self.mode == "Live" or not h:
            return cur
        return sum(h) / len(h) if self.mode == "Ø" else max(h)

    # ---- Anzeige
    def refresh_state(self):
        known = bool(self.service.states)
        self.stat_applied.set_counts(self.service.active_count() if known else None, len(self.service.catalog))
        sc = self.service.score()
        opened = self.service.open_recommended()
        if sc is None:
            self.stat_score.set_text("–", "wird gelesen")
            self.subline.setText("Status wird gelesen …")
        else:
            self.stat_score.set_text(f"{sc:.0f}", "/ 100")
            self.subline.setText("Alle empfohlenen Tweaks sind aktiv. Dein PC ist startklar." if opened == 0 else
                                 f"{opened} empfohlene Tweaks sind noch nicht aktiv. Ein Klick auf die Ein-Klick-Optimierung erledigt das.")
        for lab, (text, ids, mode) in zip(self.check_labels, self.CHECKS):
            sts = [self.service.states.get(i, (eng.STATUS_UNKNOWN, ""))[0] for i in ids]
            known_s = [s for s in sts if s != eng.STATUS_UNKNOWN]
            if not known_s:
                lab.setText(f"○  {text}  ·  nicht verfügbar")
                lab.setStyleSheet(f"color:{PAL.dim};")
                continue
            ok = any(s == eng.STATUS_ACTIVE for s in known_s) if mode == "any" else all(s == eng.STATUS_ACTIVE for s in known_s)
            lab.setText(("✔  " if ok else "○  ") + text)
            lab.setStyleSheet(f"color:{GREEN};" if ok else f"color:{PAL.muted};")

    def on_sample(self, d: dict):
        hw = d.get("hw") or {}
        gpu = d.get("gpu") or {}
        try:
            self.stat_uptime.set_text(fmt_uptime(time.time() - psutil.boot_time()))
        except Exception:  # noqa: BLE001
            self.stat_uptime.set_text("–")
        # CPU
        cpu_v = self._shown("cpu", d["cpu"])
        self.cpu_card.set_model(hw.get("cpu_name"))
        self.cpu_card.set_usage(f"{cpu_v:.0f}%", d["cpu"])
        phys, logi = psutil.cpu_count(logical=False), psutil.cpu_count()
        cores = f"{phys} / {logi}" if phys and logi else (str(logi) if logi else None)
        freq = d.get("cpu_freq")
        cpu_temp, cpu_tip = fmt_temp(hw.get("cpu_temp"), hw.get("cpu_temp_src"))
        self.cpu_card.set_stats([cores, f"{freq / 1000:.2f} GHz" if freq else None, cpu_temp], [None, None, cpu_tip])
        # GPU: nvidia-smi hat Vorrang, sonst Registry-Name und (falls vorhanden) Sensor eines Hardware-Monitors
        gu = gpu.get("usage")
        gu_v = self._shown("gpu", gu)
        self.gpu_card.set_model(gpu.get("name") or hw.get("gpu_name"))
        self.gpu_card.set_usage(f"{gu_v:.0f}%" if gu_v is not None else None, gu)
        if gpu.get("mem_total"):
            vram = f"{gpu['mem_used'] / 1024:.1f} / {gpu['mem_total'] / 1024:.1f} GB" if gpu.get("mem_used") is not None else f"{gpu['mem_total'] / 1024:.1f} GB"
        else:
            vram = svc.fmt_bytes(hw["gpu_vram"]) if hw.get("gpu_vram") else None
        if gpu.get("temp") is not None:
            gtemp, gtip, gval = fmt_temp(gpu["temp"], "nvidia-smi")[0], "Quelle: nvidia-smi", gpu["temp"]
        else:
            gtemp, gtip = fmt_temp(hw.get("gpu_temp"), hw.get("gpu_temp_src"))
            gval = hw.get("gpu_temp")
        self.gpu_card.set_stats([vram, gpu.get("driver") or hw.get("gpu_driver"), gtemp], [None, None, gtip])
        # RAM
        total, free = d["ram_total"], d.get("ram_free")
        ram_v = self._shown("ram", d["ram"])
        self.ram_card.set_model(f"{svc.fmt_bytes(total)} gesamt")
        self.ram_card.set_usage(f"{ram_v:.0f}%", d["ram"])
        if free is not None:
            self.ram_card.set_stats([svc.fmt_bytes(total - free), svc.fmt_bytes(free), svc.fmt_bytes(total)])
        else:
            self.ram_card.set_stats([svc.fmt_bytes(d["ram_used"]), None, svc.fmt_bytes(total)])
        # Temperatur-Monitor (nur echte Werte, sonst 'Nicht verfügbar')
        self.monitor.push(hw.get("cpu_temp"), gval, TEMP_TIPS.get(hw.get("cpu_temp_src") or "", ""), gtip or "")
        if d.get("disk") is not None:
            self.disk.set(f"{d['disk']:.0f}%", f"{svc.fmt_bytes(d['disk_free'])} frei")
        else:
            self.disk.set("–", "Nicht verfügbar")
        self.net.set(f"↓ {svc.fmt_bytes(d['down'])}/s", f"↑ {svc.fmt_bytes(d['up'])}/s")
        ping = d.get("ping")
        self.ping.set(f"{ping:.0f} ms" if ping is not None else "–", "Antwortzeit zu 1.1.1.1" if ping is not None else "keine Antwort")
        top = d.get("top")
        self.top.set(top[0][:18] if top else "–", f"{top[1]:.0f}% CPU" if top else "")


# ===========================================================================
class TweaksList(QWidget):
    """Zeilen werden einmal gebaut und nur ein-/ausgeblendet (kein Neuaufbau, kein Lag)."""

    def __init__(self, service: svc.Service, tweaks: list, with_filters: bool = True):
        super().__init__()
        self.service = service
        self.rows: dict[str, TweakRow] = {}
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        self.filter, self.query = "Alle", ""
        if with_filters:
            top = QHBoxLayout()
            top.setSpacing(12)
            self.search = QLineEdit()
            self.search.setPlaceholderText("Suchen …")
            self.search.setFixedWidth(220)
            self.search.textChanged.connect(self._q)
            top.addWidget(self.search)
            self.chips = Chips(["Alle", "Empfohlen", "Belegt", "FPS", "Latenz", "Ping", "Aktiv"])
            self.chips.changed.connect(self._f)
            top.addWidget(self.chips, 1)
            lay.addLayout(top)
        box = QVBoxLayout()
        box.setSpacing(8)
        lay.addLayout(box)
        for t in tweaks:
            r = TweakRow(t, service.admin)
            r.toggled.connect(service.set_tweak)
            box.addWidget(r)
            self.rows[t.id] = r
        self.empty = label("Keine Tweaks für diese Auswahl.", "muted")
        self.empty.setAlignment(Qt.AlignCenter)
        box.addWidget(self.empty)
        self.empty.hide()
        service.states_changed.connect(self.sync)
        self.sync()

    def _q(self, text: str):
        self.query = text.strip().lower()
        self.sync()

    def _f(self, name: str):
        self.filter = name
        self.sync()

    def sync(self):
        shown = 0
        for tid, row in self.rows.items():
            t = row.tweak
            st = self.service.states.get(tid, (eng.STATUS_UNKNOWN, ""))
            if tid in self.service.states:
                row.set_state(*st)
            ok = True
            if self.filter == "Empfohlen":
                ok = bool(t.recommended)
            elif self.filter == "Belegt":
                ok = t.evidence == "belegt"
            elif self.filter in ("FPS", "Latenz", "Ping"):
                ok = self.filter.upper() in t.tags
            elif self.filter == "Aktiv":
                ok = st[0] == eng.STATUS_ACTIVE
            if self.query and self.query not in (t.name + " " + t.description + " " + " ".join(t.tags)).lower():
                ok = False
            row.setVisible(ok)
            shown += ok
        self.empty.setVisible(shown == 0)


class TweaksPage(BasePage):
    def __init__(self, service: svc.Service):
        super().__init__()
        self.service = service
        lay = page_layout(self, "Tweaks", "Schalter umlegen, fertig. Jede Änderung wird gesichert, geprüft und lässt sich zurücknehmen.")
        hero = Card("hero")
        h = QHBoxLayout(hero)
        h.setContentsMargins(22, 18, 22, 18)
        h.setSpacing(20)
        left = QVBoxLayout()
        left.setSpacing(4)
        left.addWidget(label("Ein Klick für alles", "h2"))
        self.msg = label("Erkennt dein System und setzt alle passenden Tweaks selbst. Punkte: grün = belegt, gelb = klein, grau = kaum belegt.", "muted", True)
        left.addWidget(self.msg)
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setRange(0, 1000)
        left.addSpacing(6)
        left.addWidget(self.bar)
        h.addLayout(left, 1)
        self.profile = Chips([v[0] for v in catalog.PROFILES.values()], "Competitive")
        h.addWidget(self.profile)
        self.btn = AnimButton("Auto Optimize", "accent")
        self.btn.clicked.connect(self.run_auto)
        h.addWidget(self.btn)
        lay.addWidget(hero)
        if not service.admin:
            locked = sum(1 for t in service.catalog if t.admin)
            ban = Card()
            bl = QHBoxLayout(ban)
            bl.setContentsMargins(18, 12, 18, 12)
            bl.setSpacing(16)
            bl.addWidget(label(f"Ohne Administratorrechte sind {locked} Tweaks gesperrt (Schalter ausgegraut). "
                               "Starte SquallowTweaks als Administrator, um alle zu nutzen.", "muted", True), 1)
            restart = AnimButton("Als Administrator neu starten", "accent")
            restart.clicked.connect(self.restart_admin)
            bl.addWidget(restart)
            lay.addWidget(ban)
        self.list = TweaksList(service, service.catalog)
        lay.addWidget(self.list)
        lay.addStretch(1)
        service.progress.connect(self._progress)
        service.auto_finished.connect(self._finished)

    def restart_admin(self):
        if svc.relaunch_as_admin():
            QApplication.quit()
        else:
            QMessageBox.warning(self, "SquallowTweaks", "Der Neustart als Administrator wurde abgebrochen oder ist nicht möglich.\n"
                                "Starte das Programm per Rechtsklick > 'Als Administrator ausführen'.")

    def run_auto(self):
        key = next(k for k, v in catalog.PROFILES.items() if v[0] == self.profile.current)
        self.btn.setEnabled(False)
        self.bar.setValue(10)
        self.service.auto(key)

    def _progress(self, frac: float, text: str):
        self.bar.setValue(int(frac * 1000))
        self.msg.setText(text)

    def _finished(self, profile, results, skipped, cleaned):
        self.btn.setEnabled(True)
        ok = sum(1 for r in results if r[0])
        bad = [r for r in results if not r[0]]
        txt = f"{ok} Tweaks angewendet" if results else "Alles war schon optimal eingestellt"
        if bad:
            txt += f" · {len(bad)} fehlgeschlagen"
        if ok and any("Neustart" in (self.service.by_id[t].restart or "") for t in self.service.by_id if self.service.engine.has_backup(t)):
            txt += " · Neustart empfohlen"
        self.msg.setText(txt + (f" · {cleaned}" if cleaned else ""))
        if bad:
            QMessageBox.warning(self, "SquallowTweaks", "Nicht alles ließ sich anwenden:\n\n" + "\n".join(f"• {n}: {m}" for _o, n, m in bad))


# ===========================================================================
class FortnitePage(BasePage):
    INGAME = (("Rendering-Modus: Performance", "Der größte FPS- und Latenz-Hebel. Alternativ DirectX 11 (stabiler als DX12)."),
              ("NVIDIA Reflex: An + Boost", "Senkt die System-Latenz. Bei AMD: Radeon Anti-Lag 2."),
              ("Fenstermodus: Vollbild", "Niedrigste Eingabelatenz."),
              ("Schatten aus, Rest niedrig", "Schatten kosten am meisten FPS. Sichtweite hoch lassen."),
              ("Keine Startoption -high", "Kann den Anti-Cheat stören. Die Priorität setzt SquallowTweaks selbst, falls du es willst."))

    def __init__(self, service: svc.Service):
        super().__init__()
        self.service = service
        lay = page_layout(self, "Fortnite", "Config-Tweaks für FPS und Latenz · Fortnite muss dafür beendet sein")
        hero = Card("hero")
        h = QHBoxLayout(hero)
        h.setContentsMargins(22, 18, 22, 18)
        h.setSpacing(20)
        left = QVBoxLayout()
        self.state = label("", "h2")
        self.cfg = label("", "muted", True)
        left.addWidget(self.state)
        left.addWidget(self.cfg)
        pr = QHBoxLayout()
        pr.setSpacing(10)
        self.prio = Toggle()
        self.prio.clicked.connect(lambda c: setattr(self, "prio_on", bool(c)))
        pr.addWidget(self.prio)
        pr.addWidget(label("Priorität HOCH, sobald Fortnite läuft (Standard: aus)", "muted"))
        pr.addStretch(1)
        left.addLayout(pr)
        h.addLayout(left, 1)
        self.btn = AnimButton("Fortnite optimieren", "accent")
        self.btn.clicked.connect(self.optimize)
        h.addWidget(self.btn)
        lay.addWidget(hero)
        lay.addWidget(label("Im Spiel einstellen", "h2"))
        card = Card()
        cv = QVBoxLayout(card)
        cv.setContentsMargins(20, 14, 20, 14)
        cv.setSpacing(6)
        for t, d in self.INGAME:
            row = QHBoxLayout()
            row.addWidget(label("▸", "muted"))
            row.addWidget(label(t, "h2"))
            row.addWidget(label(d, "muted"), 1)
            cv.addLayout(row)
        cv.addWidget(label("Diese Optionen liegen nur im Spiel; SquallowTweaks setzt nichts, was es nicht sicher prüfen kann.", "dim", True))
        lay.addWidget(card)
        lay.addWidget(label("Config & Windows für Fortnite", "h2"))
        fn_tweaks = [t for t in service.catalog if catalog.F in t.categories]
        lay.addWidget(TweaksList(service, fn_tweaks, with_filters=False))
        bench = AnimButton("Messung vorher/nachher starten", "ghost")
        bench.clicked.connect(lambda: self.navigate.emit("Benchmark"))
        lay.addWidget(bench, 0, Qt.AlignLeft)
        lay.addStretch(1)
        self.prio_on = False
        self.refresh()

    def refresh(self):
        ini = eng.fortnite_ini_path()
        self.cfg.setText("Config gefunden." if ini.exists() else "Keine GameUserSettings.ini gefunden. Starte Fortnite einmal bis ins Menü und beende es wieder.")
        self.state.setText("Fortnite läuft" if self.service.fortnite_running else "Fortnite ist beendet")
        self.state.setStyleSheet(f"color:{GREEN if self.service.fortnite_running else PAL.text};")

    def optimize(self):
        if not eng.fortnite_ini_path().exists():
            QMessageBox.information(self, "SquallowTweaks", "Keine GameUserSettings.ini gefunden. Starte Fortnite einmal bis ins Menü, beende es und klicke dann erneut.")
            return
        if self.service.fortnite_running:
            if QMessageBox.question(self, "SquallowTweaks", "Fortnite läuft und muss beendet werden, sonst überschreibt es die Config.\n\nJetzt beenden und optimieren?") != QMessageBox.Yes:
                return
            for p in psutil.process_iter(["name"]):
                try:
                    if (p.info.get("name") or "").lower() == svc.FORTNITE_EXE:
                        p.terminate()
                except Exception:  # noqa: BLE001
                    pass
            self.service.fortnite_running = False
        self.btn.setEnabled(False)
        self.service.auto_finished.connect(self._done)
        self.service.auto("competitive", only_fortnite=True)

    def _done(self, *_a):
        try:
            self.service.auto_finished.disconnect(self._done)
        except (RuntimeError, TypeError):
            pass
        self.btn.setEnabled(True)
        self.cfg.setText("Fertig. Starte Fortnite jetzt normal.")


# ===========================================================================
class BenchmarkPage(BasePage):
    def __init__(self, service: svc.Service):
        super().__init__()
        self.service = service
        lay = page_layout(self, "Benchmark", "Miss, ob die Tweaks bei dir wirklich etwas bringen: Messung vorher, Tweaks umlegen, Messung nachher")
        card = Card()
        v = QVBoxLayout(card)
        v.setContentsMargins(20, 16, 20, 16)
        v.setSpacing(10)
        top = QHBoxLayout()
        top.setSpacing(12)
        top.addWidget(label("Fortnite-Messung (PresentMon)", "h2"))
        top.addStretch(1)
        self.name = QLineEdit()
        self.name.setPlaceholderText("Name, z. B. Vorher")
        self.name.setFixedWidth(180)
        top.addWidget(self.name)
        self.dur = Chips(["30 s", "60 s"], "30 s")
        top.addWidget(self.dur)
        self.btn = AnimButton("Messung starten", "accent")
        self.btn.clicked.connect(self.measure)
        top.addWidget(self.btn)
        v.addLayout(top)
        self.msg = label("Starte ein Match oder den Übungsmodus, bleib im Spiel und klicke auf Messung starten.", "muted", True)
        v.addWidget(self.msg)
        tiles = QHBoxLayout()
        tiles.setSpacing(12)
        self.t = {k: StatTile(n, c) for k, n, c in (("avg", "Ø FPS", None), ("low1", "1% Low", CYAN), ("low01", "0,1% Low", PINK), ("stut", "Ruckler", YELLOW))}
        for x in self.t.values():
            tiles.addWidget(x)
        v.addLayout(tiles)
        self.chart = LineChart(None, " ms", 200, show_legend=False)
        self.chart.add_series("Frametime", "@accent2")
        self.chart.setMinimumHeight(150)
        v.addWidget(label("Frametime-Verlauf (niedriger und gleichmäßiger ist besser)", "dim"))
        v.addWidget(self.chart)
        lay.addWidget(card)
        hist = Card()
        hv = QVBoxLayout(hist)
        hv.setContentsMargins(20, 16, 20, 16)
        hv.setSpacing(6)
        head = QHBoxLayout()
        head.addWidget(label("Verlauf", "h2"))
        head.addStretch(1)
        clr = AnimButton("Leeren", "ghost")
        clr.clicked.connect(self.clear_history)
        head.addWidget(clr)
        hv.addLayout(head)
        self.hist_box = QVBoxLayout()
        self.hist_box.setSpacing(4)
        hv.addLayout(self.hist_box)
        lay.addWidget(hist)
        net = Card()
        nv = QVBoxLayout(net)
        nv.setContentsMargins(20, 16, 20, 16)
        nv.setSpacing(10)
        nt = QHBoxLayout()
        nt.addWidget(label("Ping-Test (20 Messungen)", "h2"))
        nt.addStretch(1)
        self.pbtn = AnimButton("Ping testen", "ghost")
        self.pbtn.clicked.connect(self.ping_test)
        nt.addWidget(self.pbtn)
        nv.addLayout(nt)
        pt = QHBoxLayout()
        pt.setSpacing(12)
        self.p = {k: StatTile(n, c) for k, n, c in (("avg", "Ø Ping", None), ("jit", "Jitter", CYAN), ("loss", "Verlust", YELLOW), ("dns", "DNS", PINK))}
        for x in self.p.values():
            pt.addWidget(x)
        nv.addLayout(pt)
        lay.addWidget(net)
        lay.addStretch(1)
        self.render_history()

    # ---- PresentMon
    def measure(self):
        exe = fnmon.find_presentmon()
        if not exe:
            if QMessageBox.question(self, "SquallowTweaks", "PresentMon.exe wurde nicht gefunden (Intel, kostenlos).\n\nLege die Datei neben SquallowTweaks.exe. Download-Seite öffnen?") == QMessageBox.Yes:
                webbrowser.open("https://github.com/GameTechDev/PresentMon/releases")
            return
        if not self.service.fortnite_running:
            QMessageBox.information(self, "SquallowTweaks", "Fortnite läuft nicht. Starte ein Match oder den Übungsmodus.")
            return
        secs = 60 if self.dur.current == "60 s" else 30
        self.btn.setEnabled(False)
        self.msg.setText(f"Messung läuft {secs} s … bleib im Spiel.")
        out = svc.APP_DIR / "capture.csv"

        def work():
            ok, err = fnmon.run_capture(exe, out, secs)
            if not ok:
                return err
            frames = fnmon.parse_presentmon_csv(out)
            return frames, fnmon.compute_frame_stats(frames)

        def done(res):
            self.btn.setEnabled(True)
            if isinstance(res, (str, Exception)) or res is None or res[1] is None:
                self.msg.setText("Messung fehlgeschlagen oder zu wenige Frames (Fortnite im Vordergrund? Administratorrechte?).")
                return
            frames, st = res
            step = max(1, len(frames) // 200)
            self.chart.set_data("Frametime", [sum(frames[i:i + step]) / len(frames[i:i + step]) for i in range(0, len(frames), step)])
            self.t["avg"].set(f"{st.avg_fps:.0f}", "")
            self.t["low1"].set(f"{st.low1_fps:.0f}", "")
            self.t["low01"].set(f"{st.low01_fps:.0f}", "")
            self.t["stut"].set(str(st.stutters), f"p99 {st.p99_ms:.1f} ms")
            self.msg.setText(f"{st.frames} Frames in {st.duration_s:.0f} s gemessen.")
            svc.save_benchmark({"t": time.strftime("%d.%m. %H:%M"), "name": self.name.text().strip() or "Messung", "avg": st.avg_fps, "low1": st.low1_fps,
                                "low01": st.low01_fps, "stut": st.stutters, "tweaks": self.service.active_count()})
            self.render_history()
        svc.run_async(work, done)

    def render_history(self):
        while self.hist_box.count():
            w = self.hist_box.takeAt(0).widget()
            if w:
                w.deleteLater()
        runs = svc.load_benchmarks()
        if not runs:
            self.hist_box.addWidget(label("Noch keine Messungen.", "muted"))
            return
        prev = None
        rows = []
        for r in runs:
            d = ""
            if prev and prev.get("avg"):
                d = f"  ({(r['avg'] / prev['avg'] - 1) * 100:+.0f}% Ø · {(r['low1'] / max(prev['low1'], 0.1) - 1) * 100:+.0f}% 1% Low)"
            rows.append(f"{r['t']}  ·  {r['name']}  ·  Ø {r['avg']:.0f} FPS  ·  1% Low {r['low1']:.0f}  ·  0,1% Low {r['low01']:.0f}  ·  {r['stut']} Ruckler  ·  {r['tweaks']} Tweaks aktiv{d}")
            prev = r
        for text in reversed(rows[-8:]):
            self.hist_box.addWidget(label(text, "muted"))

    def clear_history(self):
        try:
            svc.BENCH_FILE.unlink()
        except OSError:
            pass
        self.render_history()

    # ---- Ping
    def ping_test(self):
        self.pbtn.setEnabled(False)

        def work():
            res = netlab.ping_series("1.1.1.1", 20, 0.4, 900)
            dns, _ = netlab.dns_lookup_ms("www.epicgames.com")
            return res, dns

        def done(r):
            self.pbtn.setEnabled(True)
            if isinstance(r, Exception):
                return
            res, dns = r
            self.p["avg"].set(f"{res.avg:.0f} ms" if res.avg is not None else "–", f"min {res.min:.0f} · max {res.max:.0f}" if res.avg is not None else "keine Antwort")
            self.p["jit"].set(f"{res.jitter:.1f} ms" if res.jitter is not None else "–", "mittlere Schwankung")
            self.p["loss"].set(f"{res.loss_pct:.0f}%" if res.loss_pct is not None else "–", f"{res.received} von {res.sent}")
            self.p["dns"].set(f"{dns:.0f} ms" if dns is not None else "–", "epicgames.com")
        svc.run_async(work, done)
