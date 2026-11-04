"""SquallowTweaks - Farben (themefaehig), Stylesheet und Widgets (mit animierten Hover-Effekten)."""
from __future__ import annotations

import math
import os
import time
import webbrowser
from collections import deque
from typing import Optional

from PySide6.QtCore import (Property, QEasingCurve, QObject, QPointF, QPropertyAnimation, QRectF, QSize, Qt, QTimer, QUrl,
                            QVariantAnimation, Signal)
from PySide6.QtGui import (QBrush, QColor, QCursor, QDesktopServices, QFont, QFontMetrics, QLinearGradient, QPainter,
                           QPainterPath, QPen, QPixmap, QPolygonF, QRadialGradient)
from PySide6.QtWidgets import (QAbstractButton, QApplication, QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QPushButton,
                               QScrollArea, QSizePolicy, QVBoxLayout, QWidget)

import themes
from themes import PAL

# ---------------------------------------------------------------------------
# Feste Farben mit Bedeutung (bleiben in jedem Theme gleich) ...
# ---------------------------------------------------------------------------
GREEN = "#4ADE80"
YELLOW = "#FBBF24"
RED = "#F87171"
CYAN = "#5EEAD4"
PINK = "#F472B6"
LAVENDER = "#B89CFF"
GREY = "#8C8CA8"
DISCORD_URL = "https://discord.gg/6dDvaPA2n"

TAG_COLORS = {"FPS": LAVENDER, "LATENZ": CYAN, "PING": GREEN, "FRAMETIME": PINK}
EVIDENCE_COLORS = {"belegt": GREEN, "klein": YELLOW, "schwach": "#6E6E8A"}
EVIDENCE_TEXT = {"belegt": "Wirkung laut Tests belegt", "klein": "Kleine/systemabhängige Wirkung", "schwach": "Wirkung kaum belegt (optional)"}


# ---------------------------------------------------------------------------
# ... und Theme-Farben: Zugriff immer ueber PAL (live) oder "@rolle"-Strings
# ---------------------------------------------------------------------------
class ThemeBus(QObject):
    changed = Signal()       # Theme gewechselt (Farben neu lesen)
    fx_changed = Signal()    # Effekte an/aus


BUS = ThemeBus()
_store: Optional[themes.SettingsStore] = None


def store() -> themes.SettingsStore:
    global _store
    if _store is None:
        _store = themes.SettingsStore()
    return _store


def role(spec: str) -> str:
    """'@accent2' -> aktuelle Theme-Farbe; alles andere bleibt unveraendert."""
    if isinstance(spec, str) and spec.startswith("@"):
        return getattr(PAL, spec[1:])
    return spec


def rc(spec) -> QColor:
    return QColor(role(spec)) if isinstance(spec, str) else QColor(spec)


def build_qss(p) -> str:
    sr, sg, sb = themes.to_rgb(p.sidebar)
    return f"""
* {{ font-family: "Segoe UI Variable Text", "Segoe UI", "Inter", "Noto Sans", "DejaVu Sans", sans-serif; font-size: 13px; color: {p.text}; }}
QMainWindow, #root {{ background: {p.bg}; }}
QWidget {{ background: transparent; }}
#sidebar {{ background: rgba({sr},{sg},{sb},{p.sidebar_alpha}); border-right: 1px solid {p.border}; }}
QLabel#h1 {{ font-size: 26px; font-weight: 700; }}
QLabel#h2 {{ font-size: 15px; font-weight: 600; }}
QLabel#muted {{ color: {p.muted}; }}
QLabel#dim {{ color: {p.dim}; font-size: 11px; }}
QLabel#section {{ color: {p.dim}; font-size: 10px; font-weight: 700; letter-spacing: 2px; }}
QLabel#big {{ font-size: 26px; font-weight: 700; }}
QLabel#pill {{ border-radius: 8px; padding: 2px 8px; font-size: 10px; font-weight: 700; letter-spacing: 1px; }}
QLineEdit {{ background: {p.card}; border: 1px solid {p.border}; border-radius: 10px; padding: 9px 12px; selection-background-color: {p.accent}; }}
QLineEdit:focus {{ border-color: {p.accent}; background: {p.input_focus}; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {p.handle}; border-radius: 4px; min-height: 36px; }}
QScrollBar::handle:vertical:hover {{ background: {p.handle_hover}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar:horizontal {{ height: 0; }}
QProgressBar {{ background: {p.card2}; border: none; border-radius: 3px; max-height: 6px; min-height: 6px; }}
QProgressBar::chunk {{ border-radius: 3px; background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {p.accent}, stop:1 {p.accent3}); }}
QToolTip {{ background: {p.tip_bg}; color: {p.text}; border: 1px solid {p.tip_border}; padding: 8px; border-radius: 6px; }}
QTableView {{ background: transparent; border: none; gridline-color: transparent; outline: 0; }}
QHeaderView::section {{ background: transparent; color: {p.dim}; border: none; padding: 6px 10px; font-size: 10px; font-weight: 700; letter-spacing: 2px; }}
QMessageBox {{ background: {p.card}; }}
QFrame#dcbox {{ background: rgba(0,0,0,40); border: 1px solid {p.border}; border-radius: 12px; }}
"""


def init_theme() -> None:
    """Beim Start: gespeichertes Theme laden und anwenden (Stylesheet setzt main.make_app)."""
    PAL.apply(store().palette())


def apply_theme(key: str, custom_accent: Optional[str] = None, persist: bool = True) -> None:
    """Theme wechseln, speichern, Stylesheet neu setzen, alle Widgets benachrichtigen."""
    st = store()
    if custom_accent and themes.valid_hex(custom_accent):
        st.data["custom_accent"] = custom_accent.upper()
    st.data["theme"] = key if key in themes.THEMES else themes.DEFAULT_THEME
    if persist:
        st.save()
    PAL.apply(st.palette())
    app = QApplication.instance()
    if app is not None:
        app.setStyleSheet(build_qss(PAL))
    BUS.changed.emit()


def set_effects(on: bool) -> None:
    st = store()
    st.data["effects"] = bool(on)
    st.save()
    BUS.fx_changed.emit()


def effects_on() -> bool:
    return bool(store()["effects"])


def open_url(url: str) -> None:
    """Oeffnet einen Link im Standardbrowser."""
    try:
        if QDesktopServices.openUrl(QUrl(url)):
            return
    except Exception:  # noqa: BLE001
        pass
    try:
        webbrowser.open(url)
    except Exception:  # noqa: BLE001
        pass


class ThemedLabel(QLabel):
    """Label, dessen Farbe einer Theme-Rolle folgt (z. B. '@accent2') und sich beim Theme-Wechsel selbst aktualisiert."""

    def __init__(self, text: str = "", name: str = "", color: Optional[str] = None, css: str = ""):
        super().__init__(text)
        if name:
            self.setObjectName(name)
        self._color, self._css = color, css
        self._restyle()
        BUS.changed.connect(self._restyle)

    def set_color(self, color: Optional[str]):
        self._color = color
        self._restyle()

    def set_css(self, css: str):
        self._css = css
        self._restyle()

    def _restyle(self):
        parts = []
        if self._color:
            parts.append(f"color:{role(self._color)};")
        if self._css:
            parts.append(self._css)
        self.setStyleSheet("".join(parts))


def lerp(a, b, t: float) -> QColor:
    a, b = QColor(a), QColor(b)
    t = max(0.0, min(1.0, t))
    return QColor(int(a.red() + (b.red() - a.red()) * t), int(a.green() + (b.green() - a.green()) * t),
                  int(a.blue() + (b.blue() - a.blue()) * t), int(a.alpha() + (b.alpha() - a.alpha()) * t))


def alpha(color, a: int) -> QColor:
    c = QColor(color)
    c.setAlpha(a)
    return c


class HoverValue:
    """Animierter Wert 0..1 fuer Hover-Effekte (sanfter Uebergang statt Sprung)."""

    def __init__(self, widget: QWidget, duration: int = 160):
        self.v = 0.0
        self.widget = widget
        self.anim = QVariantAnimation(widget)
        self.anim.setDuration(duration)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)
        self.anim.valueChanged.connect(self._tick)

    def _tick(self, x):
        self.v = float(x)
        self.widget.update()

    def to(self, end: float):
        self.anim.stop()
        self.anim.setStartValue(self.v)
        self.anim.setEndValue(float(end))
        self.anim.start()


