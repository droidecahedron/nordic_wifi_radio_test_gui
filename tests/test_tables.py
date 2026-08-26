#
# Copyright (c) 2026 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: Apache-2.0
#
"""The three command tables.

Counts are pinned to what NCS v3.4.0 declares. If an SDK bump changes a table,
these fail and the number in the docs gets updated deliberately rather than
drifting.
"""

import unittest

from nrf_radio_gui.commands import ficr, shortrange, wifi
from nrf_radio_gui.commands.spec import IntRange, Reply, Text

# NCS v3.4.0. wifi_radio_test declares init twice, once per CONFIG_NRF71_RADIO_TEST
# branch, so 56 SHELL_CMD_ARG rows cover 55 distinct names.
WIFI_NAMES = 55
SHORTRANGE_NAMES = 23
FICR_NAMES = 7

# What an nRF54LM20 DK running single_domain actually presents, measured on
# SN 1051810810. See docs/block0_findings.md.
WIFI_ON_NRF70 = 43
SHORTRANGE_ON_LM20 = 20

# Gates absent from a plain nRF70 single_domain build.
ABSENT_GATES = (
    "CONFIG_NRF71_RADIO_TEST",
    "CONFIG_NRF70_SR_COEX || CONFIG_NRF71_SR_COEX",
    "CONFIG_NRF70_SR_COEX_RF_SWITCH || CONFIG_NRF71_SR_COEX_RF_SWITCH",
)

ALL = ((wifi, WIFI_NAMES), (shortrange, SHORTRANGE_NAMES), (ficr, FICR_NAMES))


class TestTables(unittest.TestCase):
    def test_row_counts_match_the_sdk(self):
        for module, expected in ALL:
            with self.subTest(module.PREFIX or "root"):
                self.assertEqual(len(module.COMMANDS), expected)

    def test_no_duplicate_names(self):
        for module, _ in ALL:
            names = [c.name for c in module.COMMANDS]
            with self.subTest(module.PREFIX or "root"):
                self.assertCountEqual(names, set(names))

    def test_short_range_is_not_namespaced(self):
        """CMakeLists globs radio_cmd.c into the app, so these land at the root."""
        self.assertEqual(shortrange.PREFIX, "")
        self.assertEqual(wifi.PREFIX, "wifi_radio_test")
        self.assertEqual(ficr.PREFIX, "wifi_radio_ficr_prog")

    def test_every_command_has_help(self):
        for module, _ in ALL:
            for command in module.COMMANDS:
                with self.subTest(f"{module.PREFIX}:{command.name}"):
                    self.assertTrue(command.help.strip())

    def test_gating_predicts_the_measured_image(self):
        present = [c for c in wifi.COMMANDS if c.gate not in ABSENT_GATES]
        self.assertEqual(len(present), WIFI_ON_NRF70)
        present = [c for c in shortrange.COMMANDS if not c.gate]
        self.assertEqual(len(present), SHORTRANGE_ON_LM20)

    def test_nrf71_only_commands_are_gated(self):
        for name in ("rx_bss_color", "tx_dcm", "tx_fec_coding", "tx_106_tone"):
            with self.subTest(name):
                self.assertEqual(wifi.REGISTRY.by_name(name).gate,
                                 "CONFIG_NRF71_RADIO_TEST")

    def test_commands_absent_only_on_nrf71_use_a_negated_gate(self):
        for name in ("set_ant_gain", "set_edge_bo"):
            with self.subTest(name):
                self.assertEqual(wifi.REGISTRY.by_name(name).gate,
                                 "!CONFIG_NRF71_RADIO_TEST")


