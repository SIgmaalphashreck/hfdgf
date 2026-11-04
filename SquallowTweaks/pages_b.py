"""SquallowTweaks - Seiten Teil 2: Prozesse, Netzwerk, Bereinigung, Einstellungen."""
from __future__ import annotations

import os
import webbrowser

import psutil
from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QAbstractItemView, QColorDialog, QGridLayout, QHBoxLayout, QHeaderView, QLineEdit, QMessageBox,
                               QProgressBar, QStyle, QStyledItemDelegate, QTableView, QVBoxLayout, QWidget)

import cleaner
import engine as eng
import netlab
import service as svc
import themes
from pages_a import BasePage, page_layout
from themes import PAL
from ui_common import (CYAN, GREEN, PINK, RED, YELLOW, AnimButton, Card, Chips, LineChart, StatTile, ThemeSwatch, Toggle, alpha,
                       apply_theme, effects_on, label, lerp, set_effects, store)

# ===========================================================================
# Prozesse
# ===========================================================================
BROWSERS = ("chrome", "msedge", "firefox", "opera", "brave", "vivaldi")
SYSTEM = ("system", "registry", "smss", "csrss", "wininit", "services", "lsass", "winlogon", "svchost", "dwm", "fontdrvhost",
          "memory compression", "msmpeng", "searchindexer", "runtimebroker", "sihost", "taskhostw", "ctfmon", "audiodg", "wudfhost")
GAMING = ("fortnite", "epic", "easyanticheat", "eac", "steam", "discord", "riot", "battle.net")
PROTECTED = {"system", "registry", "smss.exe", "csrss.exe", "wininit.exe", "services.exe", "lsass.exe", "winlogon.exe", "svchost.exe",
             "dwm.exe", "fontdrvhost.exe", "memory compression"}
CAT_COLORS = {"game": CYAN, "browser": YELLOW, "system": "#6E6E8A"}      # "app" folgt dem Theme (PAL.accent2)


def categorize(name: str) -> str:
    n = name.lower().replace(".exe", "")
    if any(g in n for g in GAMING):
        return "game"
    if any(b in n for b in BROWSERS):
        return "browser"
    if n in SYSTEM:
        return "system"
    return "app"


class ProcModel(QAbstractTableModel):
    HEAD = ["PROZESS", "CPU", "RAM", "THREADS", "PID"]

    def __init__(self):
        super().__init__()
        self.rows: list = []

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return len(self.HEAD)

    def headerData(self, s, o, role=Qt.DisplayRole):
        if o == Qt.Horizontal and role == Qt.DisplayRole:
            return self.HEAD[s]
        if o == Qt.Horizontal and role == Qt.TextAlignmentRole:
            return int(Qt.AlignVCenter | (Qt.AlignLeft if s == 0 else Qt.AlignRight))
        return None

    def data(self, idx, role=Qt.DisplayRole):
        if idx.isValid() and role == Qt.UserRole:
            return self.rows[idx.row()]
        return None

    def set_rows(self, rows: list):
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()