def pointer_inside(w: QWidget) -> bool:
    return w.rect().contains(w.mapFromGlobal(QCursor.pos()))


# ---------------------------------------------------------------------------
# Icons (gezeichnet)
# ---------------------------------------------------------------------------
def draw_icon(p: QPainter, name: str, rect: QRectF, color) -> None:
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    p.translate(rect.topLeft())
    s = rect.width()
    c = QColor(color)
    p.setPen(QPen(c, max(1.6, s * 0.085), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    if name == "dashboard":
        g = s * 0.14
        w = (s - 3 * g) / 2
        for r in range(2):
            for q in range(2):
                p.drawRoundedRect(QRectF(g + q * (w + g), g + r * (w + g), w, w), 3, 3)
    elif name == "bolt":
        poly = QPolygonF([QPointF(s * .58, s * .08), QPointF(s * .22, s * .56), QPointF(s * .47, s * .56),
                          QPointF(s * .40, s * .92), QPointF(s * .78, s * .42), QPointF(s * .52, s * .42)])
        p.setBrush(c)
        p.drawPolygon(poly)
    elif name == "target":
        p.drawEllipse(QRectF(s * .14, s * .14, s * .72, s * .72))
        p.drawEllipse(QRectF(s * .36, s * .36, s * .28, s * .28))
        for a, b, c2, d in ((.5, .02, .5, .2), (.5, .8, .5, .98), (.02, .5, .2, .5), (.8, .5, .98, .5)):
            p.drawLine(QPointF(s * a, s * b), QPointF(s * c2, s * d))
    elif name == "bench":
        p.setPen(Qt.NoPen)
        p.setBrush(c)
        for i, h in enumerate((0.34, 0.62, 0.9)):
            p.drawRoundedRect(QRectF(s * (0.12 + i * 0.3), s * .94 - s * h, s * .2, s * h), 2, 2)
    elif name == "wifi":
        for r in (0.20, 0.36, 0.52):
            p.drawArc(QRectF(s * .5 - s * r, s * .78 - s * r, 2 * s * r, 2 * s * r), 45 * 16, 90 * 16)
        p.setBrush(c)
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(s * .5, s * .78), s * .06, s * .06)
    elif name == "list":
        for i in range(3):
            y = s * (0.22 + i * 0.28)
            p.drawLine(QPointF(s * .30, y), QPointF(s * .92, y))
            p.setBrush(c)
            p.drawEllipse(QPointF(s * .12, y), 1.4, 1.4)
            p.setBrush(Qt.NoBrush)
    elif name == "trash":
        p.drawLine(QPointF(s * .18, s * .26), QPointF(s * .82, s * .26))
        p.drawLine(QPointF(s * .40, s * .26), QPointF(s * .40, s * .14))
        p.drawLine(QPointF(s * .40, s * .14), QPointF(s * .60, s * .14))
        p.drawLine(QPointF(s * .60, s * .14), QPointF(s * .60, s * .26))
        path = QPainterPath()
        path.moveTo(s * .26, s * .26)
        path.lineTo(s * .30, s * .88)
        path.lineTo(s * .70, s * .88)
        path.lineTo(s * .74, s * .26)
        p.drawPath(path)
        p.drawLine(QPointF(s * .44, s * .42), QPointF(s * .44, s * .72))
        p.drawLine(QPointF(s * .56, s * .42), QPointF(s * .56, s * .72))
    elif name == "gear":
        p.drawEllipse(QRectF(s * .30, s * .30, s * .40, s * .40))
        for i in range(8):
            a = math.radians(i * 45)
            p.drawLine(QPointF(s * .5 + math.cos(a) * s * .30, s * .5 + math.sin(a) * s * .30),
                       QPointF(s * .5 + math.cos(a) * s * .44, s * .5 + math.sin(a) * s * .44))
    elif name == "discord":
        body = QPainterPath()
        body.addRoundedRect(QRectF(s * .06, s * .22, s * .88, s * .56), s * .24, s * .24)
        for ex in (.13, .61):
            ear = QPainterPath()
            ear.addEllipse(QRectF(s * ex, s * .10, s * .26, s * .26))
            body = body.united(ear)
        for pts in (((.20, .72), (.42, .72), (.28, .92)), ((.58, .72), (.80, .72), (.72, .92))):
            tail = QPainterPath()
            tail.addPolygon(QPolygonF([QPointF(s * x, s * y) for x, y in pts]))
            tail.closeSubpath()
            body = body.united(tail)
        eyes = QPainterPath()
        eyes.addEllipse(QRectF(s * .27, s * .42, s * .17, s * .22))
        eyes.addEllipse(QRectF(s * .56, s * .42, s * .17, s * .22))
        body = body.subtracted(eyes)
        p.setPen(Qt.NoPen)
        p.setBrush(c)
        p.drawPath(body)
    elif name == "cpu":
        p.drawRoundedRect(QRectF(s * .24, s * .24, s * .52, s * .52), 3, 3)
        p.drawRect(QRectF(s * .38, s * .38, s * .24, s * .24))
        for i in range(3):
            o = s * (0.34 + i * 0.16)
            p.drawLine(QPointF(o, s * .08), QPointF(o, s * .24))
            p.drawLine(QPointF(o, s * .76), QPointF(o, s * .92))
            p.drawLine(QPointF(s * .08, o), QPointF(s * .24, o))
            p.drawLine(QPointF(s * .76, o), QPointF(s * .92, o))
    elif name == "gpu":
        p.drawRoundedRect(QRectF(s * .06, s * .26, s * .88, s * .44), 3, 3)
        p.drawEllipse(QPointF(s * .34, s * .48), s * .12, s * .12)
        p.drawEllipse(QPointF(s * .68, s * .48), s * .08, s * .08)
        p.drawLine(QPointF(s * .14, s * .78), QPointF(s * .60, s * .78))
        p.drawLine(QPointF(s * .14, s * .70), QPointF(s * .14, s * .78))
    elif name == "ram":
        p.drawRoundedRect(QRectF(s * .06, s * .28, s * .88, s * .38), 2, 2)
        p.setBrush(c)
        for i in range(3):
            p.drawRect(QRectF(s * (0.16 + i * 0.27), s * .38, s * .17, s * .18))
        p.setBrush(Qt.NoBrush)
        for i in range(5):
            x = s * (0.16 + i * 0.17)
            p.drawLine(QPointF(x, s * .66), QPointF(x, s * .80))
    elif name == "clock":
        p.drawEllipse(QRectF(s * .12, s * .12, s * .76, s * .76))
        p.drawLine(QPointF(s * .5, s * .5), QPointF(s * .5, s * .28))
        p.drawLine(QPointF(s * .5, s * .5), QPointF(s * .66, s * .58))
    elif name == "check":
        p.drawPolyline(QPolygonF([QPointF(s * .20, s * .54), QPointF(s * .42, s * .74), QPointF(s * .80, s * .28)]))
    p.restore()


def tinted_pixmap(path: str, size: int) -> QPixmap:
    return QPixmap(path).scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)


# ---------------------------------------------------------------------------
# Bausteine
# ---------------------------------------------------------------------------
def label(text: str = "", name: str = "", wrap: bool = False) -> QLabel:
    lab = QLabel(text)
    if name:
        lab.setObjectName(name)
    lab.setWordWrap(wrap)
    return lab


def pill(text: str, color: str) -> QLabel:
    lab = QLabel(text)
    lab.setObjectName("pill")
    c = QColor(color)
    lab.setStyleSheet(f"QLabel#pill {{ color: {color}; background: rgba({c.red()},{c.green()},{c.blue()},38); }}")
    lab.setAlignment(Qt.AlignCenter)
    lab.setFixedHeight(20)
    lab.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    return lab


class ElidedLabel(QLabel):
    def __init__(self, text: str = "", name: str = ""):
        super().__init__(text)
        if name:
            self.setObjectName(name)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.setMinimumWidth(40)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    def paintEvent(self, _e):
        p = QPainter(self)
        fm = QFontMetrics(self.font())
        p.setPen(self.palette().color(self.foregroundRole()))
        p.setFont(self.font())
        p.drawText(self.rect(), Qt.AlignVCenter | Qt.AlignLeft, fm.elidedText(self.text(), Qt.ElideRight, self.width()))


