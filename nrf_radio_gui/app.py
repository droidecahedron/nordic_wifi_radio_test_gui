#
# Copyright (c) 2026 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: Apache-2.0
#
"""Window, wiring, and the send funnel.

Every command reaches the kit through `send_command()`. Nothing else touches the
transport, so the rules that must not be bypassed — the reply mode from the
table, the guard on anything that discards configuration — live in one place.

Serial work runs on a worker thread. Discovery takes up to 1.5 s per port and a
deferred reply takes about 1.4 s, both long enough to freeze the window if run on
the GUI thread.
"""

import sys
from pathlib import Path

from PyQt6.QtCore import QObject, Qt, QThread, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from nrf_radio_gui import __version__, discovery, nrfutil, theme
from nrf_radio_gui.commands import ficr, shortrange, wifi
from nrf_radio_gui.commands.spec import Reply
from nrf_radio_gui.discovery import State
from nrf_radio_gui.transport import Transport
from nrf_radio_gui.widgets.command_tab import CommandTab
from nrf_radio_gui.widgets.ficr_tab import FicrTab

# tests/test_factory.py derives a row width budget from this, so widen it there too.
WINDOW_W = 1000
WINDOW_H = 760

LOG_LIMIT = 5000

# Where a bundled image is looked for, both from a checkout and from a
# PyInstaller bundle, whose _MEIPASS directory is the executable's own.
FIRMWARE_DIRS = ("firmware", ".")


def bundled_firmware():
    """Hex files shipped with the tool, if any."""
    roots = [Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))]
    found = []
    for root in roots:
        for sub in FIRMWARE_DIRS:
            found.extend(sorted((root / sub).glob("*.hex")))
    return found


class Worker(QObject):
    """Serial and nrfutil work, off the GUI thread."""

    scanned = pyqtSignal(object, object)   # devices, probes
    exchanged = pyqtSignal(object)         # Exchange
    noted = pyqtSignal(str)
    failed = pyqtSignal(str)
    flashed = pyqtSignal(bool, str)

    def __init__(self):
        super().__init__()
        self._transport = None

    @pyqtSlot()
    def scan(self):
        try:
            devices = nrfutil.list_devices() if nrfutil.available() else ()
        except nrfutil.NrfutilError as err:
            self.failed.emit(str(err))
            devices = ()
        if not devices:
            self.noted.emit("no kits found")
            self.scanned.emit((), ())
            return
        probes = discovery.scan(devices)
        self.scanned.emit(devices, probes)

    @pyqtSlot(str)
    def connect_port(self, port):
        self.close_port()
        try:
            self._transport = Transport(port)
            self._transport.open()
            self.noted.emit(f"opened {port}")
        except Exception as err:
            self._transport = None
            self.failed.emit(f"could not open {port}: {err}")

    @pyqtSlot()
    def close_port(self):
        if self._transport is not None:
            self._transport.close()
            self._transport = None

    @pyqtSlot(str, object)
    def send(self, line, reply):
        if self._transport is None:
            self.failed.emit("not connected")
            return
        try:
            self.exchanged.emit(self._transport.send(line, reply or Reply.NONE))
        except Exception as err:
            self.failed.emit(f"{line}: {err}")

    @pyqtSlot(str, str, str)
    def flash(self, hex_path, serial, family):
        was_open = self._transport is not None
        port = self._transport.port if was_open else ""
        self.close_port()   # the programmer needs the kit, and a reset drops the port
        try:
            nrfutil.program(hex_path, serial, family=family or None)
            self.flashed.emit(True, f"programmed {Path(hex_path).name}")
        except nrfutil.NrfutilError as err:
            self.flashed.emit(False, str(err))
        finally:
            if was_open and port:
                self.connect_port(port)


