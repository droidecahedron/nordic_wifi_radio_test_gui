#
# Copyright (c) 2026 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: Apache-2.0
#
"""`wifi_radio_test` registry.

Rows come from `nrf/samples/wifi/radio_test/multi_domain/src/nrf_wifi_radio_test_shell.c`
at NCS v3.4.0, `SHELL_STATIC_SUBCMD_SET_CREATE` at line 2733. Help strings are
shortened from that file's own text.

All 55 names are here, including the ones a given image compiles out, so the tool
also drives an nRF71 or a coex build. `gate` records the Kconfig condition;
whether a command actually exists is decided by probing the shell. An
nRF54LM20 DK with an nRF7002-EB II running the single_domain sample presents 43
of these — see docs/block0_findings.md.

Reply modes are measured, not assumed. See REPLY notes on the readback commands.
"""

from nrf_radio_gui.commands.spec import (
    Choice,
    Command,
    Flag,
    IntRange,
    NumberSet,
    Registry,
    Reply,
    Text,
)

SOURCE = "nrf/samples/wifi/radio_test/multi_domain/src/nrf_wifi_radio_test_shell.c"
PREFIX = "wifi_radio_test"

# Counters in a get_stats reply, in the order the shell prints them.
STATS = (
    "rssi_avg",
    "ofdm_crc32_pass_cnt",
    "ofdm_crc32_fail_cnt",
    "dsss_crc32_pass_cnt",
    "dsss_crc32_fail_cnt",
)

_NRF71 = "CONFIG_NRF71_RADIO_TEST"
_COEX = "CONFIG_NRF70_SR_COEX || CONFIG_NRF71_SR_COEX"
_COEX_SW = "CONFIG_NRF70_SR_COEX_RF_SWITCH || CONFIG_NRF71_SR_COEX_RF_SWITCH"

_ENABLE = ("Disable", "Enable")