class HoverFrame(QFrame):
    """Karte mit animiertem Hover: Farbwechsel, leuchtender Rand, Lichtkante oben und weicher "Anhebe"-Schatten.
    kind: card | hero. Alle Farben kommen live aus dem aktiven Theme."""

    def __init__(self, radius: int = 14, kind: str = "card", hover_on: bool = True):
        super().__init__()
        self.radius, self.kind, self.hover_on = radius, kind, hover_on
        self.hv = HoverValue(self, 190)
        BUS.changed.connect(self.update)

    def enterEvent(self, e):
        if self.hover_on:
            self.hv.to(1)
        super().enterEvent(e)

    def leaveEvent(self, e):
        if self.hover_on and not pointer_inside(self):
            self.hv.to(0)
        super().leaveEvent(e)

    def colors(self):
        p = PAL
        if self.kind == "hero":
            return p.hero, p.hero_hover, p.hero_border, p.accent2
        return p.card, p.card2, p.border, p.accent

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        h = self.hv.v
        base, hover, border, hborder = self.colors()
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        fill = lerp(base, hover, h)
        fill.setAlpha(255 if self.kind == "hero" else PAL.card_alpha)
        p.setPen(QPen(lerp(border, hborder, h * 0.9), 1 + h * 0.6))
        p.setBrush(fill)
        p.drawRoundedRect(r, self.radius, self.radius)
        if h > 0.02:
            # "Anheben": Lichtkante oben, weicher Schatten unten, zarter innerer Glow
            g = QLinearGradient(0, r.top(), 0, r.bottom())
            g.setColorAt(0, alpha("#FFFFFF" if not PAL.light else hborder, int(16 * h)))
            g.setColorAt(0.5, alpha(hborder, 0))
            g.setColorAt(1, alpha("#000000", int((40 if not PAL.light else 12) * h)))
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(g))
            p.drawRoundedRect(r.adjusted(1, 1, -1, -1), self.radius - 1, self.radius - 1)
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(alpha(hborder, int(34 * h)), 3))
            p.drawRoundedRect(r.adjusted(2, 2, -2, -2), self.radius - 2, self.radius - 2)
            g2 = QLinearGradient(r.left(), 0, r.right(), 0)
            g2.setColorAt(0, alpha(hborder, 0))
            g2.setColorAt(0.5, alpha(hborder, int(200 * h)))
            g2.setColorAt(1, alpha(PAL.accent3, 0))
            p.setPen(QPen(QBrush(g2), 1.6))
            p.drawLine(QPointF(r.left() + self.radius, r.top() + 0.8), QPointF(r.right() - self.radius, r.top() + 0.8))


class Card(HoverFrame):
    def __init__(self, name: str = "card"):
        if name == "hero":
            super().__init__(16, "hero")
        else:
            super().__init__(14)


class AnimButton(QPushButton):
    """Button mit animiertem Hover. variant: accent | ghost | danger | chip."""

    def __init__(self, text: str, variant: str = "ghost"):
        super().__init__(text)
        self.variant = variant
        self.hv = HoverValue(self)
        self.setCursor(Qt.PointingHandCursor)
        self.setCheckable(variant == "chip")
        self.setFocusPolicy(Qt.NoFocus)
        self._fx: Optional[QGraphicsDropShadowEffect] = None
        self.setMinimumWidth(self.sizeHint().width())
        if variant == "accent":
            self._fx = QGraphicsDropShadowEffect(self)
            self._fx.setOffset(0, 4)
            self._glow(0.0)
            self.setGraphicsEffect(self._fx)
            self.hv.anim.valueChanged.connect(self._glow)
        BUS.changed.connect(self._retint)

    def _glow(self, v):
        if self._fx:
            self._fx.setBlurRadius(24 + 18 * float(v))
            self._fx.setColor(alpha(PAL.accent, int(100 + 110 * float(v))))

    def _retint(self):
        self._glow(self.hv.v)
        self.update()

    def sizeHint(self) -> QSize:
        f = QFont(self.font())
        f.setBold(True)
        f.setPixelSize(15 if self.variant == "accent" else 13)
        w = QFontMetrics(f).horizontalAdvance(self.text())
        return QSize(w + {"accent": 56, "chip": 30}.get(self.variant, 34), {"accent": 48, "chip": 32}.get(self.variant, 38))

    def enterEvent(self, e):
        self.hv.to(1)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.hv.to(0)
        super().leaveEvent(e)

    def paintEvent(self, _e):
        pal = PAL
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        h = self.hv.v
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        v = self.variant
        rad = 12 if v == "accent" else (r.height() / 2 if v == "chip" else 10)
        txt = QColor(pal.text)
        if not self.isEnabled():
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(pal.disabled))
            p.drawRoundedRect(r, rad, rad)
            txt = QColor(pal.dim)
        elif v == "accent":
            g = QLinearGradient(r.left(), 0, r.right(), 0)
            g.setColorAt(0, lerp(pal.btn_a, pal.btn_a_h, h))
            g.setColorAt(1, lerp(pal.btn_b, pal.btn_b_h, h))
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(g))
            p.drawRoundedRect(r, rad, rad)
            if h > 0.02:      # Lichtreflex oben beim Hover
                sheen = QLinearGradient(0, r.top(), 0, r.bottom())
                sheen.setColorAt(0, QColor(255, 255, 255, int(46 * h)))
                sheen.setColorAt(0.55, QColor(255, 255, 255, 0))
                p.setBrush(QBrush(sheen))
                p.drawRoundedRect(r, rad, rad)
            txt = QColor(pal.on_accent)
        elif v == "danger":
            red_dim, red_bg = themes.mix(pal.border, RED, 0.35), themes.mix(pal.card, RED, 0.12)
            p.setPen(QPen(lerp(red_dim, RED, h), 1))
            p.setBrush(lerp(red_bg, themes.mix(pal.card, RED, 0.22), h))
            p.drawRoundedRect(r, rad, rad)
            txt = QColor(RED)
        elif v == "chip":
            on = self.isChecked()
            p.setPen(QPen(QColor(pal.accent) if on else lerp(pal.border, pal.border_hi, h), 1))
            p.setBrush(QColor(pal.chip_on) if on else lerp(pal.card, pal.card2, h))
            p.drawRoundedRect(r, rad, rad)
            txt = QColor(pal.text) if on else lerp(pal.muted, pal.text, h)
        else:
            p.setPen(QPen(lerp(pal.border, pal.accent, h), 1))
            p.setBrush(lerp(pal.card2, pal.ghost_hover, h))
            p.drawRoundedRect(r, rad, rad)
            if h > 0.02:      # zarter Glow-Ring
                p.setBrush(Qt.NoBrush)
                p.setPen(QPen(alpha(pal.accent, int(46 * h)), 3))
                p.drawRoundedRect(r.adjusted(1.5, 1.5, -1.5, -1.5), rad - 1, rad - 1)
        p.setPen(txt)
        f = QFont(self.font())
        f.setBold(True)
        f.setPixelSize(15 if v == "accent" else 13)
        p.setFont(f)
        p.drawText(self.rect(), Qt.AlignCenter, self.text())


class NavButton(QPushButton):
    def __init__(self, text: str, icon: str):
        super().__init__(text)
        self.icon_name = icon
        self.hv = HoverValue(self, 150)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(42)
        self.setFocusPolicy(Qt.NoFocus)
        BUS.changed.connect(self.update)

    def enterEvent(self, e):
        self.hv.to(1)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.hv.to(0)
        super().leaveEvent(e)

    def paintEvent(self, _e):
        pal = PAL
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        h = self.hv.v
        on = self.isChecked()
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        if on:
            g = QLinearGradient(r.left(), 0, r.right(), 0)
            g.setColorAt(0, QColor(pal.nav_a))
            g.setColorAt(1, QColor(pal.nav_b))
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(g))
            p.drawRoundedRect(r, 10, 10)
            p.setBrush(QColor(pal.accent2))
            p.drawRoundedRect(QRectF(0, r.height() * 0.22, 3.5, r.height() * 0.56 + 2), 2, 2)
        elif h > 0.01:
            p.setPen(Qt.NoPen)
            p.setBrush(alpha(pal.nav_hover, int(255 * h)))
            p.drawRoundedRect(r, 10, 10)
        col = QColor(pal.accent2) if on else lerp(pal.muted, pal.text, h)
        draw_icon(p, self.icon_name, QRectF(16 + 3 * h, (self.height() - 20) / 2, 20, 20), col)
        p.setPen(QColor(pal.text) if on else lerp(pal.muted, pal.text, h))
        f = QFont(self.font())
        f.setPixelSize(14)
        f.setWeight(QFont.DemiBold if on else QFont.Medium)
        p.setFont(f)
        p.drawText(QRectF(48 + 3 * h, 0, self.width() - 56, self.height()), Qt.AlignVCenter | Qt.AlignLeft, self.text())


