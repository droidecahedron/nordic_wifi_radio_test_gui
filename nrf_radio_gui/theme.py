#
# Copyright (c) 2026 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: Apache-2.0
#
"""Palette and stylesheet, keyed to nRF Connect for Desktop.

Colours are sampled, not invented. They come out of nRF Connect for Desktop
5.3.2 — `nrfconnect-5.3.2-x86_64.AppImage`, `resources/app.asar`, which declares
its own CSS custom properties:

    --primary: #00a9ce    --success: #4caf50    --danger:  #f44336
    --info:    #17a2b8    --warning: #ffc107    --dark:    #37474f
    --gray:    #546e7a    --light:   #cfd8dc

The greys are the Material blue-grey ramp. `#00a9ce` is the most frequent single
colour in the bundle, so it is the accent here too.

This is a light theme because the app it borrows from is a light app. Counting
`background-color` uses in the same bundle, light surfaces outnumber dark ones
about two to one — `#cfd8dc` 15, `#ffffff` 5, `#eceff1` 4, against `#37474f` 9 and
`#263238` 3. An earlier version of this file built a dark theme from the same
values, which read as black chrome with dim grey controls and looked nothing like
the tool it sits next to.

> `QLabel` needs `background: transparent` set explicitly. QLabel is a QWidget,
> so a background rule on QWidget paints every caption with the panel colour and
> command names end up looking like input fields.

> `QStatusBar` needs its child QLabel given a colour back. `showMessage()` puts
> the text in one, and the transparent-QLabel rule above strips the colour along
> with the background, leaving the status bar blank.

Both of those are invisible to a unit test. Render the window offscreen and look
at the PNG after any change here.
"""

# Material blue-grey, light end, as nRF Connect for Desktop uses it.
BG = "#eceff1"              # 50, window
SURFACE = "#ffffff"         # panels and group boxes
SURFACE_RAISED = "#ffffff"  # inputs
SURFACE_SUNK = "#f7f9fa"    # log pane, read-only areas
BORDER = "#cfd8dc"          # 100, --light
BORDER_LIGHT = "#b0bec5"    # 200, stronger edge on controls
TEXT = "#263238"            # 900, body text
TEXT_MUTED = "#546e7a"      # 600, --gray
TEXT_FAINT = "#90a4ae"      # 300, disabled

ACCENT = "#00a9ce"          # --primary
ACCENT_HOVER = "#00bce4"
ACCENT_PRESSED = "#0089a8"
# Dark text on the accent, not white. #00a9ce against white is about 2.6:1, which
# fails AA; against #263238 it is roughly 5.2:1, which passes.
ON_ACCENT = "#0b2027"

SUCCESS = "#388e3c"         # --success darkened for contrast on white
WARNING = "#b26a00"         # --warning darkened; #ffc107 on white is unreadable
DANGER = "#d32f2f"          # --danger darkened
INFO = "#17a2b8"            # --info

MONO = "Menlo, Consolas, 'DejaVu Sans Mono', monospace"

# State colours for a discovery result. Keys are discovery.State values.
STATE_COLOURS = {
    "ready": SUCCESS,
    "no shell": WARNING,
    "unreachable": TEXT_MUTED,
    "error": DANGER,
}


