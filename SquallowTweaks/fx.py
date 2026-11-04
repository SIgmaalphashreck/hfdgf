"""SquallowTweaks - Hintergrund-Effekte: jedes Theme hat sein eigenes, klar erkennbares visuelles Merkmal.

Alles wird live mit QPainter gezeichnet (keine Bilddateien). Performance-Regeln:
  * ein einziges Zeichen-Widget (der Fensterhintergrund), eigene niedrige Bildrate je Effekt (themes.FX_FPS)
  * der Timer laeuft nur, solange das Fenster sichtbar und aktiv ist; sonst steht die Animation
  * Einstellungen > "Hintergrund-Effekte" aus: Effekt wird einmal statisch gezeichnet, kein Timer
"""
from __future__ import annotations

import math
import random
import time

from PySide6.QtCore import QEvent, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPen, QPixmap, QPolygonF, QRadialGradient
from PySide6.QtWidgets import QApplication, QWidget

import themes
from themes import PAL
from ui_common import BUS, alpha, effects_on

GLYPHS = "01{}[]<>/\\|=+*$#%&;:~^"
FROZEN_T = 7.3          # Zeitpunkt, an dem der statische Effekt "eingefroren" wird (sieht gut aus)


def glow(p: QPainter, cx: float, cy: float, r: float, col, a: int) -> None:
    g = QRadialGradient(cx, cy, r)
    g.setColorAt(0, alpha(col, a))
    g.setColorAt(1, alpha(col, 0))
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(g))
    p.drawEllipse(QPointF(cx, cy), r, r)