class RowDelegate(QStyledItemDelegate):
    """Zeichnet jede Zeile als Karte mit Hover-/Auswahl-Hervorhebung, Last-Balken und Kategorie-Punkt."""

    def paint(self, p: QPainter, opt, idx):
        row = idx.data(Qt.UserRole)
        if not row:
            return
        col = idx.column()
        view = opt.widget
        full = QRectF(2, opt.rect.top() + 3, view.viewport().width() - 4, opt.rect.height() - 6)
        hover = bool(opt.state & QStyle.State_MouseOver)
        sel = bool(opt.state & QStyle.State_Selected)
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        p.setClipRect(opt.rect)
        if sel:
            g = QLinearGradient(full.left(), 0, full.right(), 0)
            g.setColorAt(0, QColor(PAL.nav_a))
            g.setColorAt(1, QColor(PAL.nav_b))
            p.setBrush(g)
            p.setPen(QPen(QColor(PAL.accent), 1))
        else:
            p.setBrush(QColor(PAL.card2) if hover else QColor(PAL.card))
            p.setPen(QPen(QColor(PAL.border_hi) if hover else QColor(PAL.border), 1))
        p.drawRoundedRect(full, 10, 10)
        cell = QRectF(opt.rect)
        f = QFont(opt.font)
        f.setPixelSize(13)
        if col == 0:
            c = QColor(CAT_COLORS.get(row["cat"], PAL.accent2))
            p.setPen(Qt.NoPen)
            p.setBrush(alpha(c, 70))
            p.drawEllipse(QPointF(cell.left() + 24, cell.center().y()), 7, 7)
            p.setBrush(c)
            p.drawEllipse(QPointF(cell.left() + 24, cell.center().y()), 3.5, 3.5)
            f.setWeight(QFont.DemiBold)
            p.setFont(f)
            p.setPen(QColor(PAL.text))
            name = row["name"]
            fm = p.fontMetrics()
            name = fm.elidedText(name, Qt.ElideRight, int(cell.width() - 110))
            p.drawText(QRectF(cell.left() + 42, cell.top(), cell.width() - 100, cell.height()), Qt.AlignVCenter | Qt.AlignLeft, name)
            if row["count"] > 1:
                tw = fm.horizontalAdvance(name)
                bx = cell.left() + 42 + tw + 10
                pill = QRectF(bx, cell.center().y() - 9, 34, 18)
                p.setPen(Qt.NoPen)
                p.setBrush(alpha(PAL.accent, 50))
                p.drawRoundedRect(pill, 9, 9)
                f2 = QFont(f)
                f2.setPixelSize(11)
                p.setFont(f2)
                p.setPen(QColor(PAL.accent2))
                p.drawText(pill, Qt.AlignCenter, f"×{row['count']}")
        elif col in (1, 2):
            val, vmax, color, text = (row["cpu"], 25.0, PAL.accent, f"{row['cpu']:.1f} %") if col == 1 else (row["ram"], 2000.0, CYAN, self.ram_text(row["ram"]))
            frac = max(0.0, min(1.0, val / vmax))
            bar_w = 90
            bx = cell.right() - 16 - bar_w
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(PAL.track))
            p.drawRoundedRect(QRectF(bx, cell.center().y() - 3, bar_w, 6), 3, 3)
            if frac > 0.01:
                c = lerp(color, RED, max(0.0, (frac - 0.6) / 0.4))
                p.setBrush(alpha(c, 70))
                p.drawRoundedRect(QRectF(bx - 1, cell.center().y() - 4, bar_w * frac + 2, 8), 4, 4)
                p.setBrush(c)
                p.drawRoundedRect(QRectF(bx, cell.center().y() - 3, bar_w * frac, 6), 3, 3)
            p.setFont(f)
            p.setPen(QColor(PAL.text) if frac > 0.02 else QColor(PAL.muted))
            p.drawText(QRectF(cell.left(), cell.top(), bx - cell.left() - 10, cell.height()), Qt.AlignVCenter | Qt.AlignRight, text)
        else:
            p.setFont(f)
            p.setPen(QColor(PAL.muted))
            text = str(row["threads"]) if col == 3 else (str(row["pids"][0]) if row["count"] == 1 else "–")
            p.drawText(QRectF(cell.left(), cell.top(), cell.width() - 16, cell.height()), Qt.AlignVCenter | Qt.AlignRight, text)
        p.restore()

    @staticmethod
    def ram_text(mb: float) -> str:
        return f"{mb / 1024:.1f} GB" if mb >= 1024 else f"{mb:.0f} MB"

    def sizeHint(self, opt, idx):
        s = super().sizeHint(opt, idx)
        s.setHeight(46)
        return s


