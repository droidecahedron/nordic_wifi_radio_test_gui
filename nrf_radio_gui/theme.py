#
# Copyright (c) 2026 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: Apache-2.0
#
"""Dark palette and stylesheet.

Colours are sampled, not invented. They come out of nRF Connect for Desktop
5.3.2 — `nrfconnect-5.3.2-x86_64.AppImage`, `resources/app.asar`, which declares
its own CSS custom properties:

    --primary: #00a9ce    --success: #4caf50    --danger:  #f44336
    --info:    #17a2b8    --warning: #ffc107    --dark:    #37474f
    --gray:    #546e7a    --light:   #cfd8dc

The greys are the Material blue-grey ramp, and the app uses all of it, #263238
through #eceff1. #00a9ce is by far the most frequent single colour in the bundle,
so it is the accent here too.

> `QLabel` needs `background: transparent` set explicitly. QLabel is a QWidget,
> so a background rule on QWidget paints every caption with the panel colour and
> command names end up looking like editable fields. This is the single most
> visible styling mistake available here, and it is invisible in a unit test —
> render the window offscreen and look at the PNG.
"""

# Material blue-grey, as used by nRF Connect for Desktop.
BG = "#263238"          # 900, window
SURFACE = "#2f3d44"     # between 900 and 800, panels
SURFACE_RAISED = "#37474f"  # 800, --dark, inputs and headers
BORDER = "#455a64"      # 700
BORDER_LIGHT = "#546e7a"  # 600, --gray
TEXT = "#eceff1"        # 50
TEXT_MUTED = "#b0bec5"  # 200
TEXT_FAINT = "#78909c"  # 400

ACCENT = "#00a9ce"      # --primary, Nordic blue
ACCENT_HOVER = "#1abbdd"
ACCENT_PRESSED = "#0090b0"

SUCCESS = "#4caf50"     # --success
WARNING = "#ffc107"     # --warning
DANGER = "#f44336"      # --danger
INFO = "#17a2b8"        # --info

MONO = "Menlo, Consolas, 'DejaVu Sans Mono', monospace"

# State colours for a discovery result. Keys are discovery.State values.
STATE_COLOURS = {
    "ready": SUCCESS,
    "no shell": WARNING,
    "unreachable": TEXT_FAINT,
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
    background: {SURFACE_RAISED};
    color: {TEXT};
    border: 1px solid {BORDER_LIGHT};
    border-radius: 4px;
    padding: 5px 14px;
    min-height: 20px;
}}
QPushButton:hover {{
    border-color: {ACCENT};
    color: {TEXT};
}}
QPushButton:pressed {{
    background: {BORDER};
}}
QPushButton:disabled {{
    color: {TEXT_FAINT};
    border-color: {BORDER};
    background: {SURFACE};
}}
QPushButton[role="primary"] {{
    background: {ACCENT};
    border-color: {ACCENT};
    color: {BG};
    font-weight: 600;
}}
QPushButton[role="primary"]:hover {{
    background: {ACCENT_HOVER};
    border-color: {ACCENT_HOVER};
}}
QPushButton[role="primary"]:pressed {{
    background: {ACCENT_PRESSED};
}}
/* Anything that writes OTP. Permanent, so it should not look like Send. */
QPushButton[role="danger"] {{
    background: {SURFACE_RAISED};
    border-color: {DANGER};
    color: {DANGER};
    font-weight: 600;
}}
QPushButton[role="danger"]:hover {{
    background: {DANGER};
    color: {TEXT};
}}
QPushButton[role="danger"]:disabled {{
    border-color: {BORDER};
    color: {TEXT_FAINT};
}}

QLineEdit, QSpinBox, QComboBox {{
    background: {SURFACE_RAISED};
    color: {TEXT};
    border: 1px solid {BORDER_LIGHT};
    border-radius: 4px;
    padding: 4px 6px;
    selection-background-color: {ACCENT};
    selection-color: {BG};
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{
    border-color: {ACCENT};
}}
QLineEdit[state="invalid"] {{
    border-color: {DANGER};
}}
QComboBox::drop-down {{
    border: none;
    width: 18px;
}}
QComboBox QAbstractItemView {{
    background: {SURFACE_RAISED};
    color: {TEXT};
    border: 1px solid {BORDER_LIGHT};
    selection-background-color: {ACCENT};
    selection-color: {BG};
}}
/* Qt draws no arrow glyph unless given an image, so a bare button is an
 * invisible sliver. Render them as two stacked blocks instead, wide enough to
 * hit, and let the keyboard and wheel do the real work. */
QSpinBox::up-button, QSpinBox::down-button {{
    background: {BORDER};
    border-left: 1px solid {BORDER_LIGHT};
    width: 16px;
}}
QSpinBox::up-button {{
    subcontrol-origin: border;
    subcontrol-position: top right;
    border-bottom: 1px solid {BORDER_LIGHT};
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
QSpinBox::up-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-bottom: 5px solid {TEXT_MUTED};
    width: 0;
    height: 0;
}}
QSpinBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {TEXT_MUTED};
    width: 0;
    height: 0;
}}

QPlainTextEdit, QTextEdit {{
    background: #1e282d;
    color: {TEXT_MUTED};
    border: 1px solid {BORDER};
    border-radius: 4px;
    font-family: {MONO};
    font-size: 12px;
    selection-background-color: {ACCENT};
    selection-color: {BG};
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
    background: {TEXT_FAINT};
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    height: 0;
    width: 0;
}}
QScrollBar::add-page, QScrollBar::sub-page {{
    background: transparent;
}}

QStatusBar {{
    background: {SURFACE_RAISED};
    color: {TEXT_MUTED};
    border-top: 1px solid {BORDER};
    min-height: 22px;
}}
QStatusBar::item {{
    border: none;
}}
/* showMessage() puts the text in a child QLabel, and the transparent-QLabel
 * rule above strips its colour along with its background. Give it one back or
 * the status bar renders empty. */
QStatusBar QLabel {{
    background: transparent;
    color: {TEXT_MUTED};
    padding-left: 6px;
}}

QToolTip {{
    background: {SURFACE_RAISED};
    color: {TEXT};
    border: 1px solid {ACCENT};
    padding: 4px;
}}

QSplitter::handle {{
    background: {BORDER};
}}
"""


def apply(app):
    """Apply the stylesheet to a QApplication."""
    app.setStyleSheet(stylesheet())