class IconButton(QAbstractButton):
    """Runder Icon-Button (z. B. Einstellungen): Hover = Aufhellen, Glow-Ring, Icon dreht sich dezent."""

    def __init__(self, icon: str, tooltip: str = "", size: int = 42, spin: bool = True):
        super().__init__()
        self.icon_name, self.spin = icon, spin
        self.hv = HoverValue(self, 260)
        self.setFixedSize(size, size)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        if tooltip:
            self.setToolTip(tooltip)
        BUS.changed.connect(self.update)

    def enterEvent(self, e):
        self.hv.to(1)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.hv.to(0)
        super().leaveEvent(e)

    def paintEvent(self, _e):
        pal = PAL
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        h = self.hv.v
        r = QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5)
        rad = r.height() * 0.32
        if h > 0.02:
            p.setPen(QPen(alpha(pal.accent, int(48 * h)), 3.2))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(r.adjusted(-0.6, -0.6, 0.6, 0.6), rad, rad)
        p.setPen(QPen(lerp(pal.border, pal.accent, h), 1))
        p.setBrush(lerp(pal.card2, pal.ghost_hover, h))
        p.drawRoundedRect(r, rad, rad)
        s = min(self.width(), self.height()) * 0.5
        c = r.center()
        p.save()
        p.translate(c)
        if self.spin:
            p.rotate(90 * h)
        draw_icon(p, self.icon_name, QRectF(-s / 2, -s / 2, s, s), lerp(pal.muted, pal.text, h))
        p.restore()


class DiscordButton(QAbstractButton):
    """Discord-Einladung. Farben folgen dem Theme (Verlauf Akzent -> Akzent 3), Klick oeffnet den Link im Standardbrowser."""

    def __init__(self, url: str = DISCORD_URL, compact: bool = False):
        super().__init__()
        self.url = url
        self.hv = HoverValue(self, 200)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setFixedHeight(40 if compact else 44)
        self.setToolTip("Discord-Server beitreten")
        self._fx = QGraphicsDropShadowEffect(self)
        self._fx.setOffset(0, 3)
        self._glow(0.0)
        self.setGraphicsEffect(self._fx)
        self.hv.anim.valueChanged.connect(self._glow)
        self.clicked.connect(lambda: open_url(self.url))
        BUS.changed.connect(self._retint)

    def _glow(self, v):
        self._fx.setBlurRadius(14 + 16 * float(v))
        self._fx.setColor(alpha(PAL.accent, int(70 + 130 * float(v))))

    def _retint(self):
        self._glow(self.hv.v)
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(200, self.height())

    def enterEvent(self, e):
        self.hv.to(1)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.hv.to(0)
        super().leaveEvent(e)

    def paintEvent(self, _e):
        pal = PAL
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        h = self.hv.v
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        g = QLinearGradient(r.left(), 0, r.right(), 0)
        g.setColorAt(0, lerp(pal.btn_a, pal.btn_a_h, h))
        g.setColorAt(1, lerp(themes.mix(pal.accent3, "#000000", 0.12), pal.accent3, h))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(g))
        p.drawRoundedRect(r, 12, 12)
        sheen = QLinearGradient(0, r.top(), 0, r.bottom())
        sheen.setColorAt(0, QColor(255, 255, 255, int(30 + 40 * h)))
        sheen.setColorAt(0.6, QColor(255, 255, 255, 0))
        p.setBrush(QBrush(sheen))
        p.drawRoundedRect(r, 12, 12)
        fg = QColor(pal.on_accent)
        draw_icon(p, "discord", QRectF(14 + 2 * h, (self.height() - 22) / 2, 22, 22), fg)
        f = QFont(self.font())
        f.setBold(True)
        f.setPixelSize(13)
        p.setFont(f)
        p.setPen(fg)
        p.drawText(QRectF(44 + 2 * h, 0, self.width() - 52, self.height()), Qt.AlignVCenter | Qt.AlignLeft, "Discord beitreten")


class GradientLine(QWidget):
    """Duenne Akzentlinie mit wanderndem Lichtreflex."""

    def __init__(self):
        super().__init__()
        self.setFixedHeight(3)
        self.pos = -0.3
        self.anim = QVariantAnimation(self)
        self.anim.setDuration(5200)
        self.anim.setStartValue(-0.3)
        self.anim.setEndValue(1.3)
        self.anim.setLoopCount(-1)
        self.anim.valueChanged.connect(self._t)
        self.anim.start()

    def _t(self, v):
        self.pos = float(v)
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        g = QLinearGradient(0, 0, self.width(), 0)
        g.setColorAt(0, QColor(PAL.accent))
        g.setColorAt(1, QColor(PAL.accent3))
        p.fillRect(self.rect(), QBrush(g))
        s = QLinearGradient(self.width() * (self.pos - 0.15), 0, self.width() * (self.pos + 0.15), 0)
        s.setColorAt(0, QColor(255, 255, 255, 0))
        s.setColorAt(0.5, QColor(255, 255, 255, 150))
        s.setColorAt(1, QColor(255, 255, 255, 0))
        p.fillRect(self.rect(), QBrush(s))


class Toggle(QAbstractButton):
    def __init__(self):
        super().__init__()
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(46, 26)
        self._pos = 0.0
        self._anim = QPropertyAnimation(self, b"offset", self)
        self._anim.setDuration(140)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self.toggled.connect(self._animate)
        self.hv = HoverValue(self, 120)
        BUS.changed.connect(self.update)

    def _get(self) -> float:
        return self._pos

    def _set(self, v: float) -> None:
        self._pos = v
        self.update()

    offset = Property(float, _get, _set)

    def enterEvent(self, e):
        self.hv.to(1)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.hv.to(0)
        super().leaveEvent(e)

    def _animate(self, on: bool):
        self._anim.stop()
        self._anim.setEndValue(1.0 if on else 0.0)
        self._anim.start()

    def set_checked_silent(self, on: bool):
        self.blockSignals(True)
        self.setChecked(on)
        self.blockSignals(False)
        self._anim.stop()
        self._pos = 1.0 if on else 0.0
        self.update()

    def paintEvent(self, _e):
        pal = PAL
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(1, 1, self.width() - 2, self.height() - 2)
        t = self._pos
        col = lerp(lerp(pal.toggle_off, pal.toggle_off_h, self.hv.v), pal.accent, t)
        if not self.isEnabled():
            col.setAlpha(110)
        if self.hv.v > 0.02 and self.isEnabled() and t > 0.5:
            p.setPen(QPen(alpha(pal.accent2, int(90 * self.hv.v)), 3))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(r.adjusted(-0.5, -0.5, 0.5, 0.5), r.height() / 2, r.height() / 2)
        p.setPen(Qt.NoPen)
        p.setBrush(col)
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        d = r.height() - 6
        x = r.left() + 3 + (r.width() - d - 6) * t
        p.setBrush(QColor("#ffffff" if self.isEnabled() else "#9A9AB0"))
        p.drawEllipse(QRectF(x, r.top() + 3, d, d))


class Chips(QWidget):
    changed = Signal(str)

    def __init__(self, names: list[str], current: Optional[str] = None):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        self.buttons: dict[str, AnimButton] = {}
        for n in names:
            b = AnimButton(n, "chip")
            b.clicked.connect(lambda _c=False, name=n: self.select(name))
            lay.addWidget(b)
            self.buttons[n] = b
        lay.addStretch(1)
        self.current = names[0]
        self.select(current or names[0], emit=False)

    def select(self, name: str, emit: bool = True):
        for n, b in self.buttons.items():
            b.setChecked(n == name)
            b.update()
        self.current = name
        if emit:
            self.changed.emit(name)


