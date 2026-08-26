#
# Copyright (c) 2026 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: Apache-2.0
#
"""Argument spec to widget, and the row geometry that keeps a row on screen.

One function per Arg type, dispatched by type. Adding a command never comes here;
adding an argument *kind* does.

> The row width budget is not decoration. A command with three arguments and
> generous widget minimums pushes its own Send button off the right edge, behind
> a horizontal scroll bar, where nobody finds it. `fits()` is checked in the
> tests against the widest command in the tables — `wifi_radio_test config_pta`,
> which takes three.

Widget choice follows one rule: never invent a bound. An `IntRange` with both
bounds known becomes a spin box, because the range is real. One with an unknown
bound becomes a line edit validated against the spec, because a spin box has to
be given a ceiling and the only honest ceiling is "unknown". `tx_power` is the
case that matters — the published range is 0-24 and the device takes 30.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QWidget,
)

from nrf_radio_gui.commands.spec import (
    Choice,
    Flag,
    IntRange,
    Keyword,
    NumberSet,
    Text,
)

# Derived from the 1000 px window in app.py. Keep them in step.
WINDOW_W = 1000
# The longest command name, `set_channel_sequence_hopping_mode`, measures 216 px
# in the application font. At 170 the label silently clipped
# `start_duty_cycle_modulated_tx` to `start_duty_cycle_modulated`, which reads as
# a different command. A clipped command name is worse than a narrow field.
LABEL_W = 232
# Every argument widget is exactly this wide, so the column lines up. Trimmed
# from 220 so a three-argument row still fits once LABEL_W grew.
ARG_MAX_W = 200
BUTTON_W = 90
SPACING = 6
MARGINS = 24
# Reserve the vertical scroll bar's width so a full command list does not push
# rows sideways once it appears.
SCROLLBAR_W = 12

# The widest command in any table takes three arguments (wifi_radio_test
# config_pta). Sized for that, with the budget asserted in the tests.
MAX_ARGS = 3


def row_width(count):
    """Width a row needs for `count` argument widgets at their maximum."""
    widgets = 2 + count           # label, args, button
    return (LABEL_W + count * ARG_MAX_W + BUTTON_W
            + SPACING * (widgets - 1) + MARGINS + SCROLLBAR_W)


def budget():
    return WINDOW_W


def fits(count):
    return row_width(count) <= budget()


def _combo(pairs, tip=""):
    """Combo box over (value, label) pairs. The value goes on the wire."""
    box = QComboBox()
    for value, label in pairs:
        box.addItem(f"{value} - {label}", userData=str(value))
    # Fixed, not a range: each combo would otherwise size to its own longest
    # item and the argument column would come out ragged.
    box.setFixedWidth(ARG_MAX_W)
    if tip:
        box.setToolTip(tip)
    return box


def _line(text="", tip=""):
    edit = QLineEdit(text)
    edit.setFixedWidth(ARG_MAX_W)
    if tip:
        edit.setToolTip(tip)
    return edit


def widget_for(arg):
    """Build the control for one argument."""
    tip = " ".join(p for p in (arg.help, getattr(arg, "note", "")) if p)

    if isinstance(arg, Flag):
        return _combo(arg.labels(), tip)

    if isinstance(arg, (Choice, Keyword)):
        return _combo(arg.labels(), tip)

    if isinstance(arg, NumberSet):
        box = QComboBox()
        if arg.sentinel is not None:
            # sentinel_help already names the value, e.g. "-1 leaves legacy rate
            # unused". Prefixing the sentinel again gave "-1 - -1 leaves ...".
            label = arg.sentinel_help or f"{arg.sentinel} - unused"
            box.addItem(label, userData=arg.sentinel)
        for value in arg.values:
            box.addItem(str(value), userData=str(value))
        box.setFixedWidth(ARG_MAX_W)
        if tip:
            box.setToolTip(tip)
        return box

    if isinstance(arg, IntRange):
        if arg.lo is not None and arg.hi is not None:
            spin = QSpinBox()
            spin.setRange(arg.lo, arg.hi)
            if arg.default is not None:
                spin.setValue(arg.default)
            if arg.unit:
                spin.setSuffix(f" {arg.unit}")
            spin.setFixedWidth(ARG_MAX_W)
            if tip:
                spin.setToolTip(tip)
            return spin
        # An open bound cannot be given to a spin box without inventing one.
        start = "" if arg.default is None else str(arg.default)
        return _line(start, tip or "No documented bound; the shell decides")

    if isinstance(arg, Text):
        return _line("", tip)

    raise TypeError(f"no widget for {type(arg).__name__}")


def value_of(widget):
    """The string this control contributes to the command line."""
    if isinstance(widget, QComboBox):
        data = widget.currentData()
        return data if data is not None else widget.currentText()
    if isinstance(widget, QSpinBox):
        return str(widget.value())
    if isinstance(widget, QLineEdit):
        return widget.text().strip()
    raise TypeError(f"no value for {type(widget).__name__}")


def mark(widget, invalid):
    """Flag a control as rejected, so theme.py can colour its border."""
    widget.setProperty("state", "invalid" if invalid else "")
    # A dynamic property change needs the style re-evaluated to take effect.
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class CommandRow(QWidget):
    """One command: name, its arguments, and the button that sends it."""

    def __init__(self, command, prefix, on_send, parent=None):
        super().__init__(parent)
        self.command = command
        self.prefix = prefix
        self._on_send = on_send

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(SPACING)

        name = QLabel(command.name)
        name.setMinimumWidth(LABEL_W)
        name.setMaximumWidth(LABEL_W)
        name.setToolTip(command.help or command.name)
        layout.addWidget(name)

        self.widgets = []
        for arg in command.args:
            control = widget_for(arg)
            self.widgets.append(control)
            layout.addWidget(control)

        # Zero-argument commands would otherwise leave the button floating in the
        # middle of the row, out of line with every other row's button.
        layout.addStretch(1)

        self.button = QPushButton("Write OTP" if command.permanent else "Send")
        self.button.setProperty("role", "danger" if command.permanent else "primary")
        self.button.setMinimumWidth(BUTTON_W)
        self.button.clicked.connect(self._send)
        layout.addWidget(self.button)

    def values(self):
        return tuple(value_of(w) for w in self.widgets)

    def errors(self):
        return self.command.errors(self.values())

    def line(self):
        return self.command.render(self.prefix, self.values())

    def _send(self):
        """Validate, mark up anything rejected, then hand the row to the owner.

        The row passes itself rather than just the rendered line, so the owner
        never has to work out which row a click came from.
        """
        found = self.errors()
        for arg, control in zip(self.command.args, self.widgets):
            mark(control, arg.name in found)
        if found:
            self._on_send(self, None, found)
            return
        self._on_send(self, self.line(), {})