class FxBackground(QWidget):
    """Fensterhintergrund (#root). Zeichnet Grundfarbe + Theme-Effekt; alle Kinder liegen transparent/halbtransparent darauf."""

    def __init__(self):
        super().__init__()
        self.setObjectName("root")
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        self.t0 = time.time()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self._cache_size = None
        self._stars = []
        self._cols = None
        self._parts = []
        self._scan = None
        self._glyph_cache = {}
        BUS.changed.connect(self._theme_changed)
        BUS.fx_changed.connect(self._sync)
        app = QApplication.instance()
        if app is not None:
            app.applicationStateChanged.connect(self._sync)

    # ---- Steuerung
    def _should_run(self) -> bool:
        if not effects_on() or not self.isVisible():
            return False
        if PAL.fx not in themes.FX_FPS:
            return False
        w = self.window()
        if w is not None and w.isMinimized():
            return False
        app = QApplication.instance()
        return app is None or app.applicationState() == Qt.ApplicationActive

    def _sync(self, *_a):
        if self._should_run():
            self.timer.setInterval(int(1000 / themes.FX_FPS.get(PAL.fx, 10)))
            if not self.timer.isActive():
                self.timer.start()
        else:
            self.timer.stop()
        self.update()

    def _theme_changed(self):
        self._glyph_cache.clear()
        self._sync()

    def showEvent(self, e):
        super().showEvent(e)
        self._sync()

    def hideEvent(self, e):
        self.timer.stop()
        super().hideEvent(e)

    def changeEvent(self, e):
        super().changeEvent(e)
        if e.type() in (QEvent.WindowStateChange, QEvent.ActivationChange) and hasattr(self, "timer"):
            self._sync()

    def _tick(self):
        if PAL.key == "chromatic":
            PAL.apply(themes.chromatic_at((time.time() - self.t0) * 6.0))
        if not self._should_run():
            self.timer.stop()
        self.update()

    # ---- Zeichnen
    def _prepare(self, w: int, h: int):
        if self._cache_size == (w, h):
            return
        self._cache_size = (w, h)
        rng = random.Random(42)
        self._stars = [(rng.random() * w, rng.random() * h, rng.uniform(0.6, 1.7), rng.uniform(0, 6.28), rng.uniform(0.4, 1.6))
                       for _ in range(max(40, int(w * h / 9500)))]
        cols = max(1, w // 26)
        self._cols = [(rng.uniform(45, 115), rng.uniform(0, 3000), rng.randint(7, 14)) for _ in range(cols)]
        self._parts = [(rng.random(), rng.uniform(14, 40), rng.uniform(0, 1500), rng.uniform(1.2, 2.6)) for _ in range(22)]
        scan = QPixmap(w, h)
        scan.fill(Qt.transparent)
        sp = QPainter(scan)
        sp.setPen(QPen(QColor(255, 255, 255, 9), 1))
        for y in range(0, h, 4):
            sp.drawLine(0, y, w, y)
        sp.end()
        self._scan = scan

    def paintEvent(self, _e):
        w, h = self.width(), self.height()
        if w < 20 or h < 20:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(PAL.bg))
        t = (time.time() - self.t0) if self.timer.isActive() else FROZEN_T
        fn = getattr(self, "_fx_" + PAL.fx, None)
        if fn is not None:
            self._prepare(w, h)
            fn(p, w, h, t)

    # ---- Black: Glass ----------------------------------------------------
    def _fx_glass(self, p, w, h, t):
        big = max(w, h)
        glow(p, w * (0.16 + 0.03 * math.sin(t * 0.25)), h * 0.04, big * 0.6, "#FFFFFF", 15)
        glow(p, w * 0.95, h * 1.0, big * 0.5, PAL.accent3, 13)
        x = (t * 16) % (w + 500) - 250
        band = h * 0.35
        g = QLinearGradient(x, 0, x + 190 + band, 0)
        g.setColorAt(0, QColor(255, 255, 255, 0))
        g.setColorAt(0.5, QColor(255, 255, 255, 13))
        g.setColorAt(1, QColor(255, 255, 255, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(g))
        p.drawPolygon(QPolygonF([QPointF(x + band, 0), QPointF(x + band + 190, 0), QPointF(x + 190, h), QPointF(x, h)]))
        edge = QLinearGradient(0, 0, w, 0)
        edge.setColorAt(0, QColor(255, 255, 255, 0))
        edge.setColorAt(0.5, QColor(255, 255, 255, 46))
        edge.setColorAt(1, QColor(255, 255, 255, 0))
        p.fillRect(QRectF(0, 0, w, 1.2), QBrush(edge))

    # ---- White: weiche Lichtteppiche -----------------------------------------
    def _fx_bloom(self, p, w, h, t):
        big = max(w, h)
        glow(p, w * (0.2 + 0.08 * math.sin(t * 0.18)), h * (0.2 + 0.06 * math.cos(t * 0.22)), big * 0.55, PAL.accent, 46)
        glow(p, w * (0.82 + 0.06 * math.cos(t * 0.2)), h * (0.35 + 0.08 * math.sin(t * 0.17)), big * 0.5, PAL.accent3, 40)
        glow(p, w * (0.5 + 0.1 * math.sin(t * 0.13)), h * 1.0, big * 0.55, PAL.accent2, 36)
        glow(p, w * 0.5, -h * 0.1, big * 0.6, "#FFFFFF", 150)

    # ---- Pink: Neon-Roehren + Glow-Puls ----------------------------------------
    def _fx_neon(self, p, w, h, t):
        pulse = 0.5 + 0.5 * math.sin(t * 1.4)
        big = max(w, h)
        glow(p, w * 0.95, h * 0.05, big * 0.5, PAL.accent, int(34 + 36 * pulse))
        glow(p, w * 0.05, h * 0.95, big * 0.5, PAL.accent3, int(26 + 30 * (1 - pulse)))
        p.setBrush(Qt.NoBrush)
        rect = QRectF(7, 7, w - 14, h - 14)
        for width, a in ((11, 14 + 18 * pulse), (6, 30 + 30 * pulse), (2.2, 200)):
            p.setPen(QPen(alpha(PAL.accent, int(a)), width))
            p.drawRoundedRect(rect, 20, 20)
        p.setPen(QPen(alpha("#FFFFFF", 110), 0.8))
        p.drawRoundedRect(rect, 20, 20)

    # ---- Purple: wandernde Energie-Lichtlinien -----------------------------------
    def _fx_energy(self, p, w, h, t):
        big = max(w, h)
        glow(p, w * 0.82, h * 0.12, big * 0.45, PAL.accent, 36)
        glow(p, w * 0.12, h * 0.92, big * 0.4, PAL.accent3, 20)
        for i in range(8):
            u = (t * (0.035 + 0.012 * i) + i * 0.37) % 1.0
            x = -0.3 * w + u * 1.6 * w
            y = h * (0.08 + 0.115 * i)
            dx, dy = w * 0.36, -h * 0.14
            g = QLinearGradient(x, y, x + dx, y + dy)
            col = PAL.accent2 if i % 2 else PAL.accent
            g.setColorAt(0, alpha(col, 0))
            g.setColorAt(0.5, alpha(col, 105))
            g.setColorAt(1, alpha(col, 0))
            p.setPen(QPen(QBrush(g), 1.5))
            p.drawLine(QPointF(x, y), QPointF(x + dx, y + dy))

    # ---- Green: Code-Regen + Partikel ------------------------------------------------
    def _glyphs(self, head: bool):
        key = (PAL.accent2, head)
        pix = self._glyph_cache.get(key)
        if pix is None:
            dpr = max(1.0, self.devicePixelRatioF())
            col = QColor("#E8FFE8") if head else QColor(PAL.accent2)
            pix = []
            font = QFont("Consolas")
            font.setStyleHint(QFont.Monospace)
            font.setPixelSize(15)
            font.setBold(True)
            for ch in GLYPHS:
                pm = QPixmap(int(16 * dpr), int(20 * dpr))
                pm.setDevicePixelRatio(dpr)
                pm.fill(Qt.transparent)
                gp = QPainter(pm)
                gp.setFont(font)
                gp.setPen(col)
                gp.drawText(QRectF(0, 0, 16, 20), Qt.AlignCenter, ch)
                gp.end()
                pix.append(pm)
            self._glyph_cache[key] = pix
        return pix

    def _fx_matrix(self, p, w, h, t):
        body, head = self._glyphs(False), self._glyphs(True)
        n, gh = len(body), 19
        for ci, (speed, off, length) in enumerate(self._cols):
            x = ci * 26 + 5
            total = h + length * gh
            top = (off + t * speed) % total
            for k in range(length):
                y = top - k * gh
                if y < -gh or y > h:
                    continue
                idx = (ci * 7 + k * 3 + (int(t * (2 + ci % 3)) if k % 2 else 0)) % n
                p.setOpacity(0.55 if k == 0 else 0.30 * (1 - k / length) ** 1.5)
                p.drawPixmap(QPointF(x, y), (head if k == 0 else body)[idx])
        p.setOpacity(1.0)
        p.setPen(Qt.NoPen)
        for fx, sp, off, r in self._parts:                   # dezente aufsteigende Partikel
            y = h - ((t * sp + off) % (h + 30))
            p.setBrush(alpha(PAL.accent2, 70))
            p.drawEllipse(QPointF(fx * w + 8 * math.sin(t * 0.6 + off), y), r, r)

    # ---- Blue: Hologramm ---------------------------------------------------------------
    def _fx_holo(self, p, w, h, t):
        flick = 0.85 + 0.15 * math.sin(t * 9.0) * math.sin(t * 1.3)
        p.setPen(QPen(alpha(PAL.accent, int(11 * flick)), 1))
        for x in range(0, w, 64):
            p.drawLine(x, 0, x, h)
        for y in range(0, h, 64):
            p.drawLine(0, y, w, y)
        if self._scan is not None:
            p.drawPixmap(0, 0, self._scan)
        y = (t * 80) % (h + 220) - 110
        g = QLinearGradient(0, y - 90, 0, y + 90)
        g.setColorAt(0, alpha(PAL.accent3, 0))
        g.setColorAt(0.5, alpha(PAL.accent3, int(40 * flick)))
        g.setColorAt(1, alpha(PAL.accent3, 0))
        p.fillRect(QRectF(0, y - 90, w, 180), QBrush(g))
        p.setPen(QPen(alpha(PAL.accent3, int(150 * flick)), 1.6))      # Rahmen-Ecken wie ein Projektions-Feld
        L, m = 26, 12
        for cx, cy, sx, sy in ((m, m, 1, 1), (w - m, m, -1, 1), (m, h - m, 1, -1), (w - m, h - m, -1, -1)):
            p.drawLine(QPointF(cx, cy), QPointF(cx + sx * L, cy))
            p.drawLine(QPointF(cx, cy), QPointF(cx, cy + sy * L))

    # ---- Red: Licht-Impulse -------------------------------------------------------------
    def _fx_pulse(self, p, w, h, t):
        beat = max(0.0, math.sin(t * 2.2)) ** 8
        r = max(w, h) * 0.85
        g = QRadialGradient(w / 2, h / 2, r)
        g.setColorAt(0, alpha(PAL.accent, 0))
        g.setColorAt(0.55, alpha(PAL.accent, 0))
        g.setColorAt(1, alpha(PAL.accent, int(26 + 70 * beat)))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(g))
        p.drawRect(0, 0, w, h)
        for i in range(3):
            x = (t * 55 + i * (w + 300) / 3) % (w + 300) - 150
            slant = h * 0.5
            p.setPen(Qt.NoPen)
            p.setBrush(alpha(PAL.accent, 14 + int(10 * beat)))
            p.drawPolygon(QPolygonF([QPointF(x, h), QPointF(x + 46, h), QPointF(x + 46 + slant, 0), QPointF(x + slant, 0)]))
            p.setPen(QPen(alpha(PAL.accent2, 70 + int(60 * beat)), 1.2))
            p.drawLine(QPointF(x + 46, h), QPointF(x + 46 + slant, 0))

    # ---- Cyan: elektrische Entladungen ----------------------------------------------------------
    def _fx_electric(self, p, w, h, t):
        big = max(w, h)
        glow(p, 0, h * 0.2, big * 0.4, PAL.accent, 24)
        glow(p, w, h * 0.85, big * 0.4, PAL.accent3, 22)
        cycle = 1.1
        k, ph = int(t / cycle), (t / cycle) % 1.0
        rng = random.Random(k * 977 + 13)
        if rng.random() < 0.7:
            a = math.sin(math.pi * ph) ** 1.5
            for _ in range(2):
                x0, x1 = rng.uniform(0, w), rng.uniform(0, w)
                pts = []
                for i in range(15):
                    u = i / 14
                    jitter = 0 if i in (0, 14) else rng.uniform(-30, 30)
                    pts.append(QPointF(x0 + (x1 - x0) * u + jitter, h * u))
                p.setBrush(Qt.NoBrush)
                p.setPen(QPen(alpha(PAL.accent, int(48 * a)), 6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                p.drawPolyline(QPolygonF(pts))
                p.setPen(QPen(alpha(PAL.accent2, int(190 * a)), 1.3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                p.drawPolyline(QPolygonF(pts))

    # ---- Midnight: Sterne, Nebel, Sternschnuppe ---------------------------------------------------
    def _fx_galaxy(self, p, w, h, t):
        big = max(w, h)
        glow(p, w * 0.22 + 30 * math.sin(t * 0.05), h * 0.3, big * 0.5, PAL.accent, 34)
        glow(p, w * 0.8 + 24 * math.cos(t * 0.04), h * 0.75, big * 0.45, PAL.accent3, 28)
        p.setPen(Qt.NoPen)
        for x, y, r, ph, sp in self._stars:
            a = int(70 + 150 * (0.5 + 0.5 * math.sin(t * sp + ph)))
            p.setBrush(QColor(214, 222, 255, a))
            p.drawEllipse(QPointF(x, y), r, r)
        period = 11.0
        k, ph = int(t / period), (t % period) / period
        if ph < 0.09:
            u = ph / 0.09
            rng = random.Random(k * 31 + 5)
            sx, sy = rng.uniform(0.35, 0.95) * w, rng.uniform(0.02, 0.35) * h
            hx, hy = sx - u * w * 0.4, sy + u * w * 0.4 * 0.55
            tx, ty = hx + 150 * (1 - u * 0.3), hy - 150 * 0.55 * (1 - u * 0.3)
            g = QLinearGradient(tx, ty, hx, hy)
            g.setColorAt(0, QColor(255, 255, 255, 0))
            g.setColorAt(1, QColor(255, 255, 255, int(220 * math.sin(math.pi * u))))
            p.setPen(QPen(QBrush(g), 1.8, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPointF(tx, ty), QPointF(hx, hy))

    # ---- Chromatic: wandernde Farbverlaeufe (PAL selbst wechselt die Akzentfarben) ---------------------
    def _fx_chroma(self, p, w, h, t):
        big = max(w, h)
        g = QLinearGradient(0, 0, w, h)
        g.setColorAt(0, alpha(PAL.accent, 26))
        g.setColorAt(0.5, alpha(PAL.accent2, 12))
        g.setColorAt(1, alpha(PAL.accent3, 26))
        p.fillRect(QRectF(0, 0, w, h), QBrush(g))
        glow(p, w * (0.25 + 0.15 * math.sin(t * 0.2)), h * 0.3, big * 0.5, PAL.accent, 40)
        glow(p, w * (0.75 + 0.12 * math.cos(t * 0.17)), h * 0.7, big * 0.5, PAL.accent3, 36)
        glow(p, w * 0.5, h * (0.5 + 0.3 * math.sin(t * 0.13)), big * 0.4, PAL.accent2, 22)

    # ---- Custom: ruhiger Akzent-Glow --------------------------------------------------------------------
    def _fx_glow(self, p, w, h, t):
        big = max(w, h)
        pulse = 0.5 + 0.5 * math.sin(t * 0.6)
        glow(p, w * 0.9, h * 0.08, big * 0.5, PAL.accent, int(30 + 24 * pulse))
        glow(p, w * 0.08, h * 0.95, big * 0.45, PAL.accent3, int(18 + 14 * (1 - pulse)))