class RingGauge(QWidget):
    def __init__(self, c1: str = "@accent", c2: str = "@accent3", minimum: int = 140):
        super().__init__()
        self.c1, self.c2 = c1, c2
        self._target = 0.0
        self._shown = 0.0
        self.text = "–"
        self.sub = ""
        self.setMinimumSize(minimum, minimum)
        self._anim = QPropertyAnimation(self, b"shown", self)
        self._anim.setDuration(450)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    def _g(self) -> float:
        return self._shown

    def _s(self, v: float) -> None:
        self._shown = v
        self.update()

    shown = Property(float, _g, _s)

    def set_value(self, frac: Optional[float], text: str, sub: str = ""):
        self.text, self.sub = text, sub
        frac = max(0.0, min(1.0, frac or 0.0))
        if abs(frac - self._target) > 0.004:
            self._target = frac
            self._anim.stop()
            self._anim.setStartValue(self._shown)
            self._anim.setEndValue(frac)
            self._anim.start()
        else:
            self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        side = min(self.width(), self.height())
        th = max(10, side * 0.085)
        r = QRectF((self.width() - side) / 2 + th, (self.height() - side) / 2 + th, side - 2 * th, side - 2 * th)
        p.setPen(QPen(QColor(PAL.track), th, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(r, 0, 360 * 16)
        t = self._shown
        col = lerp(rc(self.c1), rc(self.c2), t)
        if t > 0.8:
            col = lerp(col, RED, (t - 0.8) / 0.2)
        if t > 0.004:
            p.setPen(QPen(alpha(col, 50), th * 1.9, Qt.SolidLine, Qt.RoundCap))
            p.drawArc(r, 90 * 16, int(-360 * 16 * t))
            p.setPen(QPen(col, th, Qt.SolidLine, Qt.RoundCap))
            p.drawArc(r, 90 * 16, int(-360 * 16 * t))
        p.setPen(QColor(PAL.text))
        f = QFont(self.font())
        f.setPixelSize(int(side * 0.22))
        f.setBold(True)
        p.setFont(f)
        p.drawText(QRectF(r.left(), r.top() + r.height() * 0.22, r.width(), r.height() * 0.36), Qt.AlignCenter, self.text)
        f.setPixelSize(max(10, int(side * 0.085)))
        f.setBold(False)
        p.setFont(f)
        p.setPen(QColor(PAL.muted))
        p.drawText(QRectF(r.left(), r.top() + r.height() * 0.56, r.width(), r.height() * 0.2), Qt.AlignCenter, self.sub)


class LineChart(QWidget):
    def __init__(self, vmax: Optional[float] = 100.0, unit: str = "%", maxlen: int = 90, show_legend: bool = True):
        super().__init__()
        self.vmax, self.unit, self.maxlen, self.show_legend = vmax, unit, maxlen, show_legend
        self.series: dict[str, tuple[QColor, deque]] = {}
        self.setMinimumHeight(120)

    def add_series(self, name: str, color: str):
        self.series[name] = (color, deque(maxlen=self.maxlen))

    def push(self, name: str, value: Optional[float]):
        self.series[name][1].append(value)

    def set_data(self, name: str, values: list):
        self.series[name][1].clear()
        self.series[name][1].extend(values)
        self.update()

    def clear(self):
        for _c, d in self.series.values():
            d.clear()
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        top_pad, bot_pad = (30 if self.show_legend else 8), 8
        plot_h = max(10, h - top_pad - bot_pad)
        vals = [v for _c, d in self.series.values() for v in d if v is not None]
        vmax = self.vmax or max(max(vals, default=1.0) * 1.25, 1.0)
        p.setPen(QPen(QColor(PAL.grid), 1))
        for i in range(5):
            y = top_pad + plot_h * i / 4
            p.drawLine(QPointF(0, y), QPointF(w, y))
        p.setPen(QColor(PAL.dim))
        f = QFont(self.font())
        f.setPixelSize(10)
        p.setFont(f)
        p.drawText(QRectF(w - 70, top_pad - 14, 66, 12), Qt.AlignRight, f"{vmax:.0f}{self.unit}")
        x = 4
        for name, (spec, data) in self.series.items():
            col = rc(spec)
            if self.show_legend:
                p.setBrush(col)
                p.setPen(Qt.NoPen)
                p.drawEllipse(QPointF(x + 4, 14), 4, 4)
                p.setPen(QColor(PAL.muted))
                f2 = QFont(self.font())
                f2.setPixelSize(12)
                p.setFont(f2)
                p.drawText(QPointF(x + 14, 18), name)
                x += 24 + QFontMetrics(f2).horizontalAdvance(name)
            pts = list(data)
            if len(pts) < 2:
                continue
            step = w / max(1, self.maxlen - 1)
            x0 = w - step * (len(pts) - 1)
            path = QPainterPath()
            started = False
            for i, v in enumerate(pts):
                px = x0 + i * step
                if v is None:
                    p.setPen(QPen(QColor(RED), 2))
                    p.drawLine(QPointF(px, h - bot_pad), QPointF(px, h - bot_pad - 14))
                    started = False
                    continue
                py = top_pad + plot_h * (1 - min(1.0, v / vmax))
                if not started:
                    path.moveTo(px, py)
                    started = True
                else:
                    path.lineTo(px, py)
            if started and len(self.series) == 1:
                fill = QPainterPath(path)
                fill.lineTo(QPointF(w, h - bot_pad))
                fill.lineTo(QPointF(x0, h - bot_pad))
                g = QLinearGradient(0, top_pad, 0, h)
                g.setColorAt(0, alpha(col, 70))
                g.setColorAt(1, alpha(col, 0))
                p.setPen(Qt.NoPen)
                p.setBrush(g)
                p.drawPath(fill)
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(alpha(col, 60), 5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.drawPath(path)
            p.setPen(QPen(col, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.drawPath(path)


class Sparkline(QWidget):
    """Kleine Verlaufslinie fuer Metrik-Karten."""

    def __init__(self, color: str = "@accent", maxlen: int = 60, vmax: Optional[float] = 100.0):
        super().__init__()
        self.color, self.maxlen, self.vmax = color, maxlen, vmax
        self.data: deque = deque(maxlen=maxlen)
        self.setFixedHeight(46)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    def push(self, v: float):
        self.data.append(v)
        self.update()

    def paintEvent(self, _e):
        if len(self.data) < 2:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        vmax = self.vmax or max(max(self.data), 1.0) * 1.2
        step = w / (self.maxlen - 1)
        x0 = w - step * (len(self.data) - 1)
        path = QPainterPath()
        for i, v in enumerate(self.data):
            x, y = x0 + i * step, h - 3 - (h - 8) * min(1.0, v / vmax)
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
        fill = QPainterPath(path)
        fill.lineTo(w, h)
        fill.lineTo(x0, h)
        col = rc(self.color)
        g = QLinearGradient(0, 0, 0, h)
        g.setColorAt(0, alpha(col, 80))
        g.setColorAt(1, alpha(col, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(g)
        p.drawPath(fill)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(col, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(path)


class OrbBanner(Card):
    """Hero-Banner mit langsam wandernden Farb-Orbs (animiert nur, solange sichtbar)."""

    def __init__(self):
        super().__init__("hero")
        self.t0 = time.time()
        self.timer = QTimer(self)
        self.timer.setInterval(50)
        self.timer.timeout.connect(self.update)

    def showEvent(self, e):
        self.timer.start()
        super().showEvent(e)

    def hideEvent(self, e):
        self.timer.stop()
        super().hideEvent(e)

    def paintEvent(self, e):
        super().paintEvent(e)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), self.radius, self.radius)
        p.setClipPath(path)
        t = time.time() - self.t0
        w, h = self.width(), self.height()
        for col, sp, ph in ((PAL.accent, 0.35, 0.0), (PAL.accent3, 0.27, 2.1), (PAL.accent2, 0.21, 4.2)):
            cx = w * (0.25 + 0.5 * (0.5 + 0.5 * math.sin(t * sp + ph)))
            cy = h * (0.35 + 0.3 * math.sin(t * sp * 1.3 + ph))
            g = QRadialGradient(cx, cy, h * 1.1)
            g.setColorAt(0, alpha(col, 46))
            g.setColorAt(1, alpha(col, 0))
            p.setPen(Qt.NoPen)
            p.setBrush(g)
            p.drawEllipse(QPointF(cx, cy), h * 1.1, h * 1.1)


class StatTile(Card):
    def __init__(self, title: str, color: Optional[str] = None):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(2)
        self.title = label(title.upper(), "dim")
        self.value = ThemedLabel("–", "big", color)
        self.sub = label("", "muted")
        for w in (self.title, self.value, self.sub):
            w.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            lay.addWidget(w)

    def set(self, value: str, sub: str = ""):
        self.value.setText(value)
        self.sub.setText(sub)


class TweakRow(HoverFrame):
    """Eine Zeile: Wirkungs-Punkt, Name, EIN Satz, Tags, Schalter. Details im Tooltip."""
    toggled = Signal(str, bool)

    def __init__(self, tweak, admin_ok: bool):
        super().__init__(12)
        self.tweak = tweak
        self.locked = tweak.admin and not admin_ok
        self.unavailable = False
        self.setFixedHeight(68)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 8, 16, 8)
        lay.setSpacing(12)
        col = QVBoxLayout()
        col.setSpacing(2)
        head = QHBoxLayout()
        head.setSpacing(8)
        if tweak.evidence:
            dot = QLabel()
            dot.setFixedSize(9, 9)
            dot.setStyleSheet("background:" + EVIDENCE_COLORS.get(tweak.evidence, "#6E6E8A") + ";border-radius:4px;")
            dot.setToolTip(EVIDENCE_TEXT.get(tweak.evidence, ""))
            head.addWidget(dot)
        name = QLabel(tweak.name)
        name.setStyleSheet("font-size:14px;font-weight:600;")
        name.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        head.addWidget(name)
        if tweak.recommended:
            star = ThemedLabel("★", "", "@accent2")
            star.setToolTip("Wird von Auto Optimize gesetzt")
            head.addWidget(star)
        head.addStretch(1)
        col.addLayout(head)
        self.desc = ElidedLabel(tweak.description, "muted")
        col.addWidget(self.desc)
        lay.addLayout(col, 1)
        tags = QHBoxLayout()
        tags.setSpacing(6)
        for t in tweak.tags:
            tags.addWidget(pill(t, TAG_COLORS.get(t, GREY)))
        if tweak.risk != "niedrig":
            tags.addWidget(pill("RISIKO", YELLOW))
        if tweak.admin:
            tags.addWidget(pill("ADMIN", RED if self.locked else GREY))
        lay.addLayout(tags)
        self.toggle = Toggle()
        lay.addWidget(self.toggle)
        self.toggle.clicked.connect(lambda c: self.toggled.emit(self.tweak.id, bool(c)))
        tip = f"{tweak.description}\n\n{tweak.impact}"
        if tweak.evidence:
            tip += f"\n\n{EVIDENCE_TEXT.get(tweak.evidence, '')}"
        if tweak.restart and tweak.restart != "Nein":
            tip += f"\nWirksam: {tweak.restart}"
        if tweak.risk != "niedrig":
            tip += f"\nRisiko: {tweak.risk}"
        self.base_tip = tip
        if self.locked:
            tip += "\n\nBraucht Administratorrechte."
            self.toggle.setEnabled(False)
            self.desc.setText("Gesperrt: starte SquallowTweaks als Administrator, um diesen Tweak zu nutzen.")
        self.setToolTip(tip)

    def set_state(self, state: str, msg: str = ""):
        from engine import STATUS_ACTIVE, STATUS_UNKNOWN
        self.toggle.set_checked_silent(state == STATUS_ACTIVE)
        self.toggle.setEnabled(state != STATUS_UNKNOWN and not self.locked)
        self.unavailable = state == STATUS_UNKNOWN
        if self.locked:
            pass                                    # Hinweistext bleibt (siehe __init__)
        elif self.unavailable:
            reason = msg or "Auf diesem System nicht verfügbar."
            self.desc.setText("Nicht verfügbar: " + reason)
            self.setToolTip(self.base_tip + "\n\nNicht verfügbar: " + reason)
        else:
            self.desc.setText(self.tweak.description)
            self.setToolTip(self.base_tip)
        self.update()

    def paintEvent(self, e):
        super().paintEvent(e)
        if self.unavailable:
            p = QPainter(self)
            p.setPen(Qt.NoPen)
            p.setBrush(alpha(PAL.bg, 120))
            p.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 12, 12)


class IconTile(QWidget):
    """Abgerundete Kachel mit Icon in Akzentfarbe (Karten-Kopf)."""

    def __init__(self, icon: str, color: str = "@accent", size: int = 40):
        super().__init__()
        self.icon_name, self.color = icon, color
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        BUS.changed.connect(self.update)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = rc(self.color)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(QPen(alpha(c, 70), 1))
        p.setBrush(alpha(c, 34))
        p.drawRoundedRect(r, r.width() * 0.3, r.width() * 0.3)
        s = self.width() * 0.52
        draw_icon(p, self.icon_name, QRectF((self.width() - s) / 2, (self.height() - s) / 2, s, s), c)


class FracBar(QWidget):
    """Duenner Fortschrittsbalken (animiert, Theme-Verlauf)."""

    def __init__(self, height: int = 6):
        super().__init__()
        self.setFixedHeight(height)
        self._shown = 0.0
        self._anim = QPropertyAnimation(self, b"shown", self)
        self._anim.setDuration(500)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        BUS.changed.connect(self.update)

    def _g(self) -> float:
        return self._shown

    def _s(self, v: float) -> None:
        self._shown = v
        self.update()

    shown = Property(float, _g, _s)

    def set_fraction(self, frac: float):
        frac = max(0.0, min(1.0, frac))
        self._anim.stop()
        self._anim.setStartValue(self._shown)
        self._anim.setEndValue(frac)
        self._anim.start()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect())
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(PAL.track))
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        if self._shown > 0.004:
            w = max(r.height(), r.width() * self._shown)
            g = QLinearGradient(0, 0, r.width(), 0)
            g.setColorAt(0, QColor(PAL.accent))
            g.setColorAt(1, QColor(PAL.accent3))
            p.setBrush(QBrush(g))
            p.drawRoundedRect(QRectF(0, 0, w, r.height()), r.height() / 2, r.height() / 2)


NA = "Nicht verfügbar"


class HwCard(Card):
    """Hardware-Karte: Modell, aktuelle Auslastung, Verlauf und drei Detailwerte. Fehlende Werte zeigen 'Nicht verfügbar'."""

    def __init__(self, title: str, icon: str, stat_titles: tuple, color: str = "@accent2"):
        super().__init__()
        self.stat_titles = stat_titles
        v = QVBoxLayout(self)
        v.setContentsMargins(18, 16, 18, 14)
        v.setSpacing(0)
        head = QHBoxLayout()
        head.setSpacing(12)
        head.addWidget(IconTile(icon, color))
        col = QVBoxLayout()
        col.setSpacing(0)
        col.addWidget(label(title, "h2"))
        self.model = ElidedLabel(NA, "muted")
        col.addWidget(self.model)
        head.addLayout(col, 1)
        head.addWidget(pill("LIVE", GREEN), 0, Qt.AlignTop)
        v.addLayout(head)
        v.addSpacing(8)
        self.value = ThemedLabel("–", "big", None, "font-size:36px;font-weight:700;")
        self.value.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        v.addWidget(self.value)
        self.spark = Sparkline(color)
        v.addWidget(self.spark)
        v.addSpacing(8)
        foot = QHBoxLayout()
        foot.setSpacing(10)
        self.stat_values = []
        for t in stat_titles:
            c = QVBoxLayout()
            c.setSpacing(1)
            c.addWidget(label(t.upper(), "dim"))
            val = ThemedLabel("–", "", None, "font-size:13px;font-weight:600;")
            val.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            val.setMinimumWidth(0)
            c.addWidget(val)
            foot.addLayout(c, 1)
            self.stat_values.append(val)
        v.addLayout(foot)

    def set_model(self, text, tip: str = ""):
        self.model.setText(text or NA)
        self.model.setToolTip(text or "")

    def set_usage(self, text: Optional[str], number: Optional[float]):
        self.value.setText(text if text is not None else NA)
        self.value.set_css("font-size:36px;font-weight:700;" if text is not None else "font-size:20px;font-weight:600;")
        if number is not None:
            self.spark.push(number)

    def set_stats(self, values: list, tips: Optional[list] = None):
        for i, (lab, val) in enumerate(zip(self.stat_values, values)):
            lab.setText(val if val is not None else NA)
            lab.set_color(None if val is not None else "@dim")
            lab.set_css("font-size:13px;font-weight:600;" if val is not None else "font-size:11px;font-weight:600;")
            tip = tips[i] if tips and i < len(tips) and tips[i] else ""
            lab.setToolTip(tip or (val or ""))


class ThemeSwatch(QAbstractButton):
    """Auswahlkachel fuer ein Theme: Mini-Vorschau der echten Farben, Name, Haken bei Auswahl."""

    def __init__(self, key: str):
        super().__init__()
        self.key = key
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setFixedSize(118, 78)
        self.hv = HoverValue(self, 150)
        self.setToolTip(themes.THEMES[key].name)
        BUS.changed.connect(self.update)

    def enterEvent(self, e):
        self.hv.to(1)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.hv.to(0)
        super().leaveEvent(e)

    def paintEvent(self, _e):
        pal = themes.resolve(self.key, store()["custom_accent"])
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        h = self.hv.v
        on = self.isChecked()
        r = QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5)
        outer = PAL
        p.setPen(QPen(QColor(outer.accent) if on else lerp(outer.border, outer.border_hi, h), 2 if on else 1))
        p.setBrush(lerp(outer.card, outer.card2, h))
        p.drawRoundedRect(r, 12, 12)
        pv = QRectF(r.left() + 8, r.top() + 8, r.width() - 16, 38)
        path = QPainterPath()
        path.addRoundedRect(pv, 8, 8)
        p.save()
        p.setClipPath(path)
        p.fillRect(pv, QColor(pal.bg))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(pal.card))
        p.drawRoundedRect(QRectF(pv.left() + 14, pv.top() + 8, pv.width() - 22, pv.height() - 14), 5, 5)
        p.setBrush(QColor(pal.sidebar))
        p.drawRect(QRectF(pv.left(), pv.top(), 11, pv.height()))
        g = QLinearGradient(pv.left() + 20, 0, pv.right() - 10, 0)
        g.setColorAt(0, QColor(pal.accent))
        g.setColorAt(1, QColor(pal.accent3))
        p.setBrush(QBrush(g))
        p.drawRoundedRect(QRectF(pv.left() + 20, pv.top() + 15, pv.width() * 0.45, 5), 2.5, 2.5)
        p.setBrush(QColor(pal.accent2))
        p.drawEllipse(QPointF(pv.right() - 14, pv.top() + 17), 4, 4)
        p.restore()
        f = QFont(self.font())
        f.setPixelSize(12)
        f.setWeight(QFont.DemiBold if on else QFont.Medium)
        p.setFont(f)
        p.setPen(QColor(outer.text) if on else lerp(outer.muted, outer.text, h))
        p.drawText(QRectF(r.left() + 8, pv.bottom() + 4, r.width() - 16, 20), Qt.AlignVCenter | Qt.AlignLeft, pal.name)
        if on:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(outer.accent))
            p.drawEllipse(QPointF(r.right() - 17, pv.bottom() + 14), 7, 7)
            draw_icon(p, "check", QRectF(r.right() - 22, pv.bottom() + 9, 10, 10), QColor(outer.on_accent))


