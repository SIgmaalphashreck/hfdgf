"""SquallowTweaks - Hardware-Infos fuer das Dashboard (nur lesen, Qt-frei).

Grundsatz: Nichts erfinden. Jeder Wert ist entweder aus einer echten Quelle gelesen oder None
(die UI zeigt dann "Nicht verfuegbar").

Quellen
  CPU-/GPU-Name   Windows-Registry (sofort, ohne Prozessstart); Linux: /proc/cpuinfo (nur Entwicklung)
  GPU-Last/-Temp  nvidia-smi (bereits im Sampler); sonst LibreHardwareMonitor/OpenHardwareMonitor, falls dessen
                  WMI-Schnittstelle laeuft
  CPU-Temp        1. LibreHardwareMonitor/OpenHardwareMonitor (echter CPU-Sensor)
                  2. ACPI-Thermalzone (Firmware-Sensor; kann vom Kern abweichen -> wird als "ACPI" gekennzeichnet)
                  3. Linux: psutil.sensors_temperatures (nur Entwicklung)
Die Temperaturabfrage laeuft in einem eigenen Thread, selten und mit Backoff, und blockiert nie die Oberflaeche.
"""
from __future__ import annotations

import json
import os
import re
import threading
from typing import Callable, Optional

IS_WINDOWS = os.name == "nt"
GPU_CLASS = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
CPU_KEY = r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
TEMP_MIN, TEMP_MAX = 1.0, 125.0      # alles ausserhalb gilt als Sensorfehler und wird verworfen

PS_SCRIPT = r"""
$ErrorActionPreference='SilentlyContinue'
$o=@{}
foreach($ns in 'root\LibreHardwareMonitor','root\OpenHardwareMonitor'){
  $s=Get-CimInstance -Namespace $ns -ClassName Sensor -Filter "SensorType='Temperature'"
  if($s){ $o.hw=@($s | ForEach-Object { @{n=[string]$_.Name; i=[string]$_.Identifier; v=[double]$_.Value} }); $o.src=$ns.Split('\')[1]; break }
}
$z=Get-CimInstance -Namespace root\wmi -ClassName MSAcpi_ThermalZoneTemperature
if($z){ $o.acpi=@($z | ForEach-Object { @{n=[string]$_.InstanceName; v=([double]$_.CurrentTemperature/10.0)-273.15} }) }
$o | ConvertTo-Json -Compress -Depth 5
"""


def clean_name(s: Optional[str]) -> Optional[str]:
    """Mehrfach-Leerzeichen entfernen; Modellbezeichnung sonst unveraendert (exakt wie vom System gemeldet)."""
    if not s:
        return None
    s = re.sub(r"\s+", " ", str(s).replace("\x00", " ")).strip()
    return s or None


def _ok_temp(v) -> Optional[float]:
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v if TEMP_MIN <= v <= TEMP_MAX else None


# ---------------------------------------------------------------------------
# Namen / statische Infos
# ---------------------------------------------------------------------------
def _winreg_read(path: str, name: str):
    import winreg  # noqa: PLC0415
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_READ) as key:
        return winreg.QueryValueEx(key, name)[0]


def _winreg_subkeys(path: str) -> list[str]:
    import winreg  # noqa: PLC0415
    out = []
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_READ) as key:
            i = 0
            while True:
                try:
                    out.append(winreg.EnumKey(key, i))
                except OSError:
                    break
                i += 1
    except OSError:
        pass
    return out


