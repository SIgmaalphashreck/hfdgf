"""SquallowTweaks - Bereinigung: bekannte Cache-/Temp-Ordner messen und leeren (nur Inhalt, nie den Ordner selbst)."""
from __future__ import annotations

import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

IS_WINDOWS = os.name == "nt"


def _env(name: str, default: str = "") -> Path:
    return Path(os.environ.get(name, default)) if os.environ.get(name, default) else Path()


@dataclass
class Category:
    id: str
    name: str
    desc: str
    paths: Callable[[], list]
    admin: bool = False
    special: str = ""        # "recycle" = Papierkorb ueber die Windows-API


def categories() -> list[Category]:
    local = _env("LOCALAPPDATA")
    win = _env("WINDIR", r"C:\Windows")
    temp = _env("TEMP", str(Path.home() / "AppData/Local/Temp"))
    return [
        Category("temp_user", "Temporäre Benutzerdateien", "Programm-Reste in deinem Temp-Ordner.", lambda: [temp]),
        Category("temp_win", "Windows-Temp", "Temporäre Systemdateien.", lambda: [win / "Temp"], admin=True),
        Category("wu_cache", "Windows-Update-Cache", "Bereits installierte Update-Downloads.", lambda: [win / "SoftwareDistribution" / "Download"], admin=True),
        Category("thumbs", "Vorschaubilder-Cache", "Wird automatisch neu erstellt.", lambda: sorted((local / "Microsoft" / "Windows" / "Explorer").glob("thumbcache_*.db")) if local.name else []),
        Category("crash", "Absturzberichte", "Crash-Dumps und Fehlerberichte.", lambda: [local / "CrashDumps", win / "Minidump", local / "Microsoft" / "Windows" / "WER"], admin=False),
        Category("browser", "Browser-Cache (Chrome, Edge)", "Zwischengespeicherte Webseiten. Logins bleiben erhalten.",
                 lambda: [local / "Google" / "Chrome" / "User Data" / "Default" / "Cache" / "Cache_Data",
                          local / "Google" / "Chrome" / "User Data" / "Default" / "Code Cache",
                          local / "Microsoft" / "Edge" / "User Data" / "Default" / "Cache" / "Cache_Data",
                          local / "Microsoft" / "Edge" / "User Data" / "Default" / "Code Cache"]),
        Category("epic_web", "Epic-Launcher-Cache", "Web-Cache des Epic Games Launchers.", lambda: sorted((local / "EpicGamesLauncher" / "Saved").glob("webcache*")) if local.name else []),
        Category("fn_logs", "Fortnite-Logs", "Alte Logs und Crash-Ordner von Fortnite.", lambda: [local / "FortniteGame" / "Saved" / "Logs", local / "FortniteGame" / "Saved" / "Crashes"]),
        Category("recycle", "Papierkorb", "Endgültig leeren.", lambda: [], special="recycle"),
    ]


def path_size(p: Path, deadline: float) -> int:
    total = 0
    try:
        if p.is_symlink():
            return 0
        if p.is_file():
            return p.stat().st_size
        if not p.is_dir():
            return 0
        stack = [p]
        while stack and time.time() < deadline:
            d = stack.pop()
            try:
                with os.scandir(d) as it:
                    for e in it:
                        try:
                            if e.is_symlink():
                                continue
                            if e.is_dir(follow_symlinks=False):
                                stack.append(Path(e.path))
                            else:
                                total += e.stat(follow_symlinks=False).st_size
                        except OSError:
                            continue
            except OSError:
                continue
    except OSError:
        pass
    return total


def recycle_size() -> int:
    if not IS_WINDOWS:
        return 0
    try:
        import ctypes
        from ctypes import wintypes

        class SHQUERYRBINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("i64Size", ctypes.c_longlong), ("i64NumItems", ctypes.c_longlong)]
        info = SHQUERYRBINFO()
        info.cbSize = ctypes.sizeof(info)
        if ctypes.windll.shell32.SHQueryRecycleBinW(None, ctypes.byref(info)) == 0:
            return int(info.i64Size)
    except Exception:  # noqa: BLE001
        pass
    return 0


def scan(cat: Category, limit_s: float = 8.0) -> int:
    if cat.special == "recycle":
        return recycle_size()
    deadline = time.time() + limit_s
    return sum(path_size(p, deadline) for p in cat.paths())


def _empty_dir(d: Path) -> tuple[int, int]:
    """Loescht den Inhalt von d. Gibt (befreite Bytes, Fehler) zurueck."""
    freed = errors = 0
    try:
        children = list(d.iterdir())
    except OSError:
        return 0, 0
    for c in children:
        try:
            if c.is_symlink():
                c.unlink()
                continue
            size = path_size(c, time.time() + 5)
            if c.is_dir():
                shutil.rmtree(c)
            else:
                c.unlink()
            freed += size
        except OSError:
            errors += 1
    return freed, errors


def clean(cat: Category) -> tuple[int, int]:
    if cat.special == "recycle":
        before = recycle_size()
        if IS_WINDOWS:
            try:
                import ctypes
                ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 0x7)   # ohne Rueckfrage, Fortschritt, Sound
            except Exception:  # noqa: BLE001
                return 0, 1
        return before, 0
    freed = errors = 0
    for p in cat.paths():
        if not p or not p.exists():
            continue
        if p.is_file():
            try:
                s = p.stat().st_size
                p.unlink()
                freed += s
            except OSError:
                errors += 1
        else:
            f, e = _empty_dir(p)
            freed += f
            errors += e
    return freed, errors