class ProcessesPage(BasePage):
    def __init__(self, service: svc.Service):
        super().__init__()
        self.service = service
        self.all_rows: list = []
        self.sort, self.filter, self.grouped = "cpu", "Alle", True
        self.sys_cpu, self.sys_ram = 0.0, (0.0, 0)
        lay = page_layout(self, "Prozesse", "Was gerade Leistung frisst · Windows-Leerlauf wird nicht mitgezählt")
        tiles = QHBoxLayout()
        tiles.setSpacing(14)
        self.t = {k: StatTile(n, c) for k, n, c in (("count", "Programme", None), ("cpu", "CPU gesamt", "@accent2"), ("ram", "RAM belegt", PINK), ("top", "Größter Verbraucher", YELLOW))}
        for x in self.t.values():
            tiles.addWidget(x)
        lay.addLayout(tiles)
        bar = QHBoxLayout()
        bar.setSpacing(10)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Suchen …")
        self.search.setFixedWidth(200)
        self.search.textChanged.connect(self.apply)
        bar.addWidget(self.search)
        self.chips = Chips(["Alle", "Hohe Last", "Spiele", "Browser", "System"])
        self.chips.changed.connect(self._filter)
        bar.addWidget(self.chips)
        bar.addStretch(1)
        self.group_chips = Chips(["Gruppiert", "Einzeln"], "Gruppiert")
        self.group_chips.changed.connect(self._group)
        bar.addWidget(self.group_chips)
        self.sorts = Chips(["CPU", "RAM", "Name"], "CPU")
        self.sorts.changed.connect(self._sort)
        bar.addWidget(self.sorts)
        lay.addLayout(bar)
        self.model = ProcModel()
        self.view = QTableView()
        self.view.setModel(self.model)
        self.view.setItemDelegate(RowDelegate(self.view))
        self.view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.view.setShowGrid(False)
        self.view.setMouseTracking(True)
        self.view.viewport().setMouseTracking(True)
        self.view.setFrameShape(QTableView.NoFrame)
        self.view.verticalHeader().hide()
        self.view.verticalHeader().setDefaultSectionSize(46)
        self.view.verticalScrollBar().setSingleStep(34)
        hh = self.view.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        for c, w in ((1, 230), (2, 230), (3, 100), (4, 90)):
            hh.setSectionResizeMode(c, QHeaderView.Fixed)
            self.view.setColumnWidth(c, w)
        hh.setHighlightSections(False)
        lay.addWidget(self.view, 1)
        actions = QHBoxLayout()
        actions.setSpacing(10)
        kill = AnimButton("Beenden", "danger")
        kill.clicked.connect(self.kill)
        actions.addWidget(kill)
        for text, lvl in (("Priorität Hoch", "high"), ("Normal", "normal"), ("Niedrig", "low")):
            b = AnimButton(text, "ghost")
            b.clicked.connect(lambda _c=False, l=lvl: self.priority(l))
            actions.addWidget(b)
        actions.addStretch(1)
        self.count = label("", "dim")
        actions.addWidget(self.count)
        lay.addLayout(actions)

    def _filter(self, n):
        self.filter = n
        self.apply()

    def _sort(self, n):
        self.sort = n.lower()
        self.apply()

    def _group(self, n):
        self.grouped = n == "Gruppiert"
        self.apply()

    def on_sample(self, d: dict):
        self.sys_cpu = d["cpu"]
        self.sys_ram = (d["ram"], d["ram_used"], d["ram_total"])

    def build_rows(self, procs: list) -> list:
        if not self.grouped:
            return [{"name": n, "pids": [pid], "cpu": cpu, "ram": ram, "threads": th, "count": 1, "cat": categorize(n)} for n, pid, cpu, ram, th in procs]
        groups: dict[str, dict] = {}
        for n, pid, cpu, ram, th in procs:
            g = groups.setdefault(n.lower(), {"name": n, "pids": [], "cpu": 0.0, "ram": 0.0, "threads": 0, "count": 0, "cat": categorize(n)})
            g["pids"].append(pid)
            g["cpu"] += cpu
            g["ram"] += ram
            g["threads"] += th
            g["count"] += 1
        return list(groups.values())

    def on_procs(self, procs: list):
        self.all_rows = procs
        self.apply()

    def apply(self, *_):
        q = self.search.text().strip().lower()
        rows = self.build_rows(self.all_rows)
        total = len(rows)
        top = max(rows, key=lambda r: r["cpu"], default=None)
        out = []
        for r in rows:
            if q and q not in r["name"].lower():
                continue
            if self.filter == "Hohe Last" and not (r["cpu"] >= 2.0 or r["ram"] >= 500):
                continue
            if self.filter == "Spiele" and r["cat"] != "game":
                continue
            if self.filter == "Browser" and r["cat"] != "browser":
                continue
            if self.filter == "System" and r["cat"] != "system":
                continue
            out.append(r)
        key = {"cpu": lambda r: -r["cpu"], "ram": lambda r: -r["ram"], "name": lambda r: r["name"].lower()}[self.sort]
        out.sort(key=key)
        sel = self.selected()
        sb = self.view.verticalScrollBar()
        pos = sb.value()
        self.model.set_rows(out[:250])
        sb.setValue(pos)
        if sel:
            for i, r in enumerate(self.model.rows):
                if r["name"] == sel["name"] and (not r["count"] > 1) == (not sel["count"] > 1):
                    self.view.selectRow(i)
                    break
        self.count.setText(f"{min(len(out), 250)} von {total} angezeigt")
        self.t["count"].set(str(total), "laufende Programme" if self.grouped else "laufende Prozesse")
        self.t["cpu"].set(f"{self.sys_cpu:.0f}%", "Gesamtauslastung")
        ram = getattr(self, "sys_ram", (0, 0, 0))
        self.t["ram"].set(f"{ram[0]:.0f}%", f"{svc.fmt_bytes(ram[1])} von {svc.fmt_bytes(ram[2])}" if ram[2] else "")
        if top:
            self.t["top"].set(top["name"][:16], f"{top['cpu']:.1f}% CPU · {top['ram']:.0f} MB")

    def selected(self):
        sm = self.view.selectionModel()
        sel = sm.selectedRows() if sm else []
        return self.model.rows[sel[0].row()] if sel else None

    def kill(self):
        row = self.selected()
        if not row:
            return
        if row["name"].lower() in PROTECTED or any(pid <= 4 for pid in row["pids"]):
            QMessageBox.warning(self, "SquallowTweaks", "Dieser Windows-Systemprozess ist geschützt.")
            return
        n = row["count"]
        if QMessageBox.question(self, "Beenden?", f"'{row['name']}' ({n} Prozess{'e' if n > 1 else ''}) wirklich beenden?\nUngespeicherte Daten gehen verloren.") != QMessageBox.Yes:
            return
        for pid in row["pids"]:
            try:
                psutil.Process(pid).terminate()
            except Exception:  # noqa: BLE001
                pass

    def priority(self, level: str):
        row = self.selected()
        cls = {"high": getattr(psutil, "HIGH_PRIORITY_CLASS", None), "normal": getattr(psutil, "NORMAL_PRIORITY_CLASS", None),
               "low": getattr(psutil, "IDLE_PRIORITY_CLASS", None)}[level]
        if not row or cls is None:
            return
        failed = 0
        for pid in row["pids"]:
            try:
                psutil.Process(pid).nice(cls)
            except Exception:  # noqa: BLE001
                failed += 1
        if failed:
            QMessageBox.warning(self, "SquallowTweaks", f"Für {failed} Prozess(e) nicht änderbar (geschützt oder beendet).")


