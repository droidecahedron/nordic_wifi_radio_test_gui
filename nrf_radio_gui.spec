# -*- mode: python ; coding: utf-8 -*-
#
# Copyright (c) 2026 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: Apache-2.0
#
"""PyInstaller spec. One file per platform, built on that platform.

    pyinstaller nrf_radio_gui.spec

PyInstaller does not cross-compile. A Windows .exe must be built on Windows and
a macOS .app on macOS; there is no flag that produces either from Linux. CI does
all three, see .github/workflows/build.yml.

A console build, for when a traceback in the frozen binary would otherwise be
swallowed:

    NRF_RADIO_GUI_CONSOLE=1 pyinstaller nrf_radio_gui.spec

That is an environment variable rather than a second spec so the two builds
cannot drift apart.

`nrfutil` is NOT bundled. It is a separate Nordic binary with its own licence and
update cadence, and the tool only needs it to enumerate kits and to flash — the
shell is driven over a plain serial port. It is looked up on PATH.
"""

import os
from pathlib import Path

CONSOLE = os.environ.get("NRF_RADIO_GUI_CONSOLE", "") not in ("", "0", "false")
NAME = "nrf-radio-test" + ("-console" if CONSOLE else "")

# Only QtCore and QtWidgets are imported. Qt6 ships 224 MB, most of it QML,
# Quick, 3D, Designer and PDF, none of which this reaches.
EXCLUDE = [
    "PyQt6.QtQml", "PyQt6.QtQuick", "PyQt6.QtQuick3D", "PyQt6.QtQuickWidgets",
    "PyQt6.QtWebEngineCore", "PyQt6.QtWebEngineWidgets", "PyQt6.QtWebEngineQuick",
    "PyQt6.QtWebChannel", "PyQt6.QtWebSockets",
    "PyQt6.QtDesigner", "PyQt6.QtHelp", "PyQt6.QtTest",
    "PyQt6.QtPdf", "PyQt6.QtPdfWidgets",
    "PyQt6.QtMultimedia", "PyQt6.QtMultimediaWidgets",
    "PyQt6.QtBluetooth", "PyQt6.QtNfc", "PyQt6.QtPositioning", "PyQt6.QtSensors",
    "PyQt6.QtSerialPort", "PyQt6.QtSql", "PyQt6.QtCharts", "PyQt6.QtSvgWidgets",
    "PyQt6.QtDataVisualization", "PyQt6.QtRemoteObjects", "PyQt6.QtSpatialAudio",
    "PyQt6.QtTextToSpeech", "PyQt6.QtHttpServer", "PyQt6.QtQuick3DPhysics",
    # Not Qt: pulled in by other tooling in the same venv, never by this app.
    "tkinter", "PIL", "numpy", "matplotlib", "pytest", "setuptools", "pip",
    "PyInstaller",
]

# The bundled image, so Flash works from a frozen binary. app.bundled_firmware()
# looks under sys._MEIPASS, which is where this lands.
firmware = [(str(path), "firmware")
            for path in sorted(Path("firmware").glob("*.hex"))]

analysis = Analysis(
    ["nrf_radio_gui/__main__.py"],
    pathex=[],
    binaries=[],
    datas=firmware,
    # __main__ imports these inside functions so that --version and --selftest
    # do not pay for Qt. Named here because a function-level import is easy for
    # static analysis to miss, and missing one only shows up at runtime.
    hiddenimports=[
        "serial.tools.list_ports",
        "nrf_radio_gui.app",
        "nrf_radio_gui.benchcheck",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=EXCLUDE,
    noarchive=False,
)

pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    analysis.binaries,
    analysis.datas,
    name=NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # UPX trips antivirus heuristics on Windows more than it saves
    console=CONSOLE,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,   # host arch. macOS universal2 needs a universal Python
    codesign_identity=None,
    entitlements_file=None,
)