COMMANDS = (
    Command("set_defaults", (), "Reset every configuration parameter to its default"),
    # PHY calibration toggles. Five separate switches rather than a bitmask.
    Command("phy_calib_rxdc", (Flag("rxdc", *_ENABLE),), "RX DC calibration"),
    Command("phy_calib_txdc", (Flag("txdc", *_ENABLE),), "TX DC calibration"),
    Command("phy_calib_txpow", (Flag("txpow", *_ENABLE),), "TX power calibration"),
    Command("phy_calib_rxiq", (Flag("rxiq", *_ENABLE),), "RX IQ calibration"),
    Command("phy_calib_txiq", (Flag("txiq", *_ENABLE),), "TX IQ calibration"),

    Command("he_ltf",
            (Choice("he_ltf", ((0, "1x HE LTF"), (1, "2x HE LTF"), (2, "4x HE LTF"))),),
            "HE long training field size"),
    Command("he_gi",
            (Choice("he_gi", ((0, "0.8 us"), (1, "1.6 us"), (2, "3.2 us"))),),
            "HE guard interval"),
    # VHT is absent when CONFIG_NRF70_2_4G_ONLY is set. Kept in the table; the
    # shell rejects it on a 2.4-only image.
    Command("tx_pkt_tput_mode",
            (Choice("mode", ((0, "Legacy"), (1, "HT"), (2, "VHT (not on 2.4G-only)"),
                             (3, "HE (SU)"), (4, "HE (ER SU)"), (5, "HE (TB)"))),),
            "Throughput mode"),
    Command("tx_pkt_sgi", (Flag("sgi", *_ENABLE),), "Short guard interval"),
    Command("tx_pkt_preamble",
            (Choice("preamble", ((0, "Long"), (1, "Short"), (2, "Mixed"))),),
            "Preamble type"),
    Command("tx_pkt_mcs",
            (IntRange("mcs", lo=-1, help="-1 leaves MCS unused"),),
            "MCS index, -1 to leave unused"),
    # The help advertises 5.5 and the parser refuses it, truncating to 5 and
    # answering "Invalid Legacy Rate value: 5". Left in so the disagreement shows.
    Command("tx_pkt_rate",
            (NumberSet("rate",
                       ("1", "2", "5.5", "11", "6", "9", "12", "18", "24", "36", "48", "54"),
                       sentinel="-1",
                       sentinel_help="-1 leaves legacy rate unused",
                       help="Mbps. 5.5 is advertised but rejected by the shell"),),
            "Legacy rate in Mbps, -1 to leave unused"),
    Command("tx_pkt_gap",
            (IntRange("gap", lo=200, hi=200000, default=200, unit="us"),),
            "Interval between TX packets"),
    Command("tx_pkt_num",
            (IntRange("num", lo=-1, help="-1 transmits indefinitely"),),
            "Packets to transmit, -1 for infinite"),
    Command("tx_pkt_len",
            (IntRange("len", lo=1, default=1400, unit="bytes"),),
            "Packet length"),
    # No ceiling on purpose. The published range is 0-24; SN 1051810810 boots at
    # 30, accepts a write of 30, and reads back 30.
    Command("tx_power",
            (IntRange("power", unit="dBm",
                      help="Published range is 0-24; hardware reports 30"),),
            "TX power", config_key="tx_power"),
    Command("ru_tone",
            (NumberSet("tone", ("26", "52", "106", "242")),),
            "Resource unit size"),
    Command("ru_index",
            (IntRange("index", lo=1, hi=9,
                      note="Ceiling follows ru_tone: 26->9, 52->4, 106->2, 242->1"),),
            "Resource unit location in the 20 MHz spectrum"),

    # init throws away every configuration parameter, so configure after it.
    # Takes a band as well when CONFIG_NRF71_RADIO_TEST is set.
    Command("init",
            (IntRange("channel", lo=1, help="Primary channel number"),),
            "Initialise the radio. Resets all configuration",
            resets_config=True),

    Command("tx", (Flag("tx", "Disable TX", "Enable TX"),), "TX on or off"),
    Command("rx", (Flag("rx", "Disable RX", "Enable RX"),), "RX on or off"),

    Command("sr_ant_switch_ctrl",
            (Flag("ant", "BLE antenna", "Shared Wi-Fi antenna"),),
            "Short-range antenna switch", gate=_COEX_SW),
    Command("config_pta",
            (Choice("band", ((0, "2.4 GHz"), (1, "5 GHz"))),
             Choice("antenna", ((0, "Shared"), (1, "Separate"))),
             Choice("protocol", ((0, "Thread"), (1, "Bluetooth LE"))),),
            "Configure the packet traffic arbiter", gate=_COEX),

    Command("rx_lna_gain",
            (Choice("lna", ((0, "24 dB"), (1, "18 dB"), (2, "12 dB"),
                            (3, "0 dB"), (4, "-12 dB"))),),
            "LNA gain"),
    # 5-bit field, 64 dB of range in 2 dB steps.
    Command("rx_bb_gain",
            (IntRange("bb", lo=0, hi=31, help="5-bit, 64 dB range in 2 dB steps"),),
            "Baseband gain"),
    Command("rx_capture_length",
            (IntRange("length", lo=0, hi=16384, unit="samples"),),
            "RX samples to capture"),
    Command("rx_capture_timeout",
            (IntRange("timeout", lo=0, hi=600, unit="s"),),
            "RX capture wait time"),
    Command("rx_cap",
            (Choice("cap", ((0, "ADC capture"), (1, "Filtered ADC capture"),
                            (2, "Dynamic packet capture"))),),
            "Start an RX capture"),

    Command("tx_tone_freq",
            (IntRange("offset", lo=-10, hi=10, unit="MHz",
                      help="Offset from centre frequency, 1 MHz resolution"),),
            "Tone frequency offset"),
    Command("tx_tone", (Flag("tone", *_ENABLE),), "Continuous tone on or off"),
    Command("dpd", (Flag("dpd", "Bypass DPD", "Enable DPD"),), "Digital pre-distortion"),

    # REPLY: measured deferred. Prompt returns at ~151 ms, value arrives ~1050 ms
    # as an <inf> wifi_nrf log line. Prompt-return is not end-of-reply.
    Command("get_temperature", (), "Read die temperature", reply=Reply.DEFERRED),
    Command("get_voltage", (), "Read battery voltage", reply=Reply.DEFERRED),
    Command("get_rf_rssi", (), "Read RF RSSI", reply=Reply.DEFERRED),

    Command("set_xo_val",
            (IntRange("xo", lo=0, hi=127),),
            "Set the crystal trim value", config_key="xo_val"),
    # REPLY: deferred, same shape as the getters above.
    Command("compute_optimal_xo_val", (), "Compute the optimal crystal trim",
            reply=Reply.DEFERRED),

    # REPLY: both synchronous, whole block lands before the prompt. get_stats is
    # ordinary command output rather than a log line.
    Command("show_config", (), "Show current configuration", reply=Reply.SYNC),
    Command("get_stats", (), "Show PHY statistics", reply=Reply.SYNC),

    Command("wlan_ant_switch_ctrl",
            (Flag("ant", "Separate", "Shared"),),
            "WLAN antenna switch", config_key="wlan_ant_switch_ctrl"),
    Command("tx_pkt_cw",
            (NumberSet("cw", ("0", "3", "7", "15", "31", "63", "127", "255",
                              "511", "1023")),),
            "Contention window"),
    # Country code, not a number. Reads back as 00 and must stay a string.
    Command("reg_domain",
            (Text("country", help="Two-character country code, e.g. 00"),),
            "Regulatory domain country code", config_key="reg_domain"),
    Command("bypass_reg_domain",
            (Flag("bypass", "Clamp to regulatory maximum", "Use configured TX power"),),
            "Bypass regulatory limits", config_key="bypass_reg_domain"),

    Command("set_ant_gain", (IntRange("gain", lo=0, hi=6, unit="dB"),),
            "Antenna gain", gate=f"!{_NRF71}"),
    Command("set_edge_bo", (IntRange("backoff", lo=0, hi=10, unit="dB"),),
            "Band-edge backoff", gate=f"!{_NRF71}"),

    # nRF71 only. Absent on the nRF70 images.
    Command("rx_bss_color", (IntRange("color", lo=1, hi=63),),
            "RX BSS colour", gate=_NRF71),
    Command("rx_station_id", (IntRange("id", lo=1, hi=2047),),
            "RX station ID", gate=_NRF71),
    Command("tx_dcm", (Flag("dcm", *_ENABLE),), "Dual carrier modulation", gate=_NRF71),
    Command("tx_doppler", (Flag("doppler", *_ENABLE),), "Doppler", gate=_NRF71),
    Command("tx_midample_periodicity",
            (NumberSet("periodicity", ("10", "20")),),
            "Midamble periodicity", gate=_NRF71),
    Command("tx_106_tone", (Flag("tone", *_ENABLE),), "106-tone RU", gate=_NRF71),
    Command("tx_legacy_length", (IntRange("length", lo=0, hi=4095),),
            "Legacy length field", gate=_NRF71),
    Command("tx_fec_padd_factor", (NumberSet("factor", ("1", "2", "3", "4")),),
            "FEC padding factor", gate=_NRF71),
    Command("tx_num_he_ltf",
            (Choice("num", ((0, "1 LTF"), (1, "2 LTF"), (2, "4 LTF"),
                            (3, "6 LTF"), (4, "8 LTF"))),),
            "Number of HE LTFs", gate=_NRF71),
    Command("tx_fec_coding",
            (Choice("coding", ((0, "BCC"), (1, "LDPC"))),),
            "TX FEC coding", gate=_NRF71),
)

REGISTRY = Registry("Wi-Fi radio test", PREFIX, SOURCE, COMMANDS)