# ===========================================================================
# Netzwerk
# ===========================================================================
class NetworkPage(BasePage):
    TARGETS = {"Cloudflare": "1.1.1.1", "Google": "8.8.8.8", "Gateway": ""}

    def __init__(self, service: svc.Service):
        super().__init__()
        from pages_a import TweaksList
        self.service = service
        self.monitor = None
        self._zombies: list = []
        self.samples: list = []
        self.gateway = ""
        lay = page_layout(self, "Netzwerk", "Ping-Stabilität live beobachten und verbessern")
        card = Card()
        v = QVBoxLayout(card)
        v.setContentsMargins(18, 14, 18, 14)
        top = QHBoxLayout()
        top.addWidget(label("Ping-Monitor", "h2"))
        top.addStretch(1)
        self.target = Chips(list(self.TARGETS), "Cloudflare")
        self.target.changed.connect(self._restart)
        top.addWidget(self.target)
        self.toggle_btn = AnimButton("Stopp", "ghost")
        self.toggle_btn.clicked.connect(self.toggle)
        top.addWidget(self.toggle_btn)
        v.addLayout(top)
        self.chart = LineChart(None, " ms", 120, show_legend=False)
        self.chart.add_series("Ping", CYAN)
        self.chart.setMinimumHeight(190)
        v.addWidget(self.chart, 1)
        lay.addWidget(card, 1)
        tiles = QHBoxLayout()
        tiles.setSpacing(14)
        self.t = {k: StatTile(n, c) for k, n, c in (("avg", "Ø Ping", None), ("jit", "Jitter", CYAN), ("loss", "Verlust", YELLOW), ("max", "Maximum", PINK))}
        for x in self.t.values():
            tiles.addWidget(x)
        lay.addLayout(tiles)
        lay.addWidget(label("Ping-Stabilisierung", "h2"))
        lay.addWidget(TweaksList(service, [t for t in service.catalog if "PING" in t.tags], with_filters=False))
        self.conn = label("", "muted", True)
        lay.addWidget(self.conn)
        QTimer.singleShot(300, self.detect)

    def detect(self):
        def work():
            return netlab.get_network_config(), netlab.psutil_adapters()

        def done(r):
            if isinstance(r, Exception):
                return
            cfg, ad = r
            for c in cfg:
                if c["gateway"]:
                    self.gateway = c["gateway"][0]
                    break
            lan = [a for a in ad if a["kind"] == "LAN" and a["is_up"]]
            wifi = [a for a in ad if a["kind"] == "WLAN" and a["is_up"]]
            if lan:
                self.conn.setText("LAN verbunden · " + ", ".join(f"{a['name']} ({a['speed_mbit']} Mbit/s)" if a["speed_mbit"] else a["name"] for a in lan))
            elif wifi:
                self.conn.setText("Du nutzt WLAN. Ein LAN-Kabel ist die größte Einzelverbesserung für einen stabilen Ping.")
            else:
                self.conn.setText("Kein aktiver Netzwerkadapter erkannt.")
        svc.run_async(work, done)

    def host(self) -> str:
        t = self.target.current
        return self.gateway if t == "Gateway" else self.TARGETS[t]

    def toggle(self):
        self.stop() if self.monitor else self.start()

    def _restart(self, _n=""):
        if self.monitor:
            self.stop()
            self.start()

    def start(self):
        h = self.host()
        if not h:
            self.conn.setText("Kein Gateway erkannt. Wähle ein anderes Ziel.")
            return
        self.samples.clear()
        self.chart.clear()
        self.monitor = svc.PingMonitor(h)
        self.monitor.result.connect(self.on_ping)
        self.monitor.start()
        self.toggle_btn.setText("Stopp")

    def stop(self):
        m = self.monitor
        if m:
            m.stop()
            try:
                m.result.disconnect(self.on_ping)
            except (RuntimeError, TypeError):
                pass
            self._zombies.append(m)
            m.finished.connect(lambda mm=m: self._zombies.remove(mm) if mm in self._zombies else None)
            self.monitor = None
        self.toggle_btn.setText("Start")

    def shutdown(self):
        self.stop()
        for m in list(self._zombies):
            m.wait(4000)

    def on_ping(self, v):
        self.samples = (self.samples + [v])[-300:]
        self.chart.push("Ping", v)
        self.chart.update()
        ok = [x for x in self.samples if x is not None]
        if ok:
            self.t["avg"].set(f"{sum(ok) / len(ok):.0f} ms", "")
            self.t["max"].set(f"{max(ok):.0f} ms", "")
            self.t["jit"].set(f"{netlab.calc_jitter(ok) or 0:.1f} ms", "mittlere Schwankung")
        lost = len(self.samples) - len(ok)
        self.t["loss"].set(f"{100 * lost / len(self.samples):.0f}%", f"{lost} von {len(self.samples)}")


