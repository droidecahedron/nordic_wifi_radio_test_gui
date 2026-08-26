#
# Copyright (c) 2026 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: Apache-2.0
#
"""Argument types and command rendering."""

import unittest

from nrf_radio_gui.commands.spec import (
    Choice,
    Command,
    Flag,
    IntRange,
    Keyword,
    NumberSet,
    Registry,
    Reply,
    Text,
)


class TestArgs(unittest.TestCase):
    def test_flag_takes_only_zero_or_one(self):
        flag = Flag("tx", off="Disable TX", on="Enable TX")
        self.assertIsNone(flag.validate("0"))
        self.assertIsNone(flag.validate("1"))
        self.assertIsNotNone(flag.validate("2"))
        self.assertEqual(flag.labels(), ((0, "Disable TX"), (1, "Enable TX")))

    def test_choice_rejects_outside_the_set(self):
        gi = Choice("he_gi", ((0, "0.8 us"), (1, "1.6 us"), (2, "3.2 us")))
        self.assertIsNone(gi.validate("2"))
        self.assertIn("0, 1, 2", gi.validate("9"))

    def test_int_range_enforces_known_bounds(self):
        xo = IntRange("xo", lo=0, hi=127)
        self.assertIsNone(xo.validate("127"))
        self.assertIn("maximum is 127", xo.validate("128"))
        self.assertIn("minimum is 0", xo.validate("-1"))
        self.assertIn("integer", xo.validate("abc"))

    def test_unknown_bound_means_unknown_not_infinite(self):
        """tx_power: docs say 0-24, the device accepts and reports 30."""
        power = IntRange("power", unit="dBm")
        self.assertIsNone(power.validate("30"))
        self.assertIsNone(power.validate("-40"))
        self.assertIsNotNone(power.validate("not a number"))

    def test_number_set_keeps_non_integer_members(self):
        """tx_pkt_rate advertises 5.5. An int list could not hold it."""
        rate = NumberSet("rate", ("1", "2", "5.5", "11"), sentinel="-1")
        self.assertIsNone(rate.validate("5.5"))
        self.assertIsNone(rate.validate("-1"))
        self.assertIsNotNone(rate.validate("7"))

    def test_keyword_matches_literal_names(self):
        rate = Keyword("rate", (("ble_1Mbit", "1 Mbit/s BLE"), ("ble_2Mbit", "2 Mbit/s BLE")))
        self.assertIsNone(rate.validate("ble_2Mbit"))
        self.assertIsNotNone(rate.validate("ble_3Mbit"))

    def test_text_does_not_normalise(self):
        """reg_domain reads back as 00. Parsing it to an int makes it 0."""
        domain = Text("country")
        self.assertEqual(domain.format("00"), "00")
        self.assertIsNotNone(domain.validate(""))


class TestCommand(unittest.TestCase):
    def test_render_namespaced_and_root(self):
        show = Command("show_config", reply=Reply.SYNC)
        self.assertEqual(show.render("wifi_radio_test"), "wifi_radio_test show_config")
        self.assertEqual(show.render(""), "show_config")

    def test_render_appends_arguments_verbatim(self):
        cmd = Command("reg_domain", args=(Text("cc"),))
        self.assertEqual(cmd.render("wifi_radio_test", ("00",)),
                         "wifi_radio_test reg_domain 00")

    def test_arity_is_enforced(self):
        cmd = Command("reg_domain", args=(Text("cc"),))
        self.assertIn("", cmd.errors(()))
        self.assertEqual(cmd.errors(("US",)), {})

    def test_optional_trailing_arguments(self):
        """start_duty_cycle_modulated_tx takes an optional packet count."""
        cmd = Command("duty", args=(IntRange("duty", lo=0, hi=90),
                                    IntRange("packets", lo=0)), optional=1)
        self.assertEqual(cmd.errors(("50",)), {})
        self.assertEqual(cmd.errors(("50", "10")), {})
        self.assertIn("", cmd.errors(()))
        self.assertIn("1 to 2", cmd.errors(())[""])

    def test_errors_are_keyed_by_argument(self):
        cmd = Command("x", args=(IntRange("n", lo=0, hi=5),))
        self.assertEqual(set(cmd.errors(("9",))), {"n"})

    def test_flags_default_off(self):
        cmd = Command("x")
        self.assertFalse(cmd.resets_config)
        self.assertFalse(cmd.permanent)
        self.assertIs(cmd.reply, Reply.NONE)
        self.assertEqual(cmd.gate, "")


class TestRegistry(unittest.TestCase):
    def test_lookup(self):
        show = Command("show_config")
        reg = Registry("r", "wifi_radio_test", "src", (show,))
        self.assertIs(reg.by_name("show_config"), show)
        self.assertIsNone(reg.by_name("absent"))


if __name__ == "__main__":
    unittest.main()