class TestMeasuredFacts(unittest.TestCase):
    """Table entries that encode something learned on hardware."""

    def test_tx_power_has_no_ceiling(self):
        """Published range is 0-24; the device accepts and reports 30."""
        arg = wifi.REGISTRY.by_name("tx_power").args[0]
        self.assertIsInstance(arg, IntRange)
        self.assertIsNone(arg.hi)
        self.assertIsNone(arg.validate("30"))

    def test_reg_domain_stays_a_string(self):
        self.assertIsInstance(wifi.REGISTRY.by_name("reg_domain").args[0], Text)

    def test_tx_pkt_rate_keeps_the_rate_the_parser_rejects(self):
        """The help advertises 5.5 and the shell refuses it. Keep it visible."""
        self.assertIn("5.5", wifi.REGISTRY.by_name("tx_pkt_rate").args[0].values)

    def test_deferred_commands_are_marked(self):
        for name in ("get_temperature", "get_voltage", "get_rf_rssi",
                     "compute_optimal_xo_val"):
            with self.subTest(name):
                self.assertIs(wifi.REGISTRY.by_name(name).reply, Reply.DEFERRED)

    def test_get_stats_is_synchronous(self):
        """It returns the five counters as output, not as a log line."""
        self.assertIs(wifi.REGISTRY.by_name("get_stats").reply, Reply.SYNC)
        self.assertEqual(len(wifi.STATS), 5)
        self.assertEqual(wifi.STATS[0], "rssi_avg")

    def test_init_is_flagged_as_destroying_configuration(self):
        self.assertTrue(wifi.REGISTRY.by_name("init").resets_config)

    def test_short_range_bounds_come_from_the_checks_not_the_help(self):
        """radio_cmd.c rejects channel > 80; help for time says 1-99, check says 0."""
        self.assertEqual(shortrange.REGISTRY.by_name("start_channel").args[0].hi, 80)
        self.assertEqual(shortrange.TIME_ON_CHANNEL, (0, 99))

    def test_output_power_table_is_the_source_superset(self):
        """33 declared in radio_cmd.c; nRF54LM20 presents 28 of them."""
        keys = [k for k, _ in shortrange.OUTPUT_POWER]
        self.assertEqual(len(keys), 33)
        for absent in ("pos10dBm", "pos9dBm", "neg30dBm", "neg70dBm", "neg100dBm"):
            with self.subTest(absent):
                self.assertIn(absent, keys)
        self.assertEqual(keys[0], "pos10dBm")
        self.assertEqual(keys[-1], "neg100dBm")

    def test_data_rates_are_the_source_superset(self):
        keys = [k for k, _ in shortrange.DATA_RATES]
        self.assertEqual(len(keys), 12)
        for absent in ("nrf_250Kbit", "nrf_4Mbit0_5", "nrf_4Mbit0_25"):
            with self.subTest(absent):
                self.assertIn(absent, keys)


class TestFicrSafety(unittest.TestCase):
    def test_exactly_three_permanent_commands(self):
        permanent = [c.name for c in ficr.COMMANDS if c.permanent]
        self.assertEqual(sorted(permanent), ["otp_write_params",
                                             "otp_write_retrim_params",
                                             "otp_write_retrim_version"])

    def test_reads_are_not_marked_permanent(self):
        for name in ("otp_get_status", "otp_read_params",
                     "otp_read_retrim_version", "otp_read_retrim_params"):
            with self.subTest(name):
                self.assertFalse(ficr.REGISTRY.by_name(name).permanent)

    def test_otp_addresses_are_byte_addresses(self):
        """The shell does `field >>= 2`; rpu_if.h lists word offsets."""
        expected = {"REGION_PROTECT": 64, "QSPI_KEY": 68, "MAC0_ADDR": 72,
                    "MAC1_ADDR": 74, "CALIB_XO": 76, "REGION_DEFAULTS": 85}
        self.assertEqual(len(ficr.OTP_TARGETS), len(expected))
        for target in ficr.OTP_TARGETS:
            with self.subTest(target.name):
                self.assertEqual(target.word, expected[target.name])
                self.assertEqual(target.address, target.word * 4)

    def test_calib_xo_lands_at_0x130(self):
        self.assertEqual(ficr.target_by_name("CALIB_XO").hex_address, "0x130")

    def test_data_word_counts_come_from_the_argc_checks(self):
        expected = {"REGION_PROTECT": 1, "QSPI_KEY": 4, "MAC0_ADDR": 2,
                    "MAC1_ADDR": 2, "CALIB_XO": 1, "REGION_DEFAULTS": 1}
        for target in ficr.OTP_TARGETS:
            with self.subTest(target.name):
                self.assertEqual(target.words, expected[target.name])


if __name__ == "__main__":
    unittest.main()
