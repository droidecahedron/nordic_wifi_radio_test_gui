#
# Copyright (c) 2026 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: Apache-2.0
#
"""Serial transport for the Zephyr shell.

No Qt. The GUI runs this on a worker thread; keeping it synchronous makes it
testable against a fake port with no hardware and no display.

Every timing constant below is a measurement from an nRF54LM20 DK running the
single_domain radio test, not a guess. See docs/block0_findings.md.

The awkward part is that a reply does not always end when the prompt comes back.
`get_temperature` returns the prompt at 151 ms and the value at 1057 ms as a
deferred log line, so a read-until-prompt transport reports success and no data
for every readback command. `send()` takes the expected Reply mode and keeps
listening when the answer is still in flight.
"""

import re
import time
from dataclasses import dataclass, field

from nrf_radio_gui.commands.spec import Reply

BAUD = 115200
PROMPT = "uart:~$"

# Measured first-byte latency was 50-101 ms across every command tried. A reply
# is treated as complete once the line has been quiet this long.
IDLE_S = 0.35
# Ceiling for a synchronous reply. `wifi_radio_test <bad subcommand>` dumps 4572
# bytes of help, which is the largest reply the shell produces.
SYNC_CAP_S = 8.0
# Deferred values landed at 1008-1058 ms. Roughly 2.4x margin on the slowest.
DEFERRED_CAP_S = 2.5
# The port needs a moment after opening or the first write is lost.
OPEN_SETTLE_S = 0.2
POLL_S = 0.05

_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
# A read can start or stop part-way through an escape sequence. A probe of a
# freshly reset kit came back starting `[m\r\n` — ESC consumed by the previous
# read — and containing a bare `\x1b[8`, the head of a `\x1b[8D` cursor move that
# the newline cut off. Neither matches _ANSI, so both need their own pass.
_ORPHAN = re.compile(r"\A\[[0-9;]*[A-Za-z]")
_PARTIAL = re.compile(r"\x1b\[?[0-9;]*\Z")
# [00:02:31.285,348] <inf> wifi_nrf: The temperature is = 30 degree celsius
_LOG = re.compile(
    r"\[(?P<stamp>\d\d:\d\d:\d\d\.\d+,\d+)\]\s+"
    r"<(?P<level>\w+)>\s+(?P<module>[\w_]+):\s*(?P<text>.*)"
)


@dataclass(frozen=True)
class LogLine:
    stamp: str
    level: str
    module: str
    text: str


@dataclass
class Exchange:
    """One command and everything that came back because of it."""

    sent: str
    output: tuple = ()          # command output, echo and prompt removed
    logs: tuple = ()            # deferred log lines, parsed
    first_byte_ms: int = None   # None when nothing answered
    elapsed_ms: int = 0
    raw: str = ""

    @property
    def timed_out(self):
        return self.first_byte_ms is None

    def text(self):
        """Everything a log pane should show, in arrival order."""
        return "\n".join(self.output + tuple(f"{l.module}: {l.text}" for l in self.logs))


def clean(raw):
    """Strip ANSI, normalise newlines. Prompt and echo are removed separately."""
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", "replace")
    return _ANSI.sub("", raw).replace("\r\n", "\n").replace("\r", "\n")


def split(raw, sent):
    """Separate command output from deferred log lines.

    The shell echoes what it was sent, so the echo is dropped when it matches.
    Comparing rather than dropping the first line unconditionally keeps output
    that arrives before the echo, which happens on a busy log backend.

    Leading whitespace is preserved. In a help listing the indentation is what
    separates a subcommand line from a wrapped continuation of the previous
    one's help text, and discovery relies on that to enumerate a registry.
    """
    output = []
    logs = []
    for line in clean(raw).split("\n"):
        line = _ORPHAN.sub("", line)
        line = _PARTIAL.sub("", line)
        # A prompt can be glued to the front of real content. Removing it leaves
        # the gap behind, so drop that too — but only on lines that had one.
        had_prompt = PROMPT in line
        while PROMPT in line:
            line = line.replace(PROMPT, "", 1)
        if had_prompt:
            line = line.lstrip()
        line = line.rstrip()
        if not line:
            continue
        found = _LOG.search(line)
        if found:
            logs.append(LogLine(**found.groupdict()))
            continue
        if line.strip() == sent.strip():
            continue
        output.append(line)
    return tuple(output), tuple(logs)