class MainWindow(QMainWindow):
    _scan_requested = pyqtSignal()
    _connect_requested = pyqtSignal(str)
    _disconnect_requested = pyqtSignal()
    _send_requested = pyqtSignal(str, object)
    _flash_requested = pyqtSignal(str, str, str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("nRF Radio Test")
        self.resize(WINDOW_W, WINDOW_H)

        self.devices = ()
        self.probes = ()
        self.probe = None

        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(10, 10, 10, 8)
        outer.setSpacing(8)
        outer.addLayout(self._build_toolbar())

        self.tabs = QTabWidget()
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(LOG_LIMIT)

        split = QSplitter(Qt.Orientation.Vertical)
        split.addWidget(self.tabs)
        split.addWidget(self.log)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 1)
        split.setSizes([520, 200])
        outer.addWidget(split, 1)

        self.setCentralWidget(central)
        self.setStatusBar(QStatusBar())
        self._set_status("starting")

        self._start_worker()
        self._build_tabs(None)
        self.note(f"nrf_radio_gui {__version__}")
        self._scan_requested.emit()

    # -- construction -----------------------------------------------------

    def _build_toolbar(self):
        bar = QHBoxLayout()
        bar.setSpacing(6)

        self.device_box = QComboBox()
        self.device_box.setMinimumWidth(300)
        self.device_box.currentIndexChanged.connect(self._device_changed)
        bar.addWidget(QLabel("Kit"))
        bar.addWidget(self.device_box)

        self.rescan_button = QPushButton("Rescan")
        self.rescan_button.clicked.connect(self._rescan)
        bar.addWidget(self.rescan_button)

        self.connect_button = QPushButton("Connect")
        self.connect_button.setProperty("role", "primary")
        self.connect_button.clicked.connect(self._toggle_connection)
        bar.addWidget(self.connect_button)

        self.flash_button = QPushButton("Flash")
        self.flash_button.clicked.connect(self._flash)
        bar.addWidget(self.flash_button)

        bar.addStretch(1)
        self.state_label = QLabel("no kit")
        self.state_label.setProperty("role", "caption")
        bar.addWidget(self.state_label)
        return bar

    def _start_worker(self):
        self.thread = QThread(self)
        self.worker = Worker()
        self.worker.moveToThread(self.thread)

        self._scan_requested.connect(self.worker.scan)
        self._connect_requested.connect(self.worker.connect_port)
        self._disconnect_requested.connect(self.worker.close_port)
        self._send_requested.connect(self.worker.send)
        self._flash_requested.connect(self.worker.flash)

        self.worker.scanned.connect(self._on_scanned)
        self.worker.exchanged.connect(self._on_exchange)
        self.worker.noted.connect(self.note)
        self.worker.failed.connect(self._on_failed)
        self.worker.flashed.connect(self._on_flashed)

        self.thread.start()

    def _build_tabs(self, probe):
        """Rebuild every tab for `probe`. None means nothing is known yet."""
        self.tabs.clear()
        self.tabs.addTab(CommandTab(wifi.REGISTRY, probe, self.send_command, self.note),
                         "Wi-Fi")
        self.tabs.addTab(CommandTab(shortrange.REGISTRY, probe, self.send_command, self.note),
                         "Short range")
        self.tabs.addTab(FicrTab(probe, self.send_command, self.note), "FICR")

    # -- the funnel -------------------------------------------------------

    def send_command(self, line, reply, command=None):
        """The only path to the kit.

        Guards that must not be bypassed belong here. `init` resets every
        configuration parameter, and the natural order — configure, then init
        because init sounds like a first step — leaves a radio at defaults while
        the screen still shows the values that were typed.
        """
        if not line:
            return
        if command is not None and command.resets_config:
            answer = QMessageBox.warning(
                self, "init resets configuration",
                f"{line}\n\n"
                "init returns every configuration parameter to its default.\n"
                "Anything already configured is discarded. Configure after init.",
                QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Ok,
                QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Ok:
                self.note(f"cancelled: {line}")
                return
        self.note(f"> {line}")
        self._send_requested.emit(line, reply)

    # -- slots ------------------------------------------------------------

    @pyqtSlot(object, object)
    def _on_scanned(self, devices, probes):
        self.devices = devices or ()
        self.probes = probes or ()
        self.device_box.blockSignals(True)
        self.device_box.clear()
        for device in self.devices:
            self.device_box.addItem(device.label, userData=device)
        self.device_box.blockSignals(False)
        self.rescan_button.setEnabled(True)

        ready = next((p for p in self.probes if p.state is State.READY), None)
        self.probe = ready
        for probe in self.probes:
            self.note(probe.summary())
        self._build_tabs(ready)
        if ready is not None:
            self._set_status(f"{ready.port} ready")
            self._connect_requested.emit(ready.port)
            self.connect_button.setText("Disconnect")
        else:
            self._set_status("no shell found" if self.devices else "no kit")

    @pyqtSlot(object)
    def _on_exchange(self, exchange):
        for line in exchange.output:
            self.note(line)
        for entry in exchange.logs:
            self.note(f"{entry.module}: {entry.text}")
        if exchange.timed_out:
            self.note("(no reply)")

    @pyqtSlot(str)
    def _on_failed(self, message):
        self.note(f"error: {message}")
        self._set_status(message)

    @pyqtSlot(bool, str)
    def _on_flashed(self, good, message):
        self.note(("flashed: " if good else "flash failed: ") + message)
        self.flash_button.setEnabled(True)
        if good:
            # The kit resets, so what it presents may have changed. Re-probe
            # rather than assume the tabs still match the image.
            self._rescan()

    # -- ui actions -------------------------------------------------------

    def _device_changed(self, _index):
        device = self.device_box.currentData()
        if device is not None:
            self._set_status(device.label)

    def _rescan(self):
        self.rescan_button.setEnabled(False)
        self._set_status("scanning")
        self.note("scanning")
        self._scan_requested.emit()

    def _toggle_connection(self):
        if self.connect_button.text() == "Disconnect":
            self._disconnect_requested.emit()
            self.connect_button.setText("Connect")
            self._set_status("disconnected")
            self.note("disconnected")
            return
        port = self.probe.port if self.probe else None
        device = self.device_box.currentData()
        if port is None and device is not None:
            port = device.shell_port
        if port is None:
            self.note("nothing to connect to")
            return
        self._connect_requested.emit(port)
        self.connect_button.setText("Disconnect")

    def _flash(self):
        device = self.device_box.currentData()
        if device is None:
            self.note("no kit selected")
            return
        candidates = bundled_firmware()
        path = str(candidates[0]) if candidates else QFileDialog.getOpenFileName(
            self, "Select firmware", "", "Intel HEX (*.hex)")[0]
        if not path:
            return
        family = {"NRF54L_FAMILY": "nrf54l", "NRF54H_FAMILY": "nrf54h"}.get(device.family)
        answer = QMessageBox.question(
            self, "Program kit",
            f"Program {Path(path).name}\nonto {device.label}?",
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Ok,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Ok:
            return
        self.flash_button.setEnabled(False)
        self.note(f"programming {Path(path).name} onto {device.serial}")
        self._flash_requested.emit(path, device.serial, family or "")

    # -- helpers ----------------------------------------------------------

    def note(self, text):
        self.log.appendPlainText(text)

    def _set_status(self, text):
        colour = theme.STATE_COLOURS.get(
            self.probe.state.value if self.probe else "", theme.TEXT_MUTED)
        self.state_label.setText(text)
        self.state_label.setStyleSheet(f"color: {colour};")
        bits = [f"nrf_radio_gui {__version__}"]
        if self.probe is not None and self.probe.device is not None:
            bits.append(self.probe.device.label)
        if self.probe is not None:
            bits.append(f"{self.probe.port} {self.probe.state.value}")
        self.statusBar().showMessage(" · ".join(bits))

    def closeEvent(self, event):
        self._disconnect_requested.emit()
        self.thread.quit()
        self.thread.wait(2000)
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    theme.apply(app)
    window = MainWindow()
    window.show()
    return app.exec()
