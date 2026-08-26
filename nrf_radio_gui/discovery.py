#
# Copyright (c) 2026 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: Apache-2.0
#
"""Find a kit, decide whether it is running the radio test, and ask it what it has.

No Qt. The GUI calls scan() on a worker thread.

Presence is per-image, never per-board. The same board can be built with or
without FEM, coex, or the FICR shell, so the only honest way to know what a kit
answers to is to ask it. An nRF54LM20 DK running single_domain presents 43 of the
55 wifi_radio_test names, 20 of the 23 short-range ones, and all 7 FICR ones.

> Only a READY probe may hide anything in the UI. A probe that could not open the
> port learned nothing about the image, and hiding tabs on that basis leaves
> somebody staring at an empty window with no way back. `Probe.may_hide` is the
> single place that decision is expressed.
"""

import re
from dataclasses import dataclass, field
from enum import Enum

from nrf_radio_gui import nrfutil
from nrf_radio_gui.commands import ficr, shortrange, wifi
from nrf_radio_gui.commands.spec import Reply
from nrf_radio_gui.transport import Transport

# Measured first reply was 100-101 ms, nine for nine, on a kit whose shell was
# already up. 1.5 s is roughly 15x that. It is a ceiling for deciding "nothing is
# there", not a target.
REPLY_TIMEOUT_S = 1.5

# What the shell says when a root command does not exist. A bad *subcommand* of a
# short-range parent says "Unknown argument:" instead, and a bad subcommand of
# wifi_radio_test dumps its whole help tree. Three wordings, all real.
NOT_FOUND = "command not found"
UNKNOWN_ARG = "Unknown argument:"

# `  set_defaults            : Reset configuration parameter to their default`
# Two leading spaces is what separates a subcommand from a wrapped continuation
# of the previous help string, which the shell prints at the left margin.
_SUBCOMMAND = re.compile(r"^  (\w+)\s+:", re.M)


class State(Enum):
    READY = "ready"              # shell answered and was enumerated
    NO_SHELL = "no shell"        # port opened, nothing answered
    UNREACHABLE = "unreachable"  # could not open the port at all
    ERROR = "error"


@dataclass
class Probe:
    """What one port turned out to be."""

    port: str
    state: State
    reply_ms: int = None
    detail: str = ""
    root: tuple = ()                       # root command names
    registries: dict = field(default_factory=dict)  # prefix -> subcommand names
    device: object = None                  # nrfutil.Device when known

    @property
    def may_hide(self):
        """Whether this probe is entitled to hide anything.

        Only a READY probe learned what the image contains. Everything else is a
        statement about the port, not about the firmware.
        """
        return self.state is State.READY

    def has(self, prefix, name):
        """Whether the image presents `name` in the registry at `prefix`."""
        if not self.may_hide:
            return True   # unknown, so show it rather than strand the operator
        return name in self.registries.get(prefix, ())

    def summary(self):
        if self.state is not State.READY:
            return f"{self.port}: {self.state.value}{' - ' + self.detail if self.detail else ''}"
        counts = ", ".join(
            f"{p or 'root'} {len(n)}" for p, n in sorted(self.registries.items())
        )
        return f"{self.port}: ready in {self.reply_ms} ms ({counts})"


# A registry exists if this command is present at the shell root. The short-range
# set is not namespaced, so it is proven by one of its own commands rather than by
# a prefix.
WITNESS = (
    (wifi.PREFIX, wifi.PREFIX),
    (ficr.PREFIX, ficr.PREFIX),
    (shortrange.PREFIX, "parameters_print"),
)


def subcommands(text):
    """Subcommand names from a Zephyr help listing."""
    return tuple(_SUBCOMMAND.findall(text))


def classify(exchange):
    """Decide whether a shell answered, from the reply to a bare newline."""
    if exchange is None or exchange.timed_out:
        return State.NO_SHELL
    return State.READY


def probe_port(port, opener=None):
    """Open `port`, decide what is on it, and enumerate it when there is a shell.

    Never raises for an unusable port; an unreachable port is a result, not an
    error, because a bench routinely has ports belonging to something else.
    """
    transport = Transport(port, opener=opener)
    try:
        transport.open()
    except Exception as err:  # pyserial raises several unrelated types
        return Probe(port=port, state=State.UNREACHABLE, detail=str(err))

    try:
        # A bare newline is enough to make an idle shell reprint its prompt.
        first = transport.send("", Reply.SYNC)
        state = classify(first)
        if state is not State.READY:
            return Probe(port=port, state=state, detail="no reply to a bare newline")

        root = subcommands("\n".join(transport.send("help", Reply.SYNC).output))
        registries = {}
        for prefix, witness in WITNESS:
            if witness not in root:
                continue
            if prefix:
                listing = transport.send(prefix, Reply.SYNC)
                registries[prefix] = subcommands("\n".join(listing.output))
            else:
                # Root-level commands are already in the help listing.
                registries[prefix] = tuple(
                    c.name for c in shortrange.COMMANDS if c.name in root
                )
        return Probe(port=port, state=State.READY, reply_ms=first.first_byte_ms,
                     root=tuple(root), registries=registries)
    except Exception as err:
        return Probe(port=port, state=State.ERROR, detail=str(err))
    finally:
        transport.close()


def candidate_ports(devices=None, serial=None):
    """Ports worth probing, best first.

    VCOM0 carried the shell on the nRF54LM20 DK and VCOM1 was silent, so VCOM0 is
    tried first — but VCOM1 is still offered, because that ordering is one
    board's habit rather than a rule.

    `serial` narrows to one kit. A bench with two DKs enumerates in whatever
    order nrfutil returns, so without it the first kit to answer wins — which is
    fine when only one is running the radio test and wrong the moment both are.
    """
    if devices is None:
        devices = nrfutil.list_devices()
    if serial:
        wanted = str(serial).lstrip("0")
        devices = [d for d in devices if d.serial.lstrip("0") == wanted]
    ordered = []
    for device in devices:
        for port in sorted(device.ports, key=lambda p: p.vcom):
            ordered.append((port.path, device))
    return tuple(ordered)


def scan(devices=None, opener=None, stop_at_first=True, serial=None):
    """Probe attached kits and return every Probe, READY ones first.

    With stop_at_first, probing halts once a shell is found. VCOM1 on a kit whose
    VCOM0 already answered is not worth the 1.5 s.

    Pass `serial` to pin the sweep to one kit. Probing a kit that is not the
    target costs 1.5 s per silent port and can leave a second VCOM reporting an
    access error, which reads as a fault when it is only a port nobody wanted.
    """
    results = []
    for port, device in candidate_ports(devices, serial=serial):
        probe = probe_port(port, opener=opener)
        probe.device = device
        results.append(probe)
        if stop_at_first and probe.state is State.READY:
            break
    results.sort(key=lambda p: (p.state is not State.READY, p.port))
    return tuple(results)