class Transport:
    """A shell on a serial port.

    `opener` exists so tests can pass a fake with read/write/close and never
    touch pyserial or a kit.
    """

    def __init__(self, port, baud=BAUD, opener=None):
        self.port = port
        self.baud = baud
        self._opener = opener
        self._ser = None
        # When the last write happened, and whether that command could still
        # produce a late reply. See _settle().
        self._last_write = 0.0
        self._maybe_pending = False

    def open(self):
        if self._ser is not None:
            return
        if self._opener is None:
            import serial  # imported here so the module loads without pyserial

            self._ser = serial.Serial(self.port, self.baud, timeout=POLL_S)
        else:
            self._ser = self._opener(self.port, self.baud, timeout=POLL_S)
        time.sleep(OPEN_SETTLE_S)
        self._drain()

    def close(self):
        if self._ser is not None:
            self._ser.close()
            self._ser = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *_):
        self.close()

    @property
    def is_open(self):
        return self._ser is not None

    def _drain(self):
        reset = getattr(self._ser, "reset_input_buffer", None)
        if reset:
            reset()
        else:
            self._ser.read(65536)

    def _settle(self):
        """Wait out a deferred reply that may still be in flight, and discard it.

        `reset_input_buffer` only drops bytes that have already arrived, so it
        cannot prevent a late value being attributed to the next command. Sending
        get_temperature without waiting for its answer and then asking for
        get_voltage puts the temperature in the voltage reply — measured, not
        theoretical.

        Only charged when the previous write is recent enough that something could
        still be coming. A person clicking buttons pays nothing.
        """
        if not self._maybe_pending:
            return
        remaining = DEFERRED_CAP_S - (time.monotonic() - self._last_write)
        if remaining <= 0:
            self._maybe_pending = False
            return
        deadline = time.monotonic() + remaining
        seen = 0.0
        while time.monotonic() < deadline:
            if self._ser.read(4096):
                seen = time.monotonic()
                continue
            # Silence is not evidence that nothing is coming: a deferred value
            # sits about 900 ms behind its prompt, far longer than IDLE_S. Only
            # stop early once something has arrived and then gone quiet.
            if seen and time.monotonic() - seen >= IDLE_S:
                break
        self._maybe_pending = False
        self._drain()

    def send(self, line, reply=Reply.NONE):
        """Send `line` and collect the answer according to `reply`.

        NONE and SYNC finish on an idle line after the prompt returns. DEFERRED
        keeps listening past the prompt until a log line arrives or
        DEFERRED_CAP_S elapses, because that is where the value is.
        """
        if self._ser is None:
            raise RuntimeError("transport is not open")

        self._settle()
        self._drain()
        self._ser.write(line.encode() + b"\r\n")
        self._last_write = time.monotonic()
        flush = getattr(self._ser, "flush", None)
        if flush:
            flush()

        deferred = reply is Reply.DEFERRED
        cap = DEFERRED_CAP_S if deferred else SYNC_CAP_S

        start = time.monotonic()
        first = None
        last = start
        chunks = []
        while True:
            now = time.monotonic()
            if now - start >= cap:
                break
            data = self._ser.read(4096)
            if data:
                if first is None:
                    first = time.monotonic() - start
                chunks.append(data)
                last = time.monotonic()
                continue
            if not chunks:
                continue
            if time.monotonic() - last < IDLE_S:
                continue
            # Line has gone quiet. For a deferred reply that only settles it once
            # the value has actually landed; before that, keep waiting.
            if not deferred:
                break
            _, logs = split(b"".join(chunks), line)
            if logs:
                break

        raw = b"".join(chunks)
        output, logs = split(raw, line)
        # Only a deferred command that did NOT produce its value leaves something
        # outstanding. Marking every setter and sync read as pending instead
        # charges each of them the full settle window, measured at 2.4 s.
        #
        # Residual hazard, deliberately accepted: sending one of the four deferred
        # commands with the wrong Reply mode abandons its value, which then lands
        # in the next command's reply. The command tables carry the right mode for
        # exactly this reason — drive send() from cmd.reply and it cannot happen.
        self._maybe_pending = deferred and not logs
        return Exchange(
            sent=line,
            output=output,
            logs=logs,
            first_byte_ms=None if first is None else round(first * 1000),
            elapsed_ms=round((time.monotonic() - start) * 1000),
            raw=clean(raw),
        )
