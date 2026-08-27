#
# Copyright (c) 2026 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: Apache-2.0
#
"""Short-range registry, registered at the shell root.

Rows come from `nrf/samples/peripheral/radio_test/src/radio_cmd.c` at NCS v3.4.0.
These are not namespaced: `single_domain/CMakeLists.txt` pulls that file into the
application via `${PERIP_RT_DIR}/src/radio_cmd.c`, so its `SHELL_CMD_REGISTER`
calls land at the shell root alongside `wifi_radio_test`. Hence PREFIX is "".

23 registrations in source. An nRF54LM20 DK running single_domain presents 20
`total_output_power`, `toggle_dcdc_state`, and `fem` are compiled out.

Bounds are from the argument checks in radio_cmd.c, not from the help strings,
because the two disagree in one place. See TIME_ON_CHANNEL below.
"""

from nrf_radio_gui.commands.spec import (
    Command,
    IntRange,
    Keyword,
    Registry,
    Reply,
    Text,
)

SOURCE = "nrf/samples/peripheral/radio_test/src/radio_cmd.c"
PREFIX = ""

_FEM = "CONFIG_FEM"
_AUTO_POWER = "CONFIG_RADIO_TEST_POWER_CONTROL_AUTOMATIC"
_DCDC = "TOGGLE_DCDC_HELP"

# Data rates. Each is gated on the SoC actually having the mode. nRF54LM20
# presents 9 of these 12: nrf_250Kbit, nrf_4Mbit0_5 and nrf_4Mbit0_25 are absent,
# while the two 4 Mbit BT-shaped modes are present.
DATA_RATES = (
    ("nrf_1Mbit", "1 Mbit/s Nordic proprietary"),
    ("nrf_2Mbit", "2 Mbit/s Nordic proprietary"),
    ("nrf_250Kbit", "250 kbit/s Nordic proprietary"),
    ("nrf_4Mbit0_5", "4 Mbit/s Nordic proprietary, BT 0.5"),
    ("nrf_4Mbit0_25", "4 Mbit/s Nordic proprietary, BT 0.25"),
    ("nrf_4Mbit_BT06", "4 Mbit/s Nordic proprietary, BT 0.6"),
    ("nrf_4Mbit_BT04", "4 Mbit/s Nordic proprietary, BT 0.4"),
    ("ble_1Mbit", "1 Mbit/s Bluetooth LE"),
    ("ble_2Mbit", "2 Mbit/s Bluetooth LE"),
    ("ble_lr125Kbit", "125 kbit/s Bluetooth LE coded"),
    ("ble_lr500Kbit", "500 kbit/s Bluetooth LE coded"),
    ("ieee802154_250Kbit", "250 kbit/s IEEE 802.15.4-2006"),
)

# Every step radio_cmd.c declares, each gated on its own RADIO_TXPOWER_TXPOWER_*
# define. Names are mechanical, so derive them rather than typing 33 lines.
# nRF54LM20 presents 28: +8 down to -46. Absent are +10, +9, -30, -70 and -100,
# so this part tops out at +8 dBm on the short-range radio.
_POWER_STEPS = (10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0,
                -1, -2, -3, -4, -5, -6, -7, -8, -9, -10,
                -12, -14, -16, -18, -20, -22, -28, -30, -40, -46, -70, -100)

OUTPUT_POWER = tuple(
    (f"{'pos' if dbm >= 0 else 'neg'}{abs(dbm)}dBm", f"{dbm} dBm")
    for dbm in _POWER_STEPS
)

TRANSMIT_PATTERNS = (
    ("pattern_random", "Random"),
    ("pattern_11110000", "11110000"),
    ("pattern_11001100", "11001100"),
)

HOPPING_MODES = (
    ("sequential", "Sequential, default order"),
    ("random", "Random, takes a seed"),
)

# radio_cmd.c rejects channel > 80. Offsets are MHz above 2400.
_CHANNEL_HI = 80
# The check is `time > 99` and the error reads "between 0 and 99 ms", but the
# help string says "between 1 and 99". Following the check.
TIME_ON_CHANNEL = (0, 99)

COMMANDS = (
    Command("start_channel",
            (IntRange("channel", lo=0, hi=_CHANNEL_HI, unit="MHz above 2400"),),
            "Sweep start channel, or the channel for a constant carrier"),
    Command("end_channel",
            (IntRange("channel", lo=0, hi=_CHANNEL_HI, unit="MHz above 2400"),),
            "Sweep end channel"),
    Command("time_on_channel",
            (IntRange("time", lo=TIME_ON_CHANNEL[0], hi=TIME_ON_CHANNEL[1], unit="ms",
                      help="Help says 1-99, the check allows 0"),),
            "Dwell time on each channel"),
    Command("cancel", (), "Cancel the sweep or the carrier"),

    Command("data_rate", (Keyword("rate", DATA_RATES),), "Set the data rate"),
    Command("output_power", (Keyword("power", OUTPUT_POWER),),
            "Set output power. With a FEM and automatic power control this sets "
            "total output power including FEM gain"),
    Command("total_output_power", (IntRange("power", unit="dBm"),),
            "Total output power including front-end module gain",
            gate=_AUTO_POWER),

    Command("transmit_pattern", (Keyword("pattern", TRANSMIT_PATTERNS),),
            "Set the transmission pattern"),

    Command("start_tx_carrier", (), "Start the TX carrier"),
    Command("start_tx_modulated_carrier", (), "Start the modulated TX carrier"),
    # Second argument is optional; radio_cmd.c accepts argc up to 3.
    Command("start_duty_cycle_modulated_tx",
            (IntRange("duty_cycle", lo=0, hi=90, unit="%",
                      help="Help says 01-90, the check allows 0"),
             IntRange("num_packets", lo=0)),
            "Start duty-cycled modulated TX", optional=1),

    Command("start_rx_sweep", (), "Start RX sweep"),
    Command("start_tx_sweep", (), "Start TX sweep"),
    Command("start_tx_sweep_with_sleep",
            (IntRange("tx_time", lo=0, unit="us"), IntRange("sleep_time", lo=0, unit="us")),
            "Start TX sweep with a sleep cycle"),
    Command("start_tx_sweep_with_sleep_modulated",
            (IntRange("tx_time", lo=0, unit="us"), IntRange("sleep_time", lo=0, unit="us")),
            "Start modulated TX sweep with a sleep cycle"),

    # Variadic, up to 80 channels. Left as free text; the shell validates.
    Command("set_channel_sequence",
            (Text("channels", help="Up to 80 channel numbers, space separated"),),
            "Set a custom TX channel sequence"),
    # `random` takes a seed, `sequential` takes nothing.
    Command("set_channel_sequence_hopping_mode",
            (Keyword("mode", HOPPING_MODES), IntRange("seed", lo=0)),
            "TX channel hopping mode", optional=1),
    Command("print_channel_sequence", (), "Print the custom TX channel sequence",
            reply=Reply.SYNC),

    Command("start_rx", (), "Start RX"),
    Command("print_rx", (), "Print the RX payload", reply=Reply.SYNC),
    Command("parameters_print", (), "Print current delay, channel and so on",
            reply=Reply.SYNC),

    Command("toggle_dcdc_state", (IntRange("state", lo=0, hi=1),),
            "Toggle the DC/DC converter state", gate=_DCDC),
    Command("fem", (Text("args", help="FEM subcommand and its arguments"),),
            "Front-end module parameters", gate=_FEM),
)

REGISTRY = Registry("Short range", PREFIX, SOURCE, COMMANDS)
