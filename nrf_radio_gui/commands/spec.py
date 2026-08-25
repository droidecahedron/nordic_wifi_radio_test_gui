#
# Copyright (c) 2026 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: Apache-2.0
#
"""Argument types the command tables are built from.

Data only, no Qt, so the tables stay testable without a display. The widget
factory maps these onto controls; nothing here knows a widget exists.

Ranges and labels belong to whoever writes a table row, and must be copied from
the shell's own help text rather than from published documentation. The two
disagree: the docs give `tx_power` as 0-24 and an nRF54LM20 DK with an
nRF7002-EB II reports 30 from `show_config`. See docs/block0_findings.md.
"""

from dataclasses import dataclass, field
from enum import Enum


class Reply(Enum):
    """How an answer comes back, measured on hardware.

    The shell returns its prompt before a deferred value arrives, so a transport
    that treats prompt-return as end-of-reply reads nothing from DEFERRED
    commands. `get_temperature` returned the prompt at 151 ms and the value at
    1057 ms.
    """

    NONE = "none"          # setters; prompt comes back, nothing to parse
    SYNC = "sync"          # whole reply lands before the prompt
    DEFERRED = "deferred"  # value arrives later as a <inf> log line


class Arg:
    """Base for a single positional argument."""

    name: str
    help: str

    def validate(self, text):
        """Return an error string, or None when `text` is acceptable.

        Validation is advisory. The shell is the authority on what it accepts,
        and it rejects what a given image does not support.
        """
        raise NotImplementedError

    def format(self, text):
        """Render `text` as the shell wants it. Never widen or reinterpret."""
        return str(text)


@dataclass(frozen=True)
class Flag(Arg):
    """Two-state 0/1 argument, each state carrying the shell's own wording."""

    name: str
    off: str
    on: str
    help: str = ""

    def validate(self, text):
        return None if str(text) in ("0", "1") else "expected 0 or 1"

    def labels(self):
        return ((0, self.off), (1, self.on))


@dataclass(frozen=True)
class Choice(Arg):
    """Small labelled enum, e.g. he_gi 0/1/2 as 0.8/1.6/3.2 us.

    `values` is (number, label) so the label can carry units. Order follows the
    shell help, not numeric order, because that is the order an operator reads.
    """

    name: str
    values: tuple
    help: str = ""

    def validate(self, text):
        allowed = [str(v) for v, _ in self.values]
        if str(text) in allowed:
            return None
        return f"expected one of {', '.join(allowed)}"

    def labels(self):
        return self.values


@dataclass(frozen=True)
class IntRange(Arg):
    """Bounded integer.

    `lo`/`hi` of None mean the bound is genuinely unknown rather than infinite.
    Leave them None instead of inventing one; an invented ceiling silently
    blocks a value the device would have taken.
    """

    name: str
    lo: int = None
    hi: int = None
    step: int = 1
    default: int = None
    unit: str = ""
    help: str = ""
    # Some bounds depend on another argument, e.g. ru_index on ru_tone. Record
    # the wording rather than modelling the dependency.
    note: str = ""

    def validate(self, text):
        try:
            val = int(str(text), 10)
        except ValueError:
            return "expected an integer"
        if self.lo is not None and val < self.lo:
            return f"minimum is {self.lo}"
        if self.hi is not None and val > self.hi:
            return f"maximum is {self.hi}"
        return None


@dataclass(frozen=True)
class NumberSet(Arg):
    """Discrete allowed values that are not a contiguous range.

    Values stay strings so what an operator picked is what gets sent. Round-trip
    them through a float and 11 becomes 11.0, which the shell will not take.

    The set is what the shell's help lists, and that is not always what the shell
    accepts. tx_pkt_rate advertises 5.5 and refuses it — the parser truncates to
    5, then answers `Invalid Legacy Rate value: 5`. Keep the advertised value and
    let the device reject it. Dropping it hides a disagreement that a later SDK
    may fix.
    """

    name: str
    values: tuple
    sentinel: str = None
    sentinel_help: str = ""
    help: str = ""

    def validate(self, text):
        if self.sentinel is not None and str(text) == self.sentinel:
            return None
        if str(text) in self.values:
            return None
        return f"expected one of {', '.join(self.values)}"


@dataclass(frozen=True)
class Text(Arg):
    """Free string, passed through untouched.

    reg_domain is why this exists. It reads back as `00`, a country code. Parse
    it as an integer and it becomes `0`, which is a different value to send.
    """

    name: str
    help: str = ""

    def validate(self, text):
        return None if str(text) else "must not be empty"


@dataclass(frozen=True)
class Command:
    """One shell command and how to talk to it."""

    name: str
    args: tuple = ()
    help: str = ""
    reply: Reply = Reply.NONE
    # A parameter shown by show_config under a different key, e.g. set_xo_val is
    # reported as xo_val. Empty when the command has no readback.
    config_key: str = ""
    # True when running this discards configuration. `init` resets every
    # parameter, so configure after init, never before.
    resets_config: bool = False
    # True when the effect is permanent. OTP writes cannot be undone.
    permanent: bool = False

    def render(self, prefix, values=()):
        """Build the line to send. `prefix` is "" for the root registry."""
        parts = [f"{prefix} {self.name}".strip() if prefix else self.name]
        for arg, value in zip(self.args, values):
            parts.append(arg.format(value))
        return " ".join(parts)

    def errors(self, values=()):
        """Per-argument validation errors, keyed by argument name."""
        found = {}
        if len(values) != len(self.args):
            return {"": f"expected {len(self.args)} argument(s)"}
        for arg, value in zip(self.args, values):
            err = arg.validate(value)
            if err:
                found[arg.name] = err
        return found


@dataclass(frozen=True)
class Registry:
    """A shell command set.

    `prefix` is empty for the short-range commands. They are registered at the
    shell root because single_domain/CMakeLists.txt globs
    samples/peripheral/radio_test/src/radio_cmd.c into the application, so they
    are not namespaced the way wifi_radio_test and wifi_radio_ficr_prog are.
    """

    name: str
    prefix: str
    source: str
    commands: tuple = field(default_factory=tuple)

    def by_name(self, name):
        for cmd in self.commands:
            if cmd.name == name:
                return cmd
        return None
