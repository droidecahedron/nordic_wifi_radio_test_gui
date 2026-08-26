#
# Copyright (c) 2026 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: Apache-2.0
#
"""FICR tab. Reads are ordinary; writes are permanent.

OTP cannot be rewritten, so every write goes through `confirm_permanent()` and
nothing else may reach `otp_write_params`, `otp_write_retrim_version`, or
`otp_write_retrim_params`. The confirmation asks for the target name typed out,
because an OK button is a reflex and typing `CALIB_XO` is not.

The reference table above the list exists because the shell takes a *byte*
address while `rpu_if.h` names every field by *word* offset. Passing the word
offset permanently programs a field four times lower in the map, so the addresses
are shown rather than left to be worked out.
"""

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

from nrf_radio_gui.commands import ficr
from nrf_radio_gui.widgets.command_tab import CommandTab


class ConfirmWrite(QDialog):
    """Type the target name to arm a permanent write."""

    def __init__(self, target_name, line, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Permanent write")
        self.target_name = target_name

        layout = QVBoxLayout(self)

        warning = QLabel("This writes one-time programmable memory.\n"
                         "It cannot be undone, reversed, or written again.")
        warning.setProperty("role", "danger")
        layout.addWidget(warning)

        command = QLabel(line)
        command.setProperty("role", "mono")
        command.setWordWrap(True)
        layout.addWidget(command)

        layout.addWidget(QLabel(f"Type {target_name} to continue:"))
        self.entry = QLineEdit()
        self.entry.textChanged.connect(self._recheck)
        layout.addWidget(self.entry)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Ok
        )
        self.ok = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.ok.setText("Write OTP")
        self.ok.setProperty("role", "danger")
        # Armed only by an exact match, so Enter on an empty field does nothing.
        self.ok.setEnabled(False)
        self.ok.setDefault(False)
        self.ok.setAutoDefault(False)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def _recheck(self, text):
        self.ok.setEnabled(text.strip() == self.target_name)


def confirm_permanent(target_name, line, parent=None):
    """True when the operator typed the target name. The only gate on a write."""
    dialog = ConfirmWrite(target_name, line, parent)
    return dialog.exec() == QDialog.DialogCode.Accepted


class FicrTab(CommandTab):
    def __init__(self, probe, send, notify=None, parent=None):
        super().__init__(ficr.REGISTRY, probe, send, notify, parent)

    def extra_groups(self):
        """Address reference, so nobody converts word offsets by hand."""
        box = QGroupBox("OTP write targets")
        layout = QVBoxLayout(box)

        note = QLabel("The shell takes a byte address. rpu_if.h lists word "
                      "offsets. Use the address column.")
        note.setProperty("role", "caption")
        note.setWordWrap(True)
        layout.addWidget(note)

        for target in ficr.OTP_TARGETS:
            line = QHBoxLayout()
            name = QLabel(target.name)
            name.setMinimumWidth(150)
            addr = QLabel(f"{target.hex_address}")
            addr.setProperty("role", "mono")
            addr.setMinimumWidth(70)
            words = QLabel(f"{target.words} word{'s' if target.words > 1 else ''}")
            words.setProperty("role", "caption")
            words.setMinimumWidth(70)
            line.addWidget(name)
            line.addWidget(addr)
            line.addWidget(words)
            line.addStretch(1)
            layout.addLayout(line)

        return (box,)

    def request(self, command, line):
        """Gate every permanent command. Reads fall through untouched."""
        if not command.permanent:
            super().request(command, line)
            return
        target = self._target_for(command, line)
        if not confirm_permanent(target, line, self):
            self._notify(f"cancelled: {line}")
            return
        super().request(command, line)

    @staticmethod
    def _target_for(command, line):
        """What the operator has to type.

        For otp_write_params the address identifies the field, so the field's own
        name is what gets typed. Anything unrecognised falls back to the command
        name, which still forces a deliberate act rather than a click.
        """
        parts = line.split()
        if command.name == "otp_write_params" and len(parts) > 2:
            try:
                address = int(parts[2], 0)
            except ValueError:
                return command.name
            for target in ficr.OTP_TARGETS:
                if target.address == address:
                    return target.name
        return command.name
