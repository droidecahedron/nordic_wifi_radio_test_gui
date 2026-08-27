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
from PyQt6.QtGui import QFont, QFontMetrics
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QWidget,
)

from nrf_radio_gui.commands.docs import DEFAULTS as DOC_DEFAULTS
from nrf_radio_gui.commands.docs import RANGES as DOC_RANGES
from nrf_radio_gui.commands.docs import describe
from nrf_radio_gui.commands.spec import (
    Choice,
    Flag,
    IntRange,
    Keyword,
    NumberSet,
    Text,
)

# Preferred window width. A large UI font can need more, so window_width() is
# what app.py opens at and what the budget is measured against.
WINDOW_W = 1000
# The label column is measured, not fixed. A hard-coded width is a measurement of
# one platform's font: 232 px fits the longest name in Sans Serif 9pt here, and
# clips it in DejaVu Sans 10pt at 249 px or Noto Sans 10pt at 233 px. A clipped
# command name reads as a different command, which is the worst failure this
# layout has.
LABEL_MIN_W = 170
LABEL_PAD = 16
# Argument widgets share one width so the column aligns. The ceiling is a
# preference; the floor is a requirement, and what actually gets used is whatever
# the label leaves over.
ARG_MIN_W = 110
ARG_MAX_W = 200
# Button width comes from Qt, not from font metrics plus a guess. At a fixed 90 px
# the bold "Write OTP" clipped to "Nrite OTP": the stylesheet adds 14 px of
# padding each side and a border, which a metrics-only estimate misses.
BUTTON_MIN_W = 90
BUTTON_LABELS = ("Send", "Write OTP")
# The description takes what is left after everything else and elides to fit, so
# it is deliberately absent from the budget. Squeezing arguments to make room for
# it left `nrf_1Mbit - 1 M` in a combo box.
DESC_MIN_W = 0
SPACING = 6
MARGINS = 24
# Reserve the vertical scroll bar's width so a full command list does not push
# rows sideways once it appears.
SCROLLBAR_W = 12

# The widest command in any table takes three arguments (wifi_radio_test
# config_pta). Sized for that, with the budget asserted in the tests.
MAX_ARGS = 3


_label_w = None
_button_w = None


def _command_names():
    """Every command name in every table, for measuring the label column."""
    from nrf_radio_gui.commands import ficr, shortrange, wifi

    return [c.name for m in (wifi, shortrange, ficr) for c in m.COMMANDS]


def label_width():
    """Width the longest command name needs in the font actually in use.

    Cached: it depends on the application font, which is set once at startup.
    """
    global _label_w
    if _label_w is None:
        metrics = QFontMetrics(QLabel().font())
        widest = max(metrics.horizontalAdvance(n) for n in _command_names())
        _label_w = max(LABEL_MIN_W, widest + LABEL_PAD)
    return _label_w


def button_width():
    """Width the widest button label needs, asking Qt for the real hint.

    sizeHint() accounts for the stylesheet's padding, border and font weight.
    Computing it from font metrics plus a padding constant got it wrong.
    """
    global _button_w
    if _button_w is None:
        widest = BUTTON_MIN_W
        for text in BUTTON_LABELS:
            for role in ("primary", "danger"):
                probe = QPushButton(text)
                probe.setProperty("role", role)
                probe.ensurePolished()
                widest = max(widest, probe.sizeHint().width())
        _button_w = widest
    return _button_w


def _fixed(count):
    """Everything in a row that is not an argument widget.

    Widgets are the label, `count` arguments, the button and the description, so
    the gaps between them number one fewer than the widgets. The description
    contributes no width of its own; it lives on whatever is left.
    """
    widgets = 3 + count
    return (label_width() + button_width() + SPACING * (widgets - 1)
            + MARGINS + SCROLLBAR_W)


def required_width(count=None):
    """Narrowest window that still fits a row without squeezing its arguments.

    A 14pt UI font measured the longest command name at 666 px on a Windows
    runner, which leaves 56 px per argument in a 1000 px window. Returning the
    floor anyway would overflow the row and hide the Send button behind a
    horizontal scroll bar, which is the fault the budget exists to prevent.
    """
    count = MAX_ARGS if count is None else max(1, count)
    return _fixed(count) + count * ARG_MIN_W


def window_width():
    """Width to open at: the preferred one, or wider when the font demands it."""
    return max(WINDOW_W, required_width())


def arg_width(count=None):
    """Width for each argument widget, given what the label left over."""
    count = MAX_ARGS if count is None else max(1, count)
    spare = (window_width() - _fixed(count)) // count
    return max(ARG_MIN_W, min(ARG_MAX_W, spare))


def row_width(count):
    """Width a row needs for `count` argument widgets."""
    return _fixed(count) + count * arg_width()


def budget():
    return window_width()


def fits(count):
    return row_width(count) <= budget()