# ===========================================================================
# Bereinigung (+ Autostart)
# ===========================================================================
class CleanRow(Card):
    def __init__(self, cat: cleaner.Category, locked: bool):
        super().__init__()
        self.cat = cat
        self.size = 0
        self.setFixedHeight(64)
        h = QHBoxLayout(self)
        h.setContentsMargins(16, 8, 16, 8)
        h.setSpacing(12)
        col = QVBoxLayout()
        col.setSpacing(2)
        t = label(cat.name + ("   🔒 Admin" if cat.admin and locked else ""), "h2")
        d = label(cat.desc, "muted")
        for w in (t, d):
            w.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        col.addWidget(t)
        col.addWidget(d)
        h.addLayout(col, 1)
        self.size_label = label("…", "h2")
        self.size_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        h.addWidget(self.size_label)
        self.toggle = Toggle()
        self.toggle.set_checked_silent(not locked)
        self.toggle.setEnabled(not locked)
        h.addWidget(self.toggle)

    def set_size(self, n: int):
        self.size = n
        self.size_label.setText(svc.fmt_bytes(n) if n else "leer")
        self.size_label.setStyleSheet(f"color:{PAL.accent2 if n else PAL.dim};")


class CleanPage(BasePage):
    def __init__(self, service: svc.Service):
        super().__init__()
        self.service = service
        self.rows: list[CleanRow] = []
        lay = page_layout(self, "Bereinigung", "Löscht nur Cache- und Temp-Inhalte. Persönliche Dateien bleiben unberührt.")
        hero = Card("hero")
        h = QHBoxLayout(hero)
        h.setContentsMargins(22, 18, 22, 18)
        col = QVBoxLayout()
        self.total = label("Wird gemessen …", "big")
        self.total.setStyleSheet("font-size:30px;font-weight:800;")
        col.addWidget(self.total)
        self.msg = label("Wähle aus, was weg soll, und klicke auf Bereinigen.", "muted", True)
        col.addWidget(self.msg)
        h.addLayout(col, 1)
        rescan = AnimButton("Neu messen", "ghost")
        rescan.clicked.connect(self.scan)
        h.addWidget(rescan)
        self.btn = AnimButton("Bereinigen", "accent")
        self.btn.clicked.connect(self.clean)
        h.addWidget(self.btn)
        lay.addWidget(hero)
        for cat in cleaner.categories():
            r = CleanRow(cat, cat.admin and not service.admin)
            self.rows.append(r)
            r.toggle.clicked.connect(self._update_total)
            lay.addWidget(r)
        lay.addWidget(label("Autostart", "h2"))
        lay.addWidget(label("Programme, die mit Windows starten. Ausschalten löscht nichts, du kannst es jederzeit wieder einschalten.", "muted", True))
        self.start_box = QVBoxLayout()
        self.start_box.setSpacing(8)
        lay.addLayout(self.start_box)
        lay.addStretch(1)
        QTimer.singleShot(200, self.scan)
        QTimer.singleShot(250, self.load_startup)

    def scan(self):
        self.total.setText("Wird gemessen …")
        self._pending = len(self.rows)
        for r in self.rows:
            r.size_label.setText("…")

            def work(c=r.cat):
                return cleaner.scan(c)

            def done(res, row=r):
                row.set_size(res if isinstance(res, int) else 0)
                self._update_total()
            svc.run_async(work, done)

    def _update_total(self, *_):
        n = sum(r.size for r in self.rows if r.toggle.isChecked())
        self.total.setText(f"{svc.fmt_bytes(n)} bereinigbar")

    def clean(self):
        todo = [r for r in self.rows if r.toggle.isChecked() and r.toggle.isEnabled()]
        if not todo:
            return
        self.btn.setEnabled(False)
        self.msg.setText("Bereinige …")

        def work():
            freed = errors = 0
            for r in todo:
                f, e = cleaner.clean(r.cat)
                freed += f
                errors += e
            ok, _ = netlab.flush_dns()
            return freed, errors

        def done(res):
            self.btn.setEnabled(True)
            if isinstance(res, Exception):
                self.msg.setText(f"Fehler: {res}")
                return
            freed, errors = res
            self.msg.setText(f"{svc.fmt_bytes(freed)} freigegeben" + (f" · {errors} Dateien waren gesperrt und wurden übersprungen" if errors else "") + " · DNS-Cache geleert")
            self.scan()
        svc.run_async(work, done)

    def load_startup(self):
        while self.start_box.count():
            w = self.start_box.takeAt(0).widget()
            if w:
                w.deleteLater()
        entries = eng.list_startup(self.service.engine.backend)
        if not entries:
            self.start_box.addWidget(label("Keine Autostart-Einträge im Benutzerprofil gefunden.", "muted"))
            return
        for e in entries:
            row = Card()
            row.setFixedHeight(58)
            h = QHBoxLayout(row)
            h.setContentsMargins(16, 8, 16, 8)
            col = QVBoxLayout()
            col.setSpacing(0)
            n = label(e.name, "h2")
            c = label(e.command[:90], "dim")
            for w in (n, c):
                w.setAttribute(Qt.WA_TransparentForMouseEvents, True)
                col.addWidget(w)
            h.addLayout(col, 1)
            tg = Toggle()
            tg.set_checked_silent(e.enabled)
            tg.clicked.connect(lambda checked, name=e.name: eng.set_startup_enabled(self.service.engine.backend, name, bool(checked)))
            h.addWidget(tg)
            self.start_box.addWidget(row)