class AvatarBadge(QWidget):
    """Runder Avatar mit Verlaufsring (Profil-Karte oben in der Sidebar)."""

    def __init__(self, image_path: str, size: int = 72):
        super().__init__()
        self.pix = QPixmap(image_path)
        self.setFixedSize(size, size)
        self.hv = HoverValue(self, 220)
        BUS.changed.connect(self.update)

    def enterEvent(self, e):
        self.hv.to(1)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.hv.to(0)
        super().leaveEvent(e)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        h = self.hv.v
        r = QRectF(self.rect()).adjusted(3, 3, -3, -3)
        if h > 0.02:
            p.setPen(QPen(alpha(PAL.accent, int(60 * h)), 4))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(r.adjusted(-1.5, -1.5, 1.5, 1.5))
        g = QLinearGradient(r.topLeft(), r.bottomRight())
        g.setColorAt(0, QColor(PAL.accent2))
        g.setColorAt(1, QColor(PAL.accent3))
        p.setPen(QPen(QBrush(g), 2))
        p.setBrush(QColor(PAL.card2))
        p.drawEllipse(r)
        if not self.pix.isNull():
            inner = r.adjusted(7, 7, -7, -7)
            path = QPainterPath()
            path.addEllipse(inner)
            p.setClipPath(path)
            side = inner.width()
            sc = self.pix.scaled(int(side * self.devicePixelRatioF()), int(side * self.devicePixelRatioF()),
                                 Qt.KeepAspectRatio, Qt.SmoothTransformation)
            p.drawPixmap(QPointF(inner.center().x() - sc.width() / sc.devicePixelRatioF() / 2,
                                 inner.center().y() - sc.height() / sc.devicePixelRatioF() / 2), sc)


