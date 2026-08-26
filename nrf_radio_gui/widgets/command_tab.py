#
# Copyright (c) 2026 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: Apache-2.0
#
"""One tab per registry, built from a command table.

The tab is generic. It reads a Registry, asks the probe what the image actually
has, and lays out a CommandRow for each surviving command. Subclasses override
`extra_groups()` to put something above the list and `request()` to change what
sending means — the FICR tab uses both.

There is a filter box rather than a hand-made taxonomy. `wifi_radio_test` has 55
rows and no grouping exists in the shell or the source to inherit, so any
categories here would be invented, and an invented grouping is worse than a
search box the moment someone disagrees with it.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from nrf_radio_gui.widgets.factory import CommandRow


class CommandTab(QWidget):
    """Rows for every command in `registry` that this image presents."""

    def __init__(self, registry, probe, send, notify=None, parent=None):
        """`send(line, reply, command)` reaches the kit. `notify(text)` does not."""
        super().__init__(parent)
        self.registry = registry
        self.probe = probe
        self._send = send
        self._notify = notify or (lambda text: None)
        self.rows = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(8)

        for widget in self.extra_groups():
            outer.addWidget(widget)

        header = QHBoxLayout()
        self.filter = QLineEdit()
        self.filter.setPlaceholderText("filter commands")
        self.filter.setClearButtonEnabled(True)
        self.filter.textChanged.connect(self._apply_filter)
        header.addWidget(self.filter, 1)

        self.count = QLabel()
        self.count.setProperty("role", "caption")
        header.addWidget(self.count)
        outer.addLayout(header)

        host = QWidget()
        self.list_layout = QVBoxLayout(host)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(0)

        for command in self.visible_commands():
            row = CommandRow(command, registry.prefix, self._row_sent)
            self.rows.append(row)
            self.list_layout.addWidget(row)
        self.list_layout.addStretch(1)

        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setWidget(host)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.addWidget(area, 1)

        self._update_count()

    # -- overridable ------------------------------------------------------

    def extra_groups(self):
        """Widgets to place above the command list. Empty by default."""
        return ()

    def request(self, command, line):
        """Send one command. Override to gate or transform it."""
        self._send(line, command.reply, command)

    # -- internals --------------------------------------------------------

    def visible_commands(self):
        """Commands this image presents.

        `Probe.has` answers True for anything unknown, so a kit that could not be
        probed shows every row rather than an empty tab.
        """
        return tuple(
            c for c in self.registry.commands
            if self.probe is None or self.probe.has(self.registry.prefix, c.name)
        )

    def _row_sent(self, row, line, errors):
        if line is None:
            self.rejected(row, errors)
            return
        self.request(row.command, line)

    def rejected(self, row, errors):
        """A row failed validation. Report it; nothing goes to the kit."""
        detail = "; ".join(f"{k or 'arguments'}: {v}" for k, v in errors.items())
        self._notify(f"{row.command.name}: {detail}")

    def _apply_filter(self, text):
        needle = text.strip().lower()
        for row in self.rows:
            row.setVisible(needle in row.command.name.lower() if needle else True)
        self._update_count()

    def _update_count(self):
        # isVisible() is False for every child until the window itself is shown,
        # which made the count read "0 shown" on startup. isHidden() is true only
        # for what the filter actually hid.
        shown = sum(1 for r in self.rows if not r.isHidden())
        total = len(self.registry.commands)
        present = len(self.rows)
        if shown != present:
            self.count.setText(f"{shown} shown · {present} of {total} on this image")
        else:
            self.count.setText(f"{present} of {total} on this image")
