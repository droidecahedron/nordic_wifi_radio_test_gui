#
# Copyright (c) 2026 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: Apache-2.0
#
"""Window and wiring.

Scaffolding only at this commit: the window opens and reports the version. Command
tabs, transport, and discovery land in later commits.
"""

import sys

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from nrf_radio_gui import __version__, theme

# tests/test_factory.py derives a row width budget from this, so widen it there too.
WINDOW_W = 1000
WINDOW_H = 720


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("nRF Radio Test")
        self.resize(WINDOW_W, WINDOW_H)

        central = QWidget()
        layout = QVBoxLayout(central)
        placeholder = QLabel("No kit connected.")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(placeholder)
        self.setCentralWidget(central)

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage(f"nrf_radio_gui {__version__}")


def main():
    app = QApplication(sys.argv)
    theme.apply(app)
    window = MainWindow()
    window.show()
    return app.exec()
