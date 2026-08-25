#
# Copyright (c) 2026 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: Apache-2.0
#
"""`wifi_radio_ficr_prog` registry — nRF7002 OTP.

Rows come from `nrf/samples/wifi/radio_test/multi_domain/src/nrf_wifi_radio_ficr_shell.c`
at NCS v3.4.0, `SHELL_STATIC_SUBCMD_SET_CREATE` at line 463. Field offsets come
from `modules/lib/nrf_wifi/hw_if/hal/inc/common/rpu_if.h`.

OTP is one-time programmable. A write cannot be undone, reversed, or rewritten.
Four of the seven commands only read; the other three are marked `permanent` and
must never be reachable without an explicit confirmation step.

> The address argument is a BYTE address. The handler does
> `field = strtoul(argv[1]); field >>= 2;` while rpu_if.h defines every offset as
> a WORD offset. Pass the word offset by mistake and you permanently program a
> field four times lower in the map. OTP_TARGETS below carries both numbers so
> nothing has to do that arithmetic at a call site.
"""

from dataclasses import dataclass

from nrf_radio_gui.commands.spec import (
    Command,
    IntRange,
    Registry,
    Reply,
    Text,
)

SOURCE = "nrf/samples/wifi/radio_test/multi_domain/src/nrf_wifi_radio_ficr_shell.c"
OFFSETS = "modules/lib/nrf_wifi/hw_if/hal/inc/common/rpu_if.h"
PREFIX = "wifi_radio_ficr_prog"


@dataclass(frozen=True)
class OtpTarget:
    """One writable OTP field.

    `word` is the offset as rpu_if.h defines it. `address` is what the shell
    wants, which is `word * 4`. `words` is how many data words the handler
    demands for this field, derived from its argc check.
    """

    name: str
    word: int
    words: int
    note: str = ""

    @property
    def address(self):
        return self.word * 4

    @property
    def hex_address(self):
        return f"0x{self.address:x}"


# Every field otp_write_params will accept. The handler rejects anything below
# REGION_PROTECT and anything in the retrim range PRODRETEST_PROGVERSION (86) to
# PRODRETEST_TRIM14 (101) — those go through the retrim commands instead.
OTP_TARGETS = (
    OtpTarget("REGION_PROTECT", 64, 1,
              "Writes all four consecutive REGION_PROTECT words at once"),
    OtpTarget("QSPI_KEY", 68, 4,
              "Writes all four consecutive QSPI key words at once"),
    OtpTarget("MAC0_ADDR", 72, 2,
              "Needs the driver initialised. Rejects all-zero, broadcast and "
              "multicast addresses. Second word is masked to 16 bits"),
    OtpTarget("MAC1_ADDR", 74, 2,
              "Same validation as MAC0_ADDR"),
    OtpTarget("CALIB_XO", 76, 1,
              "Crystal trim. Shows up in show_config as xo_val"),
    OtpTarget("REGION_DEFAULTS", 85, 1,
              "Bit flags marking which fields are programmed. Bit 0 QSPI_KEY, "
              "bit 1 MAC0, bit 2 MAC1, bit 3 CALIB_XO, clear meaning programmed"),
)

# Retrim writes address by index rather than by offset.
RETRIM_INDEX = (0, 14)

# Every write path first reads REGION_PROTECT and refuses unless the region is
# OTP_ENABLE_PATTERN or OTP_FRESH_FROM_FAB, reporting "USER Region is not
# Writeable". That is the last line of defence, not the first — do not rely on it.
WRITE_GUARD = "USER Region is not Writeable"

COMMANDS = (
    Command("otp_get_status", (), "Read OTP status flags", reply=Reply.SYNC),
    Command("otp_read_params", (),
            "Read the user region and which fields are programmed",
            reply=Reply.SYNC),
    Command("otp_read_retrim_version", (), "Read the retrim version",
            reply=Reply.SYNC),
    Command("otp_read_retrim_params", (), "Read the 15 retrim params",
            reply=Reply.SYNC),

    # PERMANENT. Argument count varies by target; see OTP_TARGETS.words. The
    # shell declares 1 mandatory argument and up to 16 optional, so arity cannot
    # be enforced here — the target decides it.
    Command("otp_write_params",
            (Text("address", help="Byte address, e.g. 0x130 for CALIB_XO"),
             Text("data", help="One to four 32-bit words, space separated")),
            "Write an OTP field. Permanent",
            reply=Reply.SYNC, permanent=True),
    Command("otp_write_retrim_version",
            (Text("version", help="32-bit value"),),
            "Write PRODRETEST.PROGVERSION. Permanent",
            reply=Reply.SYNC, permanent=True),
    Command("otp_write_retrim_params",
            (IntRange("index", lo=RETRIM_INDEX[0], hi=RETRIM_INDEX[1]),
             Text("data", help="32-bit value")),
            "Write one PRODRETEST.TRIM word. Permanent",
            reply=Reply.SYNC, permanent=True),
)

REGISTRY = Registry("FICR / OTP", PREFIX, SOURCE, COMMANDS)


def target_by_name(name):
    for target in OTP_TARGETS:
        if target.name == name:
            return target
    return None