def stylesheet():
    """Application-wide QSS."""
    return f"""
QWidget {{
    background: {BG};
    color: {TEXT};
    font-size: 13px;
}}

/* QLabel is a QWidget, so the rule above would paint every caption with the
 * panel colour and make command names read as input fields. */
QLabel {{
    background: transparent;
}}

QLabel[role="caption"] {{
    color: {TEXT_MUTED};
}}
QLabel[role="danger"] {{
    color: {DANGER};
    font-weight: 600;
}}
QLabel[role="mono"] {{
    font-family: {MONO};
    color: {TEXT_MUTED};
}}

QMainWindow, QDialog {{
    background: {BG};
}}

QGroupBox {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 6px;
    margin-top: 14px;
    padding: 10px 8px 8px 8px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
    color: {TEXT_MUTED};
    background: transparent;
}}

QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-radius: 6px;
    background: {SURFACE};
    top: -1px;
}}
QTabBar::tab {{
    background: {BG};
    color: {TEXT_MUTED};
    border: 1px solid {BORDER};
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 7px 16px;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background: {SURFACE};
    color: {TEXT};
    border-bottom: 2px solid {ACCENT};
}}
QTabBar::tab:hover:!selected {{
    color: {TEXT};
}}

QPushButton {{
    background: {SURFACE};
    color: {TEXT};
    border: 1px solid {BORDER_LIGHT};
    border-radius: 4px;
    padding: 5px 14px;
    min-height: 20px;
}}
QPushButton:hover {{
    border-color: {ACCENT};
    color: {ACCENT_PRESSED};
}}
QPushButton:pressed {{
    background: {BG};
}}
QPushButton:disabled {{
    color: {TEXT_FAINT};
    border-color: {BORDER};
    background: {BG};
}}
QPushButton[role="primary"] {{
    background: {ACCENT};
    border-color: {ACCENT_PRESSED};
    color: {ON_ACCENT};
    font-weight: 600;
}}
QPushButton[role="primary"]:hover {{
    background: {ACCENT_HOVER};
}}
QPushButton[role="primary"]:pressed {{
    background: {ACCENT_PRESSED};
    color: {SURFACE};
}}
QPushButton[role="primary"]:disabled {{
    background: {BORDER};
    border-color: {BORDER};
    color: {TEXT_FAINT};
}}
/* Anything that writes OTP. Permanent, so it must not look like Send. */
QPushButton[role="danger"] {{
    background: {SURFACE};
    border-color: {DANGER};
    color: {DANGER};
    font-weight: 600;
}}
QPushButton[role="danger"]:hover {{
    background: {DANGER};
    color: {SURFACE};
}}
QPushButton[role="danger"]:disabled {{
    border-color: {BORDER};
    color: {TEXT_FAINT};
    background: {BG};
}}

QLineEdit, QSpinBox, QComboBox {{
    background: {SURFACE_RAISED};
    color: {TEXT};
    border: 1px solid {BORDER_LIGHT};
    border-radius: 4px;
    padding: 4px 6px;
    selection-background-color: {ACCENT};
    selection-color: {ON_ACCENT};
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{
    border-color: {ACCENT};
}}
QLineEdit:disabled, QSpinBox:disabled, QComboBox:disabled {{
    background: {BG};
    color: {TEXT_FAINT};
}}
QLineEdit[state="invalid"] {{
    border-color: {DANGER};
    background: #fdf3f3;
}}
QComboBox::drop-down {{
    border: none;
    width: 18px;
}}
QComboBox QAbstractItemView {{
    background: {SURFACE};
    color: {TEXT};
    border: 1px solid {BORDER_LIGHT};
    selection-background-color: {ACCENT};
    selection-color: {ON_ACCENT};
}}

/* Qt draws no arrow glyph without an image, so a bare button is an invisible
 * sliver. Two stacked blocks, wide enough to hit. */
QSpinBox::up-button, QSpinBox::down-button {{
    background: {BG};
    border-left: 1px solid {BORDER};
    width: 16px;
}}
QSpinBox::up-button {{
    subcontrol-origin: border;
    subcontrol-position: top right;
    border-bottom: 1px solid {BORDER};
    border-top-right-radius: 3px;
}}
QSpinBox::down-button {{
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    border-bottom-right-radius: 3px;
}}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
    background: {ACCENT};
}}

QPlainTextEdit, QTextEdit {{
    background: {SURFACE_SUNK};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 4px;
    font-family: {MONO};
    font-size: 12px;
    selection-background-color: {ACCENT};
    selection-color: {ON_ACCENT};
}}

QScrollArea {{
    border: none;
    background: transparent;
}}
QScrollBar:vertical, QScrollBar:horizontal {{
    background: {BG};
    border: none;
    width: 10px;
    height: 10px;
}}
QScrollBar::handle {{
    background: {BORDER_LIGHT};
    border-radius: 5px;
    min-height: 24px;
    min-width: 24px;
}}
QScrollBar::handle:hover {{
    background: {TEXT_MUTED};
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    height: 0;
    width: 0;
}}
QScrollBar::add-page, QScrollBar::sub-page {{
    background: transparent;
}}

QStatusBar {{
    background: {SURFACE};
    color: {TEXT_MUTED};
    border-top: 1px solid {BORDER};
    min-height: 22px;
}}
QStatusBar::item {{
    border: none;
}}
/* showMessage() puts the text in a child QLabel, and the transparent-QLabel
 * rule above strips its colour along with its background. */
QStatusBar QLabel {{
    background: transparent;
    color: {TEXT_MUTED};
    padding-left: 6px;
}}

QToolTip {{
    background: {TEXT};
    color: {SURFACE};
    border: 1px solid {TEXT};
    padding: 4px;
}}

QSplitter::handle {{
    background: {BORDER};
}}
"""


def apply(app):
    """Apply the stylesheet to a QApplication."""
    app.setStyleSheet(stylesheet())