def _combo(pairs, tip=""):
    """Combo box over (value, label) pairs. The value goes on the wire."""
    box = QComboBox()
    for value, label in pairs:
        box.addItem(f"{value} - {label}", userData=str(value))
    # Fixed, not a range: each combo would otherwise size to its own longest
    # item and the argument column would come out ragged.
    box.setFixedWidth(arg_width())
    if tip:
        box.setToolTip(tip)
    return box


def _line(text="", tip=""):
    edit = QLineEdit(text)
    edit.setFixedWidth(arg_width())
    if tip:
        edit.setToolTip(tip)
    return edit


def describe_arg(arg, command=None):
    """Tooltip for one argument: what it accepts, and what it defaults to.

    A dropdown already shows its whole set, so this matters for the typed and
    stepped controls where the bounds are otherwise invisible. `set_xo_val`
    accepts 0-127 and nothing on screen said so.

    The default comes from the SDK doc table when it has one, since that is
    where a non-numeric answer lives: set_xo_val documents "42 or value
    programmed in OTP", which is the honest answer for a field seeded from OTP.
    """
    lines = []
    name = command.name if command is not None else ""
    lo = getattr(arg, "lo", None)
    hi = getattr(arg, "hi", None)
    unit = getattr(arg, "unit", "")
    values = getattr(arg, "values", None)

    if isinstance(arg, IntRange):
        if lo is not None and hi is not None:
            lines.append(f"Range: {lo} to {hi}{' ' + unit if unit else ''}")
        elif lo is not None:
            lines.append(f"Minimum: {lo}{' ' + unit if unit else ''}")
        elif hi is not None:
            lines.append(f"Maximum: {hi}{' ' + unit if unit else ''}")
        else:
            # tx_power is the case: the doc gives 0-24 while the kit boots at 30
            # and accepts it. Stating the documented range without clamping the
            # field keeps the doc visible and still lets the device's own value
            # be sent back.
            doc = DOC_RANGES.get(name)
            if doc:
                lines.append(f"Documented range: {doc[0]} to {doc[1]}"
                             f"{' ' + unit if unit else ''}, not enforced here")
            else:
                lines.append(f"No documented bound{'; ' + unit if unit else ''}")
        if arg.step and arg.step != 1:
            lines.append(f"Step: {arg.step}")
    elif values:
        lines.append("Accepts: " + ", ".join(str(v) for v in values))
        if getattr(arg, "sentinel", None) is not None:
            lines.append(f"Or {arg.sentinel}: {arg.sentinel_help or 'unused'}")
    elif isinstance(arg, Text):
        lines.append("Free text; the shell validates it")

    doc_default = DOC_DEFAULTS.get(command.name) if command is not None else None
    own_default = getattr(arg, "default", None)
    # Attribute it. The doc and the device disagree in places: tx_power is
    # documented as 0 and SN 1051810810 boots at 30, so a bare number would read
    # as fact.
    if doc_default is not None:
        lines.append(f"Default: {doc_default} (SDK docs)")
    elif own_default is not None:
        lines.append(f"Default: {own_default} (shell help)")

    for extra in (arg.help, getattr(arg, "note", "")):
        if extra:
            lines.append(extra)
    return "\n".join(lines)


def widget_for(arg, command=None):
    """Build the control for one argument."""
    tip = describe_arg(arg, command)

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
        box.setFixedWidth(arg_width())
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
            spin.setFixedWidth(arg_width())
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


class ElidedLabel(QLabel):
    """Label that shrinks to whatever is left and elides rather than pushing.

    A plain QLabel reports the full string as its size hint, which widened every
    row until the text ran off the right edge. This one asks for nothing and
    tails off with an ellipsis, keeping the full text in its tooltip.
    """

    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self._full = text
        self.setWordWrap(False)
        self.setToolTip(text)
        self.setSizePolicy(QSizePolicy.Policy.Ignored,
                           QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(0)

    def setText(self, text):
        self._full = text
        self.setToolTip(text)
        self._reflow()

    def text(self):
        return self._full

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reflow()

    def _reflow(self):
        metrics = QFontMetrics(self.font())
        super().setText(metrics.elidedText(self._full, Qt.TextElideMode.ElideRight,
                                           max(0, self.width())))


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
        name.setFixedWidth(label_width())
        name.setToolTip(command.help or command.name)
        layout.addWidget(name)

        self.widgets = []
        for arg in command.args:
            control = widget_for(arg, command)
            self.widgets.append(control)
            layout.addWidget(control)

        # The button sits next to the values it sends. Pinning it to the right
        # edge put it a long way from the field on a zero-argument row.
        self.button = QPushButton("Write OTP" if command.permanent else "Send")
        self.button.setProperty("role", "danger" if command.permanent else "primary")
        self.button.setFixedWidth(button_width())
        self.button.clicked.connect(self._send)
        layout.addWidget(self.button)

        # A warning outranks the description: an operator about to burn OTP does
        # not need to be told what the field means.
        text = command.warning or describe(command)
        self.detail = ElidedLabel(text)
        self.detail.setProperty("role", "danger" if command.warning else "caption")
        layout.addWidget(self.detail, 1)

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