# ===========================================================================
class SettingsPage(BasePage):
    def __init__(self, service: svc.Service):
        super().__init__()
        self.service = service
        lay = page_layout(self, "Einstellungen", "Design, Zurücksetzen und Infos")

        def card(title: str, text: str, buttons: list) -> Card:
            c = Card()
            row = QHBoxLayout(c)
            row.setContentsMargins(20, 16, 20, 16)
            col = QVBoxLayout()
            col.addWidget(label(title, "h2"))
            col.addWidget(label(text, "muted", True))
            row.addLayout(col, 1)
            for name, variant, fn in buttons:
                b = AnimButton(name, variant)
                b.clicked.connect(fn)
                row.addWidget(b)
            return c

        self.status = label("", "muted")
        lay.addWidget(self._design_card())
        lay.addWidget(card("Alles zurücksetzen", "Stellt alle von SquallowTweaks gesetzten Einstellungen auf den gesicherten Originalzustand zurück.", [("Zurücksetzen", "danger", self.undo_all)]))
        lay.addWidget(card("Daten & Log", f"Backups, Messungen und Protokoll liegen in {svc.APP_DIR}.", [("Ordner öffnen", "ghost", self.open_dir)]))
        lay.addWidget(card("Rechte", "Administrator: aktiv. Alle Tweaks sind verfügbar." if service.admin else
                           "Ohne Administratorrechte sind Tweaks mit ADMIN-Label gesperrt. Starte SquallowTweaks per Rechtsklick als Administrator.", []))
        lay.addWidget(self.status)
        lay.addStretch(1)
        lay.addWidget(label("SquallowTweaks 1.1 · Änderungen sind lokal und umkehrbar. Es wird nichts an Defender, Firewall oder Anti-Cheat verändert.", "dim", True))

    # ---- Design
    def _design_card(self) -> Card:
        c = Card()
        c.hover_on = False
        v = QVBoxLayout(c)
        v.setContentsMargins(20, 16, 20, 16)
        v.setSpacing(10)
        v.addWidget(label("Design & Themes", "h2"))
        v.addWidget(label("Jedes Theme hat eigene Farben und einen eigenen Hintergrund-Effekt. Deine Auswahl bleibt nach einem Neustart erhalten.", "muted", True))
        grid = QGridLayout()
        grid.setSpacing(10)
        self.swatches = {}
        for i, key in enumerate(themes.ORDER):
            sw = ThemeSwatch(key)
            sw.clicked.connect(lambda _c=False, k=key: self.pick_theme(k))
            grid.addWidget(sw, i // 6, i % 6)
            self.swatches[key] = sw
        grid.setColumnStretch(6, 1)
        v.addLayout(grid)
        row = QHBoxLayout()
        row.setSpacing(10)
        pick = AnimButton("Eigene Farbe wählen …", "ghost")
        pick.clicked.connect(self.pick_custom)
        row.addWidget(pick)
        row.addStretch(1)
        row.addWidget(label("Hintergrund-Effekte", "muted"))
        self.fx_toggle = Toggle()
        self.fx_toggle.set_checked_silent(effects_on())
        self.fx_toggle.clicked.connect(lambda checked: set_effects(bool(checked)))
        row.addWidget(self.fx_toggle)
        v.addLayout(row)
        self._sync_swatches()
        return c

    def _sync_swatches(self):
        cur = store()["theme"]
        for k, sw in self.swatches.items():
            sw.setChecked(k == cur)
            sw.update()

    def pick_theme(self, key: str):
        apply_theme(key)
        self._sync_swatches()

    def pick_custom(self):
        col = QColorDialog.getColor(QColor(store()["custom_accent"]), self, "Eigene Akzentfarbe wählen")
        if col.isValid():
            apply_theme("custom", col.name())
            self._sync_swatches()

    def undo_all(self):
        if QMessageBox.question(self, "SquallowTweaks", "Alle Tweaks auf den Originalzustand zurücksetzen?") != QMessageBox.Yes:
            return
        self.status.setText("Setze zurück …")
        self.service.undo_all(lambda r: self.status.setText(f"Zurückgesetzt: {r[0]} · Fehler: {r[1]}" if not isinstance(r, Exception) else str(r)))

    def open_dir(self):
        svc.APP_DIR.mkdir(parents=True, exist_ok=True)
        if svc.IS_WINDOWS:
            os.startfile(str(svc.APP_DIR))  # noqa: S606
        else:
            webbrowser.open(svc.APP_DIR.as_uri())