class ProfileCard(Card):
    """Kopf der Sidebar: Avatar, Name, Version/Modus (wie die Profil-Karte im Vorbild)."""

    def __init__(self, image_path: str, version: str, mode_text: str):
        super().__init__()
        self.hover_on = True
        v = QVBoxLayout(self)
        v.setContentsMargins(14, 16, 14, 14)
        v.setSpacing(4)
        v.addWidget(AvatarBadge(image_path), 0, Qt.AlignHCenter)
        v.addSpacing(4)
        self.name = QLabel()
        self.name.setTextFormat(Qt.RichText)
        self.name.setAlignment(Qt.AlignCenter)
        self.name.setStyleSheet("font-size:15px;font-weight:700;")
        self._retitle()
        BUS.changed.connect(self._retitle)
        v.addWidget(self.name)
        info = ThemedLabel(f"V{version}  ·  {mode_text}".upper(), "", "@dim", "font-size:10px;font-weight:700;letter-spacing:1.5px;")
        info.setAlignment(Qt.AlignCenter)
        v.addWidget(info)

    def _retitle(self):
        self.name.setText(f"Squallow<span style='color:{PAL.accent2};'>Tweaks</span>")


class HeroStat(Card):
    """Kleine Kennzahl-Kachel im Hero-Bereich (Betriebszeit, Score, Applied Tweaks). Zahlen kommen nur aus echten Messwerten."""

    def __init__(self, icon: str, title: str, color: str = "@accent2", bar: bool = False):
        super().__init__()
        h = QHBoxLayout(self)
        h.setContentsMargins(14, 10, 14, 10)
        h.setSpacing(12)
        h.addWidget(IconTile(icon, color, 38))
        col = QVBoxLayout()
        col.setSpacing(1)
        col.addWidget(label(title, "section"))
        row = QHBoxLayout()
        row.setSpacing(6)
        self.value = ThemedLabel("–", "", None, "font-size:22px;font-weight:800;")
        self.suffix = label("", "dim")
        row.addWidget(self.value)
        row.addWidget(self.suffix, 0, Qt.AlignBottom)
        row.addStretch(1)
        col.addLayout(row)
        self.bar = FracBar(4) if bar else None
        if self.bar:
            col.addSpacing(3)
            col.addWidget(self.bar)
        h.addLayout(col, 1)
        self._shown, self._known = 0, False
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(450)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(lambda x: self.value.setText(str(int(round(float(x))))))

    def set_text(self, value: str, suffix: str = ""):
        self.value.setText(value)
        self.suffix.setText(suffix)

    def set_counts(self, active: Optional[int], total: int):
        """Applied Tweaks. active=None -> noch nicht gelesen: '–' statt einer erfundenen 0."""
        if active is None:
            self._known = False
            self.set_text("–", "Status wird gelesen")
            if self.bar:
                self.bar.set_fraction(0)
            return
        if not self._known:
            self._known, self._shown = True, 0
        self._anim.stop()
        self._anim.setStartValue(float(self._shown))
        self._anim.setEndValue(float(active))
        self._anim.start()
        self._shown = active
        self.suffix.setText(f"von {total} aktiv")
        if self.bar:
            self.bar.set_fraction(active / total if total else 0.0)