def cpu_name(read: Callable[[str, str], object] = None) -> Optional[str]:
    if IS_WINDOWS or read is not None:
        try:
            return clean_name((read or _winreg_read)(CPU_KEY, "ProcessorNameString"))
        except Exception:  # noqa: BLE001
            return None
    try:
        with open("/proc/cpuinfo", encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.lower().startswith("model name"):
                    return clean_name(line.split(":", 1)[1])
    except OSError:
        pass
    return None


_BAD_GPU = ("microsoft basic", "remote", "virtual", "parsec", "indirect", "displaylink", "meta ", "mirage")


def _gpu_rank(desc: str) -> int:
    d = desc.lower()
    if any(b in d for b in _BAD_GPU):
        return -1
    if any(k in d for k in ("geforce", "rtx", "gtx", "quadro", "nvidia")):
        return 4
    if "radeon rx" in d or "radeon pro" in d or ("amd radeon" in d and "graphics" not in d):
        return 4
    if "arc" in d and "intel" in d:
        return 3
    if "radeon" in d or "amd" in d:
        return 2
    if "intel" in d:
        return 1
    return 1


def gpu_adapters(read: Callable[[str, str], object] = None, subkeys: Callable[[str], list] = None) -> list[dict]:
    """Alle echten Grafikadapter aus der Registry, beste (dedizierte) zuerst."""
    if not IS_WINDOWS and read is None:
        return []
    read = read or _winreg_read
    subkeys = subkeys or _winreg_subkeys
    found = []
    for sk in subkeys(GPU_CLASS):
        if not (len(sk) == 4 and sk.isdigit()):
            continue
        path = GPU_CLASS + "\\" + sk
        try:
            desc = clean_name(read(path, "DriverDesc"))
        except Exception:  # noqa: BLE001
            continue
        if not desc or _gpu_rank(desc) < 0:
            continue
        vram = None
        try:
            raw = read(path, "HardwareInformation.qwMemorySize")
            if isinstance(raw, (bytes, bytearray)):
                raw = int.from_bytes(raw[:8], "little")
            vram = int(raw) if raw and int(raw) > 0 else None
        except Exception:  # noqa: BLE001
            vram = None
        try:
            driver = clean_name(read(path, "DriverVersion"))
        except Exception:  # noqa: BLE001
            driver = None
        found.append({"name": desc, "vram": vram, "driver": driver, "rank": _gpu_rank(desc)})
    found.sort(key=lambda a: (-a["rank"], -(a["vram"] or 0)))
    return found


# ---------------------------------------------------------------------------
# Temperaturen
# ---------------------------------------------------------------------------
_CPU_PREF = ("cpu package", "core (tctl/tdie)", "tctl/tdie", "cpu total", "core average", "cpu (tctl/tdie)", "cpu die")


def parse_temps(text: str) -> dict:
    """PowerShell-JSON -> {"cpu": (grad, quelle)|None, "gpu": (grad, quelle)|None}. Unbrauchbare Werte werden verworfen."""
    res = {"cpu": None, "gpu": None}
    try:
        data = json.loads(text)
    except Exception:  # noqa: BLE001
        return res
    if not isinstance(data, dict):
        return res

    def as_list(x):
        return x if isinstance(x, list) else ([x] if isinstance(x, dict) else [])

    src = str(data.get("src") or "LibreHardwareMonitor")
    cpu, gpu = [], []
    for s in as_list(data.get("hw")):
        ident = str(s.get("i", "")).lower()
        v = _ok_temp(s.get("v"))
        if v is None:
            continue
        item = (str(s.get("n", "")).lower(), v)
        if "/gpu" in ident:
            gpu.append(item)
        elif "cpu" in ident:
            cpu.append(item)
    if cpu:
        pick = next((v for pref in _CPU_PREF for n, v in cpu if n == pref), None)
        res["cpu"] = (pick if pick is not None else max(v for _n, v in cpu), src)
    if gpu:
        pick = next((v for n, v in gpu if "core" in n or n == "gpu"), None)
        res["gpu"] = (pick if pick is not None else max(v for _n, v in gpu), src)
    if res["cpu"] is None:
        zones = [v for v in (_ok_temp(z.get("v")) for z in as_list(data.get("acpi"))) if v is not None]
        if zones:
            res["cpu"] = (round(max(zones), 1), "ACPI")
    return res


def read_temps_windows(runner: Callable[[list, int], tuple]) -> dict:
    code, out = runner(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", PS_SCRIPT], 15)
    if code != 0 or not out:
        return {"cpu": None, "gpu": None}
    # PowerShell kann Warnungen vor das JSON schreiben -> ab der ersten Klammer lesen
    i = out.find("{")
    return parse_temps(out[i:] if i >= 0 else out)


def read_temps_linux() -> dict:
    res = {"cpu": None, "gpu": None}
    try:
        import psutil  # noqa: PLC0415
        t = psutil.sensors_temperatures() if hasattr(psutil, "sensors_temperatures") else {}
        for key in ("coretemp", "k10temp", "zenpower", "cpu_thermal"):
            for e in t.get(key, []):
                v = _ok_temp(e.current)
                if v is not None:
                    res["cpu"] = (v, "psutil")
                    return res
    except Exception:  # noqa: BLE001
        pass
    return res


class HwMonitor:
    """Haelt die zuletzt gelesenen Hardwarewerte. Namen werden sofort gelesen, Temperaturen im Hintergrund."""

    FAST, SLOW = 6.0, 60.0           # Abfrageintervall mit/ohne bisherigen Erfolg (Sekunden)

    def __init__(self, runner: Optional[Callable] = None, cpu_reader=None, gpu_reader=None, gpu_subkeys=None, sleeper=None):
        self.runner = runner
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._sleep = sleeper or self._stop.wait
        self.cpu = cpu_name(cpu_reader)
        adapters = gpu_adapters(gpu_reader, gpu_subkeys) if (IS_WINDOWS or gpu_reader) else []
        self.adapters = adapters
        self.gpu = adapters[0] if adapters else None
        self._temps = {"cpu": None, "gpu": None}
        self._misses = 0

    # ---- Abfrage
    def poll_once(self) -> dict:
        if IS_WINDOWS and self.runner:
            t = read_temps_windows(self.runner)
        elif not IS_WINDOWS:
            t = read_temps_linux()
        else:
            t = {"cpu": None, "gpu": None}
        with self._lock:
            self._temps = t
        self._misses = 0 if (t["cpu"] or t["gpu"]) else self._misses + 1
        return t

    def _loop(self):
        while not self._stop.is_set():
            try:
                self.poll_once()
            except Exception:  # noqa: BLE001
                self._misses += 1
            # Nach 3 erfolglosen Versuchen nur noch selten pruefen (z. B. wenn LibreHardwareMonitor spaeter gestartet wird)
            if self._sleep(self.SLOW if self._misses >= 3 else self.FAST):
                break

    def start(self):
        if self._thread is None:
            self._thread = threading.Thread(target=self._loop, daemon=True, name="hwmon")
            self._thread.start()

    def stop(self):
        self._stop.set()

    def snapshot(self) -> dict:
        with self._lock:
            t = dict(self._temps)
        cpu_t, gpu_t = t.get("cpu"), t.get("gpu")
        return {"cpu_name": self.cpu,
                "gpu_name": self.gpu["name"] if self.gpu else None,
                "gpu_driver": self.gpu["driver"] if self.gpu else None,
                "gpu_vram": self.gpu["vram"] if self.gpu else None,
                "cpu_temp": cpu_t[0] if cpu_t else None, "cpu_temp_src": cpu_t[1] if cpu_t else None,
                "gpu_temp": gpu_t[0] if gpu_t else None, "gpu_temp_src": gpu_t[1] if gpu_t else None}
