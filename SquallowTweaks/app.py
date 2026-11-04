"""SquallowTweaks - Hauptfenster."""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMainWindow, QStackedWidget, QVBoxLayout, QWidget

import fx
import pages_a
import pages_b
import service as svc
from themes import PAL
from ui_common import (BUS, GREEN, RED, DiscordButton, GradientLine, NavButton, ProfileCard, Toast, apply_dark_titlebar, label, make_scroll,
                       pill)

APP_NAME = "SquallowTweaks"
VERSION = "1.1.0"


def asset(name: str) -> str:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return str(base / "assets" / name)


class MainWindow(QMainWindow):
    # (Bereich, [(Name, Icon)])
    NAV = (("ÜBERSICHT", (("Dashboard", "dashboard"),)),
           ("OPTIMIERUNG", (("Tweaks", "bolt"), ("Fortnite", "target"), ("Benchmark", "bench"))),
           ("SYSTEM", (("Prozesse", "list"), ("Netzwerk", "wifi"), ("Bereinigung", "trash"), ("Einstellungen", "gear"))))
    SCROLLING = ("Dashboard", "Tweaks", "Fortnite", "Benchmark", "Netzwerk", "Bereinigung", "Einstellungen")

    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(QIcon(asset("bird.png")))
        self.setMinimumSize(1180, 720)
        scr = QGuiApplication.primaryScreen()
        if scr is not None:                      # grosses Fenster wie im Vorbild, aber nie groesser als der Bildschirm
            av = scr.availableGeometry()
            self.resize(min(1480, av.width() - 40), min(920, av.height() - 60))
        else:
            self.resize(1440, 880)
        self.service = svc.Service()
        root = fx.FxBackground()          # Fensterhintergrund mit Theme-Effekt
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(GradientLine())
        body = QHBoxLayout()
        body.setSpacing(0)
        outer.addLayout(body, 1)
        body.addWidget(self._sidebar())
        self.stack = QStackedWidget()
        s = self.service
        self.pages = {
            "Dashboard": pages_a.DashboardPage(s), "Tweaks": pages_a.TweaksPage(s), "Fortnite": pages_a.FortnitePage(s),
            "Benchmark": pages_a.BenchmarkPage(s), "Prozesse": pages_b.ProcessesPage(s), "Netzwerk": pages_b.NetworkPage(s),
            "Bereinigung": pages_b.CleanPage(s), "Einstellungen": pages_b.SettingsPage(s),
        }
        self.holders = {}
        for name, page in self.pages.items():
            page.navigate.connect(self.go)
            if name == "Dashboard":
                page.search_requested.connect(self.search_tweaks)
            holder = make_scroll(page) if name in self.SCROLLING else page
            self.holders[name] = holder
            self.stack.addWidget(holder)
        body.addWidget(self.stack, 1)
        self.toast = Toast(root)                  # Rueckmeldung nach jedem Schalter ("angewendet" / Fehlergrund)
        self.service.tweak_done.connect(self.on_tweak_done)
        self.sampler = svc.Sampler()
        self.sampler.sample.connect(self.on_sample)
        self.sampler.procs.connect(self.pages["Prozesse"].on_procs)
        self.sampler.start()
        self.service.refresh_states()
        BUS.changed.connect(lambda: apply_dark_titlebar(self))
        self.go("Dashboard")

    def _sidebar(self) -> QWidget:
        side = QWidget()
        side.setObjectName("sidebar")
        side.setFixedWidth(232)
        v = QVBoxLayout(side)
        v.setContentsMargins(14, 20, 14, 16)
        v.setSpacing(2)
        v.addWidget(ProfileCard(asset("bird.png"), VERSION, "ADMIN" if self.service.admin else "KEIN ADMIN"))
        v.addSpacing(6)
        self.nav_buttons: dict[str, NavButton] = {}
        for section, items in self.NAV:
            sec = label(section, "section")
            sec.setContentsMargins(10, 14, 0, 6)
            v.addWidget(sec)
            for text, ico in items:
                b = NavButton(text, ico)
                b.clicked.connect(lambda _c=False, n=text: self.go(n))
                v.addWidget(b)
                self.nav_buttons[text] = b
        v.addStretch(1)
        self.discord = DiscordButton()           # eigener Button unter der Navigation, ersetzt keinen Menuepunkt
        v.addWidget(self.discord)
        v.addSpacing(10)
        row = QHBoxLayout()
        row.setContentsMargins(6, 0, 0, 0)
        row.addWidget(pill("ADMIN" if self.service.admin else "KEIN ADMIN", GREEN if self.service.admin else RED))
        row.addStretch(1)
        v.addLayout(row)
        return side

    def on_tweak_done(self, tweak_id: str, ok: bool, message: str):
        t = self.service.by_id.get(tweak_id)
        name = t.name if t else tweak_id
        self.toast.show_message(f"{name}: {message}" if ok else f"{name} – nicht angewendet: {message}", ok)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if hasattr(self, "toast"):
            self.toast.place()

    def search_tweaks(self, text: str):
        """Suche aus der Dashboard-Leiste: Tweaks-Seite oeffnen und Suchbegriff setzen."""
        self.go("Tweaks")
        box = self.pages["Tweaks"].list.search
        box.setText(text.strip())

    def go(self, name: str):
        for n, b in self.nav_buttons.items():
            b.setChecked(n == name)
        self.stack.setCurrentWidget(self.holders[name])
        self.sampler.want_procs = name == "Prozesse"
        if name == "Fortnite":
            self.pages["Fortnite"].refresh()
        if name == "Netzwerk":
            if not self.pages["Netzwerk"].monitor:
                self.pages["Netzwerk"].start()
        else:
            self.pages["Netzwerk"].stop()

    def on_sample(self, d: dict):
        self.service.fortnite_running = bool(d.get("fn"))
        self.pages["Dashboard"].on_sample(d)
        self.pages["Prozesse"].on_sample(d)
        self.sampler.auto_high = self.pages["Fortnite"].prio_on
        if self.stack.currentWidget() is self.holders["Fortnite"]:
            self.pages["Fortnite"].refresh()

    def showEvent(self, e):
        super().showEvent(e)
        apply_dark_titlebar(self)

    def closeEvent(self, e):
        self.sampler.stop()
        self.pages["Netzwerk"].shutdown()
        self.sampler.wait(2500)
        super().closeEvent(e)
