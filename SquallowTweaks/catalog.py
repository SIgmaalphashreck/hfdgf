"""SquallowTweaks - Tweak-Katalog (kurz und lesbar).

Pro Tweak: Name, EIN kurzer Satz, Tags (FPS / LATENZ / PING / FRAMETIME) und
ein Detailtext, der nur im Tooltip erscheint.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from engine import (REG_DWORD, REG_SZ, STATUS_ACTIVE, STATUS_UNKNOWN, TOGGLE_KINDS, RegValue, Tweak, TweakEngine,
                    FORT_SECTION)

CATEGORIES = ["Gaming", "Fortnite", "Latenz", "Netzwerk", "System"]
G, F, L, N, S = CATEGORIES

HKLM_MM = r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile"


def _dw(path, name, value):
    return RegValue(path, name, REG_DWORD, value)


def _sz(path, name, value):
    return RegValue(path, name, REG_SZ, value)


def msi_gpu_values(backend) -> list:
    """MSI-Modus fuer alle Grafikkarten (PCI-Klasse 'Display'), zur Laufzeit ermittelt."""
    base = r"HKLM\SYSTEM\CurrentControlSet\Enum\PCI"
    out = []
    for dev in backend.subkeys(base):
        for inst in backend.subkeys(base + "\\" + dev):
            path = base + "\\" + dev + "\\" + inst
            ok, _, cls = backend.read(path, "Class")
            if ok and str(cls).lower() == "display":
                out.append(RegValue(path + r"\Device Parameters\Interrupt Management\MessageSignaledInterruptProperties",
                                    "MSISupported", REG_DWORD, 1))
    return out


def fortnite_exe_path() -> Optional[str]:
    """Installationspfad von Fortnite laut Epic-Launcher (LauncherInstalled.dat)."""
    base = os.environ.get("ProgramData", r"C:\ProgramData")
    f = Path(base) / "Epic" / "UnrealEngineLauncher" / "LauncherInstalled.dat"
    try:
        data = json.loads(f.read_text(encoding="utf-8", errors="replace"))
        for item in data.get("InstallationList", []):
            if item.get("AppName") == "Fortnite" and item.get("InstallLocation"):
                exe = Path(item["InstallLocation"]) / "FortniteGame" / "Binaries" / "Win64" / "FortniteClient-Win64-Shipping.exe"
                return str(exe)
    except Exception:  # noqa: BLE001
        pass
    return None


def fortnite_gpu_pref_values(_backend) -> list:
    exe = fortnite_exe_path()
    if not exe:
        return []
    return [RegValue(r"Software\Microsoft\DirectX\UserGpuPreferences", exe, REG_SZ, "GpuPreference=2;")]


def fortnite_exe_flag_values(_backend) -> list:
    exe = fortnite_exe_path()
    if not exe:
        return []
    return [RegValue(r"Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers", exe, REG_SZ,
                     "~ DISABLEDXMAXIMIZEDWINDOWEDMODE")]


_FG = FORT_SECTION
_GFX = {}
for _k in ("ShadowQuality", "PostProcessQuality", "EffectsQuality", "FoliageQuality", "ShadingQuality",
           "GlobalIlluminationQuality", "ReflectionQuality"):
    _GFX[f"{_FG}|sg.{_k}"] = "0"
    _GFX[f"ScalabilityGroups|sg.{_k}"] = "0"

LAN_PROPS = {"*EEE": "0", "EEELinkAdvertisement": "0", "AdvancedEEE": "0", "GreenEthernet": "0", "EnableGreenEthernet": "0",
             "PowerSavingMode": "0", "ULPMode": "0", "GigaLite": "0", "*FlowControl": "0"}


def build_catalog() -> list[Tweak]:
    T = Tweak
    return [
        # ------------------------------------------------------------------ FPS / Frametime
        T("power_ultimate", "Ultimative Leistung", [G, L], "Stärkster Windows-Energieplan, kein Takt-Absenken.",
          "Legt den versteckten Plan 'Ultimative Leistung' an. Mehr Verbrauch und Wärme. Fällt auf Höchstleistung zurück, falls nicht vorhanden.",
          kind="power", power_target="ultimate", recommended="desktop", tags=("FPS", "FRAMETIME"), why="Stabilere Taktung am Desktop."),
        T("power_high", "Höchstleistung", [G], "Windows-Energieplan 'Höchstleistung'.",
          "Alternative zu 'Ultimative Leistung'.", kind="power", power_target="high", tags=("FPS",)),
        T("ps_min_cpu", "CPU-Takt immer oben", [G, L], "Prozessor-Mindestzustand 100 % im Netzbetrieb.",
          "Die CPU taktet nicht mehr herunter und reagiert ohne Hochtakt-Verzögerung. Mehr Leerlaufverbrauch.",
          kind="powersetting", ps_sub="SUB_PROCESSOR", ps_setting="PROCTHROTTLEMIN", ps_value=100,
          recommended="desktop", tags=("FRAMETIME", "LATENZ"), why="Kein Takt-Absenken beim Spielen."),
        T("ps_core_parking_off", "Kernparken aus", [G, L], "Alle CPU-Kerne bleiben aktiv.",
          "Verhindert, dass Windows Kerne schlafen legt und bei Lastspitzen erst aufwecken muss.",
          kind="powersetting", ps_sub="SUB_PROCESSOR", ps_setting="CPMINCORES", ps_value=100,
          recommended="desktop", tags=("FRAMETIME",), why="Weniger Aufwach-Ruckler."),
        T("games_task", "Spiele-Priorität im Scheduler", [G, F], "Windows bevorzugt Spiele bei CPU und GPU.",
          "MMCSS-Aufgabe 'Games': GPU-Priorität 8, Priorität 6, Kategorie High. Hilft bei Hintergrundlast und 1%-Lows.",
          values=[_dw(HKLM_MM + r"\Tasks\Games", "GPU Priority", 8), _dw(HKLM_MM + r"\Tasks\Games", "Priority", 6),
                  _sz(HKLM_MM + r"\Tasks\Games", "Scheduling Category", "High"), _sz(HKLM_MM + r"\Tasks\Games", "SFIO Priority", "High")],
          admin=True, restart="Neustart", recommended="baseline", tags=("FPS", "FRAMETIME"), why="Spiel bekommt Vorrang."),
        T("win32_prio", "Vordergrund-Boost", [G, L], "Das aktive Spiel bekommt mehr Rechenzeit.",
          "Win32PrioritySeparation = 0x26: kurze, feste Zeitscheiben mit starker Vordergrund-Bevorzugung.",
          values=[_dw(r"HKLM\SYSTEM\CurrentControlSet\Control\PriorityControl", "Win32PrioritySeparation", 38)],
          admin=True, restart="Neustart", recommended="desktop", tags=("LATENZ", "FRAMETIME"), why="Vordergrund vor Hintergrund."),
        T("timer_res", "Präzise Zeitgeber", [L], "Konstante 0,5-ms-Zeitgeber für flüssigere Frametimes.",
          "GlobalTimerResolutionRequests=1 (ab Windows 11 relevant). Mehr Timer-Genauigkeit, minimal mehr Stromverbrauch.",
          values=[_dw(r"HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\kernel", "GlobalTimerResolutionRequests", 1)],
          admin=True, restart="Neustart", recommended="desktop", tags=("LATENZ", "FRAMETIME"), why="Gleichmäßigere Frametimes."),
        T("power_throttling_off", "Power Throttling aus", [G], "Windows drosselt keine Hintergrund-Programme auf Sparmodus.",
          "Spiel und Launcher laufen mit voller Leistung. Minimal mehr Verbrauch.",
          values=[_dw(r"HKLM\SYSTEM\CurrentControlSet\Control\Power\PowerThrottling", "PowerThrottlingOff", 1)],
          admin=True, restart="Neustart", recommended="desktop", tags=("FPS",), why="Konstante Taktung."),
        T("ps_pcie_aspm_off", "PCIe-Sparmodus aus", [L], "Die GPU-Verbindung schläft nie ein.",
          "Link State Power Management aus. Vermeidet seltene Aufwach-Verzögerungen der Grafikkarte.",
          kind="powersetting", ps_sub="SUB_PCIE", ps_setting="ASPM", ps_value=0,
          recommended="desktop", tags=("FRAMETIME",), why="Keine GPU-Aufwach-Ruckler."),
        T("msi_gpu", "GPU Interrupts (MSI)", [L], "Effizientere Interrupts für die Grafikkarte.",
          "Aktiviert Message Signaled Interrupts für alle Grafikkarten. Aktuelle RTX-Treiber nutzen das oft schon, dann ändert sich nichts.",
          dynamic=msi_gpu_values, admin=True, restart="Neustart", tags=("LATENZ",), risk="mittel", why="Weniger DPC-Latenz."),
        T("game_mode", "Windows Game Mode", [G], "Windows priorisiert das Spiel.",
          "Spiele-Modus aktivieren. Der Effekt ist je nach System klein, aber sicher.",
          values=[_dw(r"Software\Microsoft\GameBar", "AutoGameModeEnabled", 1), _dw(r"Software\Microsoft\GameBar", "AllowAutoGameMode", 1)],
          recommended="baseline", tags=("FPS",), why="Standard für Spiele."),
        T("game_dvr", "Game DVR aus", [G], "Keine Hintergrundaufnahme.",
          "Schaltet Xbox-Hintergrundaufnahme ab (spart Overhead). Clips über die Game Bar gehen dann nicht mehr.",
          values=[_dw(r"System\GameConfigStore", "GameDVR_Enabled", 0), _dw(r"Software\Microsoft\Windows\CurrentVersion\GameDVR", "AppCaptureEnabled", 0)],
          restart="Neustart des Spiels", recommended="baseline", tags=("FPS",), why="Entfernt Aufnahme-Overhead."),
        T("fso_global", "Echtes Vollbild bevorzugen", [G, L], "Direkter Vollbild-Pfad statt Fenster-Optimierung.",
          "Kann die Eingabelatenz in DirectX-Spielen senken. Alt-Tab ist etwas träger.",
          values=[_dw(r"System\GameConfigStore", "GameDVR_FSEBehaviorMode", 2), _dw(r"System\GameConfigStore", "GameDVR_HonorUserFSEBehaviorMode", 1),
                  _dw(r"System\GameConfigStore", "GameDVR_DXGIHonorFSEWindowsCompatible", 1)],
          restart="nächster Spielstart", recommended="competitive", tags=("LATENZ",), why="Weniger Latenz im Vollbild."),
        T("mouse_accel", "Mausbeschleunigung aus", [G, L], "1:1-Mausbewegung.",
          "Setzt Zeigerbeschleunigung auf 0 und übernimmt sofort.",
          values=[_sz(r"Control Panel\Mouse", "MouseSpeed", "0"), _sz(r"Control Panel\Mouse", "MouseThreshold1", "0"),
                  _sz(r"Control Panel\Mouse", "MouseThreshold2", "0")],
          hook="mouse_live", recommended="baseline", tags=("LATENZ",), why="Gleichmäßige Mausbewegung."),
        T("ps_usb_suspend_off", "USB-Sparmodus aus", [L], "Maus und Tastatur schlafen nie ein.",
          "USB Selective Suspend aus (Netzbetrieb).", kind="powersetting", ps_sub="2a737441-1930-4402-8d77-b2bebba308a3",
          ps_setting="48e6b7a6-50f5-4782-a5d4-53bb8f07e226", ps_value=0, recommended="desktop", tags=("LATENZ",), why="Keine Aufwach-Verzögerung."),
        T("sticky_keys_off", "Tastatur-Popups aus", [G], "Keine 5x-Shift-Fenster mitten im Match.",
          "Schaltet Einrast-, Umschalt- und Anschlagverzögerung-Popups aus.",
          values=[_sz(r"Control Panel\Accessibility\StickyKeys", "Flags", "506"), _sz(r"Control Panel\Accessibility\ToggleKeys", "Flags", "58"),
                  _sz(r"Control Panel\Accessibility\Keyboard Response", "Flags", "122")],
          restart="Neuanmeldung", recommended="baseline", tags=("FPS",), why="Verhindert, dass Fortnite minimiert wird."),
        T("keyboard_fast", "Schnelle Tastaturwiederholung", [G], "Kürzeste Verzögerung, höchste Rate.",
          "KeyboardDelay 0, KeyboardSpeed 31.", values=[_sz(r"Control Panel\Keyboard", "KeyboardDelay", "0"), _sz(r"Control Panel\Keyboard", "KeyboardSpeed", "31")],
          restart="Neuanmeldung", recommended="competitive", tags=("LATENZ",), why="Schnellere Tasten."),
        # ------------------------------------------------------------------ Ping / Netzwerk
        T("net_adapter_stable", "LAN-Adapter ohne Sparmodus", [N], "Stabilerer Ping: keine Energiespar-Pausen im Netzwerkchip.",
          "Schaltet Energy-Efficient-Ethernet, Green Ethernet und Flow Control am verbundenen LAN-Adapter aus. Diese Funktionen verursachen Mikro-Pausen und Ping-Spitzen. Die Verbindung unterbricht dabei 1–3 s.",
          kind="netadapter", adapter_props=LAN_PROPS, admin=True, recommended="desktop", tags=("PING",), why="Weniger Ping-Spitzen."),
        T("net_throttle_off", "Netzwerk-Drosselung aus", [N, G], "Windows bremst Pakete beim Spielen nicht mehr.",
          "NetworkThrottlingIndex aus und Systemreaktionszeit 0 %. Wirkt vor allem bei laufender Musik/Stream.",
          values=[_dw(HKLM_MM, "NetworkThrottlingIndex", 4294967295), _dw(HKLM_MM, "SystemResponsiveness", 0)],
          admin=True, restart="Neustart", recommended="baseline", tags=("PING", "FPS"), why="Keine Paket-Drosselung."),
        T("delivery_opt_off", "Kein Update-Upload", [N], "Dein PC lädt keine Windows-Updates für andere hoch.",
          "Delivery Optimization aus. Verhindert Upload im Hintergrund, der den Ping stören kann.",
          values=[_dw(r"HKLM\SOFTWARE\Policies\Microsoft\Windows\DeliveryOptimization", "DODownloadMode", 0)],
          admin=True, restart="Neustart", tags=("PING",), why="Kein Hintergrund-Upload."),
        # ------------------------------------------------------------------ Fortnite
        T("fn_graphics_perf", "Grafik auf Leistung", [F], "Schatten, Effekte, Post, Laub, GI, Reflexionen auf Niedrig.",
          "Der größte Hebel für FPS und 1%-Lows. Sichtweite und Texturen bleiben unverändert. Fortnite muss beendet sein.",
          kind="ini", ini_section=_FG, ini_values=_GFX, recommended="fortnite", tags=("FPS", "FRAMETIME"), why="Weniger GPU/CPU-Last."),
        T("fn_fps_limit", "FPS-Limit 240", [F], "Kein FPS-Überlauf über deine Monitor-Hz.",
          "FrameRateLimit=240. Glättet die Frametime.", kind="ini", ini_section=_FG, ini_values={"FrameRateLimit": "240.000000"},
          recommended="fortnite", tags=("FRAMETIME",), why="Stabile Frametimes."),
        T("fn_vsync_off", "V-Sync aus", [F], "Weniger Eingabelatenz.",
          "bUseVSync=False. Mit G-SYNC/FreeSync kaum Tearing.", kind="ini", ini_section=_FG, ini_values={"bUseVSync": "False"},
          recommended="fortnite", tags=("LATENZ",), why="V-Sync erhöht Latenz."),
        T("fn_fullscreen", "Echtes Vollbild", [F], "Vollbild statt Fenster-Vollbild.",
          "FullscreenMode=0. Senkt die Eingabelatenz.", kind="ini", ini_section=_FG,
          ini_values={"FullscreenMode": "0", "PreferredFullscreenMode": "0", "LastConfirmedFullscreenMode": "0"},
          recommended="fortnite", tags=("LATENZ",), why="Direkter Pfad."),
        T("fn_motionblur_off", "Bewegungsunschärfe aus", [F], "Klareres Bild beim Drehen.",
          "bMotionBlur=False.", kind="ini", ini_section=_FG, ini_values={"bMotionBlur": "False"},
          recommended="fortnite", tags=("FPS",), why="Klarer und leichter."),
        T("fn_menu_fps", "Lobby auf 60 FPS", [F], "Weniger Wärme und Lärm im Menü.",
          "MenuFrameRateLimit_Unified=60. Kein Einfluss auf Matches.", kind="ini", ini_section=_FG,
          ini_values={"MenuFrameRateLimit_Unified": "60.000000"}, tags=()),
        T("fn_exe_flags", "Vollbild-Optimierung für Fortnite aus", [F], "Windows-Kompatibilitäts-Flag direkt für Fortnite.",
          "Setzt für FortniteClient-Win64-Shipping.exe das Flag 'Vollbildoptimierungen deaktivieren'. Pfad kommt aus dem Epic Launcher.",
          dynamic=fortnite_exe_flag_values, recommended="competitive", tags=("LATENZ",), why="Direkter Vollbild-Pfad."),

        # ------------------------------------------------------------------ neu (Recherche)
        T("vbs_off", "Speicher-Integrität (HVCI) aus", [G, L], "Windows-Sicherheitsfunktion aus: messbar mehr FPS.",
          "Schaltet VBS/HVCI ab. Tests von Tom's Hardware zeigten im Schnitt ca. 5 % mehr FPS (bis 17 % in einzelnen Spielen), besonders bei den 1%-Lows; PCWorld sah teils nur Messtoleranz. Nachteil: weniger Schutz vor Kernel-Angriffen. Windows kann den Wert per Richtlinie zurücksetzen.",
          values=[_dw(r"HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios\HypervisorEnforcedCodeIntegrity", "Enabled", 0),
                  _dw(r"HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard", "EnableVirtualizationBasedSecurity", 0)],
          admin=True, restart="Neustart", tags=("FPS", "FRAMETIME"), risk="mittel", why="Messbarer FPS-Gewinn, Sicherheits-Kompromiss."),
        T("ps_boost_aggressive", "CPU-Boost aggressiv", [G, L], "Die CPU taktet bei Last schneller hoch.",
          "Prozessor-Leistungsboost-Modus 'Aggressiv' (Netzbetrieb). Schnelleres Hochtakten bei Lastspitzen, minimal mehr Verbrauch.",
          kind="powersetting", ps_sub="SUB_PROCESSOR", ps_setting="PERFBOOSTMODE", ps_value=2, tags=("FRAMETIME",)),
        T("net_interrupt_mod_off", "LAN: Interrupt-Bündelung aus", [N, L], "Pakete werden sofort statt gebündelt verarbeitet.",
          "Interrupt Moderation aus: etwas geringere Latenz, dafür minimal mehr CPU-Last bei viel Traffic.",
          kind="netadapter", adapter_props={"*InterruptModeration": "0"}, admin=True, tags=("PING", "LATENZ"), risk="mittel"),
        T("faststartup_off", "Windows-Schnellstart aus", [S], "Echter Neustart statt Hibernate-Start: sauberere Treiber.",
          "HiberbootEnabled=0. Behebt Treiber-Reste nach dem Herunterfahren; Bootzeit minimal länger.",
          values=[_dw(r"HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Power", "HiberbootEnabled", 0)],
          admin=True, restart="Neustart", tags=()),
        T("fn_aa_off", "Anti-Aliasing aus", [F], "Spürbar mehr FPS, Kanten sind etwas gezackt.",
          "sg.AntiAliasingQuality=0. Wirkt mit Fortnite-Rendering 'Performance' und DX11 am stärksten.",
          kind="ini", ini_section=_FG, ini_values={f"{_FG}|sg.AntiAliasingQuality": "0", "ScalabilityGroups|sg.AntiAliasingQuality": "0"},
          tags=("FPS",)),
        T("fn_gpu_pref", "Fortnite nutzt die starke GPU", [F], "Windows startet Fortnite auf der Hochleistungs-GPU.",
          "Setzt die GPU-Präferenz für Fortnite auf 'Hochleistung'. Hilft vor allem bei Systemen mit zwei Grafikchips.",
          dynamic=fortnite_gpu_pref_values, tags=("FPS",)),
        # ------------------------------------------------------------------ Verstaerkung: maximale FPS
        T("fn_cpu_prio", "Fortnite: hohe CPU-Priorität", [F, G], "Windows startet Fortnite immer mit hoher Priorität.",
          "Setzt für FortniteClient-Win64-Shipping.exe die CPU-Priorität 'Hoch' (PerfOptions). Das Spiel bekommt bei Hintergrundlast zuerst Rechenzeit. Wird beim Zurücksetzen wieder entfernt.",
          values=[_dw(r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\FortniteClient-Win64-Shipping.exe\PerfOptions",
                      "CpuPriorityClass", 3)],
          admin=True, restart="nächster Spielstart", recommended="competitive", tags=("FPS", "FRAMETIME"), why="Spiel bekommt dauerhaft Vorrang."),
        T("ps_epp_perf", "CPU: Leistung statt Sparen", [G, L], "Die CPU bevorzugt maximale Leistung beim Hochtakten.",
          "Energy Performance Preference auf 0 (Netzbetrieb): die CPU taktet bei Last sofort und voll hoch. Mehr Wärme.",
          kind="powersetting", ps_sub="SUB_PROCESSOR", ps_setting="PERFEPP", ps_value=0, recommended="competitive",
          tags=("FPS", "FRAMETIME"), why="Schnelleres Hochtakten."),
        T("ps_max_cpu", "CPU-Maximum 100 %", [G], "Keine Drosselung nach oben.",
          "Maximaler Prozessorzustand 100 % im Netzbetrieb. Stellt sicher, dass der Plan die CPU nie deckelt.",
          kind="powersetting", ps_sub="SUB_PROCESSOR", ps_setting="PROCTHROTTLEMAX", ps_value=100, recommended="competitive",
          tags=("FPS",), why="Kein Takt-Deckel."),
        T("ps_cooling_active", "Aktive Kühlung bevorzugen", [G], "Lüfter statt Drosselung bei Hitze.",
          "Kühlungsrichtlinie 'Aktiv' (Netzbetrieb): Windows dreht erst die Lüfter auf, bevor es die CPU drosselt.",
          kind="powersetting", ps_sub="SUB_PROCESSOR", ps_setting="SYSCOOLPOL", ps_value=1, recommended="competitive",
          tags=("FRAMETIME",), why="Weniger Hitze-Drosselung."),
        T("gamebar_off", "Game-Bar-Overlay aus", [G], "Keine Game-Bar-Einblendungen und -Hooks.",
          "Schaltet Startfenster und Controller-Aufruf der Game Bar aus. Spart Overlay-Overhead.",
          values=[_dw(r"Software\Microsoft\GameBar", "ShowStartupPanel", 0), _dw(r"Software\Microsoft\GameBar", "UseNexusForGameBarEnabled", 0)],
          restart="Neuanmeldung", recommended="baseline", tags=("FPS",), why="Weniger Overlay-Last."),
        T("fn_grass_off", "Fortnite: Gras aus", [F], "Weniger Dekor-Objekte, mehr FPS.",
          "bShowGrass=False blendet dekoratives Gras aus (kein Spielelement wie hohes Gras zum Verstecken). Fortnite muss beendet sein.",
          kind="ini", ini_section=_FG, ini_values={"bShowGrass": "False"}, recommended="fortnite", tags=("FPS",), why="Weniger Objekte zu zeichnen."),
        T("fn_multithread", "Fortnite: Multithread-Rendering", [F], "Fortnite nutzt mehr CPU-Kerne zum Rendern.",
          "bAllowMultithreadedRendering=True. Verteilt Render-Arbeit auf mehrere Kerne. Fortnite muss beendet sein.",
          kind="ini", ini_section=_FG, ini_values={"bAllowMultithreadedRendering": "True"}, recommended="fortnite", tags=("FPS", "FRAMETIME"),
          why="Mehr Kerne = höhere CPU-Grenze."),
        T("hags_on", "GPU-Planung per Hardware (HAGS)", [G, L], "Die GPU plant ihren Speicher selbst.",
          "HwSchMode=2. Kann Latenz senken und Frame Generation (DLSS 3/FSR 3) ermöglichen. Bei älteren Karten/Treibern kann es auch nichts bringen. Neustart nötig.",
          values=[_dw(r"HKLM\SYSTEM\CurrentControlSet\Control\GraphicsDrivers", "HwSchMode", 2)],
          admin=True, restart="Neustart", tags=("FPS", "LATENZ")),
        T("mpo_off", "Multiplane Overlay aus", [G], "Behebt Ruckler/Flackern auf manchen NVIDIA/AMD-Systemen.",
          "OverlayTestMode=5 schaltet MPO im Desktop-Fenstermanager ab. Hilft bei Stottern und schwarzen Bildschirmen; sonst keine Wirkung.",
          values=[_dw(r"HKLM\SOFTWARE\Microsoft\Windows\Dwm", "OverlayTestMode", 5)], admin=True, restart="Neustart", tags=("FRAMETIME",)),
        T("mitigations_off", "Spectre/Meltdown-Schutz aus", [G], "Mehr CPU-Leistung, vor allem bei älteren Prozessoren.",
          "FeatureSettingsOverride=3 (+Mask 3) schaltet die Spectre/Meltdown-Abschwächungen ab. Gewinn: klein bei neuen CPUs, spürbar bei älteren Intel-Modellen. "
          "Nachteil: weniger Schutz vor Seitenkanal-Angriffen. Nur für reine Gaming-PCs. Neustart nötig.",
          values=[_dw(r"HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management", "FeatureSettingsOverride", 3),
                  _dw(r"HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management", "FeatureSettingsOverrideMask", 3)],
          admin=True, restart="Neustart", tags=("FPS",), risk="mittel", why="Mehr CPU-Leistung, Sicherheits-Kompromiss."),
        # ------------------------------------------------------------------ System
        T("bg_apps_off", "Hintergrund-Apps aus", [S], "Store-Apps laufen nicht im Hintergrund.",
          "Spart CPU, RAM und Netzwerk.", values=[_dw(r"Software\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications", "GlobalUserDisabled", 1),
                                                  _dw(r"Software\Microsoft\Windows\CurrentVersion\Search", "BackgroundAppGlobalToggle", 0)],
          restart="Neuanmeldung", tags=("FPS",), why="Weniger Hintergrundlast."),
        T("telemetry_policy", "Telemetrie minimal", [S], "Weniger Diagnosedaten-Versand.",
          "AllowTelemetry=0. Home-Editionen nutzen die niedrigste erlaubte Stufe.",
          values=[_dw(r"HKLM\SOFTWARE\Policies\Microsoft\Windows\DataCollection", "AllowTelemetry", 0)], admin=True, restart="Neustart", tags=()),
        T("diagtrack_off", "Telemetrie-Dienst aus", [S], "DiagTrack läuft nicht mehr.",
          "Starttyp 'Deaktiviert' für den Dienst 'Benutzererfahrungen und Telemetrie'.",
          values=[_dw(r"HKLM\SYSTEM\CurrentControlSet\Services\DiagTrack", "Start", 4)], admin=True, restart="Neustart", tags=("FPS",)),
        T("visualfx", "Windows-Effekte: beste Leistung", [S], "Weniger Animationen und Effekte.",
          "VisualFXSetting=2.", values=[_dw(r"Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects", "VisualFXSetting", 2)],
          restart="Neuanmeldung", tags=()),
        T("transparency_off", "Transparenz aus", [S], "Weniger DWM-Last.", "EnableTransparency=0.",
          values=[_dw(r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize", "EnableTransparency", 0)], tags=()),
        T("window_anim_off", "Fensteranimationen aus", [S], "Fenster reagieren direkter.", "MinAnimate=0.",
          values=[_sz(r"Control Panel\Desktop\WindowMetrics", "MinAnimate", "0")], restart="Neuanmeldung", tags=()),
    ]


# Wirkung laut Tests/Quellen: belegt = messbar, klein = klein/systemabhaengig, schwach = kaum belegt/umstritten
EVIDENCE = {
    "fn_cpu_prio": "klein", "ps_epp_perf": "klein", "ps_max_cpu": "klein", "ps_cooling_active": "klein", "gamebar_off": "klein",
    "fn_grass_off": "klein", "fn_multithread": "klein", "hags_on": "klein", "mpo_off": "klein", "mitigations_off": "klein",
    "fn_graphics_perf": "belegt", "fn_vsync_off": "belegt", "fn_aa_off": "belegt", "vbs_off": "belegt",
    "power_ultimate": "klein", "power_high": "klein", "ps_min_cpu": "klein", "ps_core_parking_off": "klein", "ps_pcie_aspm_off": "klein",
    "ps_usb_suspend_off": "klein", "ps_boost_aggressive": "klein", "msi_gpu": "klein", "game_mode": "klein", "game_dvr": "klein",
    "fso_global": "klein", "mouse_accel": "klein", "sticky_keys_off": "klein", "keyboard_fast": "klein", "net_adapter_stable": "klein",
    "net_interrupt_mod_off": "klein", "delivery_opt_off": "klein", "timer_res": "klein", "power_throttling_off": "klein",
    "bg_apps_off": "klein", "faststartup_off": "klein", "fn_fps_limit": "klein", "fn_fullscreen": "klein", "fn_motionblur_off": "klein",
    "fn_menu_fps": "klein", "fn_exe_flags": "klein", "fn_gpu_pref": "klein",
    "net_throttle_off": "schwach", "games_task": "schwach", "win32_prio": "schwach", "telemetry_policy": "schwach",
    "diagtrack_off": "schwach", "visualfx": "schwach", "transparency_off": "schwach", "window_anim_off": "schwach",
}
# Laut Recherche kaum/umstritten belegt: nicht mehr automatisch gesetzt, bleiben als manueller Schalter.
NOT_AUTO = ("net_throttle_off", "games_task", "win32_prio", "timer_res")
_build_raw = build_catalog


def build_catalog() -> list[Tweak]:
    out = _build_raw()
    for t in out:
        t.evidence = EVIDENCE.get(t.id, "")
        if t.id in NOT_AUTO:
            t.recommended = ""
    return out


# ---------------------------------------------------------------------------
# Auswahl fuer den Auto-Modus
# ---------------------------------------------------------------------------
PROFILES = {
    "safe": ("Safe", "Nur Basis-Tweaks, minimales Risiko."),
    "competitive": ("Competitive", "Alles Empfohlene für dein System."),
    "maxfps": ("Max FPS", "Alles für maximale FPS: Competitive plus Effekte, Hintergrund, Telemetrie, GPU-MSI, Boost, Gras/AA aus. Gilt auch für Notebooks (am Netz)."),
}
MAXFPS_EXTRA_IDS = ("visualfx", "transparency_off", "window_anim_off", "bg_apps_off", "telemetry_policy", "diagtrack_off",
                    "delivery_opt_off", "msi_gpu", "fn_menu_fps", "fn_aa_off", "ps_boost_aggressive", "net_interrupt_mod_off", "faststartup_off",
                    "fn_grass_off", "timer_res", "win32_prio", "games_task", "net_throttle_off")


def by_category(tweaks: list[Tweak], category: str) -> list[Tweak]:
    return [t for t in tweaks if category in t.categories]


def applicable(t: Tweak, ctx: dict) -> tuple[bool, str]:
    if t.recommended == "desktop" and not ctx.get("desktop", True):
        return False, "Notebook: Dauer-Hochtakt wird nicht automatisch gesetzt."
    if t.admin and not ctx.get("admin", True):
        return False, "Braucht Administratorrechte."
    if t.kind == "ini":
        if not ctx.get("fortnite_config", False):
            return False, "Fortnite-Config nicht gefunden."
        if ctx.get("fortnite_running", False):
            return False, "Fortnite läuft."
    return True, ""


def recommend(catalog: list[Tweak], engine: TweakEngine, ctx: dict):
    chosen: list[Tweak] = []
    skipped: list[tuple[Tweak, str]] = []
    for t in catalog:
        if t.kind not in TOGGLE_KINDS or not t.recommended:
            continue
        ok, reason = applicable(t, ctx)
        if not ok:
            skipped.append((t, reason))
            continue
        state, _ = engine.status(t)
        if state == STATUS_ACTIVE:
            continue
        if state == STATUS_UNKNOWN and t.kind in ("powersetting", "ini", "netadapter") or (state == STATUS_UNKNOWN and t.dynamic):
            skipped.append((t, "Auf diesem System nicht verfügbar."))
            continue
        chosen.append(t)
    return chosen, skipped


def select_for_profile(catalog: list[Tweak], engine: TweakEngine, ctx: dict, profile: str = "competitive"):
    if profile not in PROFILES:
        profile = "competitive"
    if profile == "maxfps":
        ctx = dict(ctx, desktop=True)      # Max FPS gilt auch fuer Notebooks (Werte gelten nur im Netzbetrieb bzw. werden gesichert)
    chosen, skipped = recommend(catalog, engine, ctx)
    if profile == "safe":
        skipped = skipped + [(t, "Nicht im Profil Safe.") for t in chosen if t.recommended != "baseline"]
        chosen = [t for t in chosen if t.recommended == "baseline"]
    elif profile == "maxfps":
        have = {t.id for t in chosen}
        for t in catalog:
            if t.id in MAXFPS_EXTRA_IDS and t.id not in have and t.kind in TOGGLE_KINDS:
                ok, reason = applicable(t, ctx)
                if not ok:
                    skipped.append((t, reason))
                    continue
                state = engine.status(t)[0]
                if state not in (STATUS_ACTIVE, STATUS_UNKNOWN):
                    chosen.append(t)
    return chosen, skipped