class DiscordCard(Card):
    """Community-Karte rechts im Dashboard mit dem Discord-Button."""

    def __init__(self, url: str = DISCORD_URL):
        super().__init__("hero")
        v = QVBoxLayout(self)
        v.setContentsMargins(20, 18, 20, 18)
        v.setSpacing(8)
        top = QHBoxLayout()
        top.addWidget(IconTile("discord", "@accent2", 46))
        top.addStretch(1)
        top.addWidget(label("COMMUNITY", "section"), 0, Qt.AlignTop)
        v.addLayout(top)
        v.addSpacing(4)
        title = label("Discord beitreten", "h2")
        title.setStyleSheet("font-size:20px;font-weight:800;")
        v.addWidget(title)
        v.addWidget(label("Tausche dich mit der Community aus, bekomme Hilfe und erfahre als Erster von neuen Tweaks.", "muted", True))
        box = QFrame()
        box.setObjectName("dcbox")
        bl = QVBoxLayout(box)
        bl.setContentsMargins(12, 10, 12, 10)
        bl.setSpacing(5)
        for text in ("Support & Hilfe", "Updates & neue Tweaks", "Feedback & Ideen"):
            r = QHBoxLayout()
            r.setSpacing(8)
            r.addWidget(ThemedLabel("✔", "", "@accent2", "font-size:11px;font-weight:700;"))
            r.addWidget(label(text, "muted"), 1)
            bl.addLayout(r)
        v.addWidget(box)
        v.addStretch(1)
        self.button = DiscordButton(url)
        v.addWidget(self.button)


class TempMonitorCard(Card):
    """Grosser Temperatur-Monitor (CPU/GPU umschaltbar) mit Verlauf. Ohne Messwert: 'Nicht verfügbar' + Hinweis."""

    def __init__(self, missing_hint: str = ""):
        super().__init__()
        self.missing_hint = missing_hint
        self.sel = "CPU"
        self.cur = {"CPU": None, "GPU": None}
        self.note = {"CPU": "", "GPU": ""}
        self.hist = {"CPU": deque(maxlen=90), "GPU": deque(maxlen=90)}
        v = QVBoxLayout(self)
        v.setContentsMargins(22, 18, 22, 16)
        v.setSpacing(2)
        head = QHBoxLayout()
        col = QVBoxLayout()
        col.setSpacing(0)
        col.addWidget(label("AKTIVER MONITOR", "dim"))
        self.title = label("CPU-Temperatur", "h2")
        self.title.setStyleSheet("font-size:22px;font-weight:800;")
        col.addWidget(self.title)
        head.addLayout(col, 1)
        self.chips = Chips(["CPU", "GPU"], "CPU")
        self.chips.changed.connect(self._select)
        head.addWidget(self.chips, 0, Qt.AlignTop)
        v.addLayout(head)
        row = QHBoxLayout()
        row.setSpacing(6)
        self.value = ThemedLabel("–", "", None, "font-size:60px;font-weight:800;")
        self.unit = ThemedLabel("°C", "", "@accent2", "font-size:22px;font-weight:600;")
        row.addWidget(self.value)
        row.addWidget(self.unit, 0, Qt.AlignBottom)
        row.addStretch(1)
        v.addLayout(row)
        self.info = label("", "muted", True)
        v.addWidget(self.info)
        self.chart = LineChart(100.0, "°", 90, False)
        self.chart.setMinimumHeight(110)
        self.chart.add_series("T", "@accent2")
        v.addWidget(self.chart, 1)

    def _select(self, name: str):
        self.sel = name
        self._render()

    def push(self, cpu: Optional[float], gpu: Optional[float], cpu_note: str = "", gpu_note: str = ""):
        self.cur, self.note = {"CPU": cpu, "GPU": gpu}, {"CPU": cpu_note, "GPU": gpu_note}
        self.hist["CPU"].append(cpu)
        self.hist["GPU"].append(gpu)
        self._render()

    def _render(self):
        val = self.cur[self.sel]
        self.title.setText(f"{self.sel}-Temperatur")
        if val is None:
            self.value.set_css("font-size:26px;font-weight:700;")
            self.value.setText("Nicht verfügbar")
            self.unit.setText("")
            self.info.setText(self.missing_hint)
        else:
            self.value.set_css("font-size:60px;font-weight:800;")
            self.value.setText(f"{val:.0f}")
            self.unit.setText("°C")
            self.info.setText(self.note[self.sel])
        self.chart.set_data("T", list(self.hist[self.sel]))


class Toast(QWidget):
    """Kurze Rueckmeldung unten mittig (z. B. 'Tweak angewendet'), blendet sich selbst aus."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.text, self.ok, self.op = "", True, 0.0
        self.anim = QVariantAnimation(self)
        self.anim.setDuration(220)
        self.anim.valueChanged.connect(self._fade)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._hide)
        self.hide()

    def _fade(self, v):
        self.op = float(v)
        self.update()
        if self.op <= 0.01 and self.anim.endValue() == 0.0:
            self.hide()

    def _hide(self):
        self.anim.stop()
        self.anim.setStartValue(self.op)
        self.anim.setEndValue(0.0)
        self.anim.start()

    def show_message(self, text: str, ok: bool = True, ms: int = 5000):
        self.text, self.ok = text, ok
        fm = QFontMetrics(self.font())
        w = min(self.parentWidget().width() - 60, fm.horizontalAdvance(text) + 70)
        self.setFixedSize(max(260, w), 46)
        self.place()
        self.show()
        self.raise_()
        self.anim.stop()
        self.anim.setStartValue(self.op)
        self.anim.setEndValue(1.0)
        self.anim.start()
        self.timer.start(ms)

    def place(self):
        par = self.parentWidget()
        if par is not None:
            self.move((par.width() - self.width()) // 2, par.height() - self.height() - 26)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setOpacity(self.op)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        col = QColor(GREEN if self.ok else RED)
        p.setPen(QPen(alpha(col, 150), 1))
        c = QColor(PAL.card2)
        c.setAlpha(250)
        p.setBrush(c)
        p.drawRoundedRect(r, 14, 14)
        p.setPen(Qt.NoPen)
        p.setBrush(col)
        p.drawEllipse(QPointF(r.left() + 22, r.center().y()), 5, 5)
        p.setPen(QColor(PAL.text))
        p.drawText(QRectF(r.left() + 40, r.top(), r.width() - 52, r.height()), Qt.AlignVCenter | Qt.AlignLeft,
                   QFontMetrics(self.font()).elidedText(self.text, Qt.ElideRight, int(r.width() - 52)))


def make_scroll(widget: QWidget) -> QScrollArea:
    """Ganze Seite scrollt als Einheit; ein Mausrad-Schritt = etwa eine Zeile (normales Windows-Gefuehl)."""
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.NoFrame)
    area.setWidget(widget)
    area.viewport().setAutoFillBackground(False)       # Hintergrund-Effekt scheint durch
    widget.setAutoFillBackground(False)
    area.verticalScrollBar().setSingleStep(34)
    return area


def apply_dark_titlebar(win: QWidget) -> None:
    """Titelleiste passend zum aktiven Theme (Windows 10/11); heller Modus bei hellem Theme."""
    if os.name != "nt":
        return
    try:
        import ctypes
        hwnd = int(win.winId())
        dwm = ctypes.windll.dwmapi

        def put(attr: int, val: int):
            v = ctypes.c_int(val)
            dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(v), ctypes.sizeof(v))

        def bgr(h: str) -> int:
            r, g, b = themes.to_rgb(h)
            return (b << 16) | (g << 8) | r
        dark = 0 if PAL.light else 1
        put(20, dark)                    # DWMWA_USE_IMMERSIVE_DARK_MODE
        put(19, dark)                    # aeltere Windows-10-Builds
        put(35, bgr(PAL.sidebar))        # Titelleistenfarbe (Windows 11)
        put(36, bgr(PAL.text))           # Titeltext
        put(34, bgr(PAL.sidebar))        # Rahmenfarbe
    except Exception:  # noqa: BLE001
        pass
