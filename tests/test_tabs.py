#
# Copyright (c) 2026 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: Apache-2.0
#
"""Tabs: what they show, and the gate in front of a permanent write."""

import unittest

from PyQt6.QtWidgets import QApplication

from nrf_radio_gui import theme
from nrf_radio_gui.commands import ficr, shortrange, wifi
from nrf_radio_gui.discovery import Probe, State
from nrf_radio_gui.widgets import ficr_tab as ficr_tab_module
from nrf_radio_gui.widgets.command_tab import CommandTab
from nrf_radio_gui.widgets.ficr_tab import ConfirmWrite, FicrTab

ABSENT_GATES = (
    "CONFIG_NRF71_RADIO_TEST",
    "CONFIG_NRF70_SR_COEX || CONFIG_NRF71_SR_COEX",
    "CONFIG_NRF70_SR_COEX_RF_SWITCH || CONFIG_NRF71_SR_COEX_RF_SWITCH",
)


def setUpModule():
    global _app
    _app = QApplication.instance() or QApplication([])
    theme.apply(_app)


def measured_probe():
    """What SN 1051810810 actually presented, as a Probe."""
    return Probe(port="/dev/ttyACM2", state=State.READY, reply_ms=50, registries={
        wifi.PREFIX: tuple(c.name for c in wifi.COMMANDS
                           if c.gate not in ABSENT_GATES),
        shortrange.PREFIX: tuple(c.name for c in shortrange.COMMANDS if not c.gate),
        ficr.PREFIX: tuple(c.name for c in ficr.COMMANDS),
    })


class TestGating(unittest.TestCase):
    def setUp(self):
        self.sent = []
        self.notes = []
        self.send = lambda line, reply, command: self.sent.append((line, reply, command))
        self.notify = self.notes.append

    def tab(self, registry, probe):
        return CommandTab(registry, probe, self.send, self.notify)

    def test_rows_match_the_measured_image(self):
        probe = measured_probe()
        for registry, expected in ((wifi.REGISTRY, 43), (shortrange.REGISTRY, 20),
                                   (ficr.REGISTRY, 7)):
            with self.subTest(registry.prefix or "root"):
                self.assertEqual(len(self.tab(registry, probe).rows), expected)

    def test_gated_out_commands_are_absent(self):
        names = [r.command.name for r in self.tab(wifi.REGISTRY, measured_probe()).rows]
        for absent in ("rx_bss_color", "config_pta", "sr_ant_switch_ctrl", "tx_dcm"):
            with self.subTest(absent):
                self.assertNotIn(absent, names)
        self.assertIn("set_ant_gain", names)

    def test_a_probe_that_learned_nothing_shows_everything(self):
        """Hiding on a failed probe strands the operator in an empty window."""
        for state in (State.NO_SHELL, State.UNREACHABLE, State.ERROR):
            with self.subTest(state.value):
                tab = self.tab(wifi.REGISTRY, Probe(port="/dev/x", state=state))
                self.assertEqual(len(tab.rows), len(wifi.COMMANDS))

    def test_no_probe_at_all_shows_everything(self):
        self.assertEqual(len(self.tab(wifi.REGISTRY, None).rows), len(wifi.COMMANDS))


class TestFilterAndCount(unittest.TestCase):
    def setUp(self):
        self.tab = CommandTab(wifi.REGISTRY, measured_probe(),
                              lambda *a: None, lambda t: None)

    def shown(self):
        return sum(1 for r in self.tab.rows if not r.isHidden())

    def test_count_is_right_before_the_window_is_shown(self):
        """isVisible() is False for every child until shown; isHidden() is not."""
        self.assertEqual(self.tab.count.text(), "43 of 55 on this image")

    def test_filter_narrows(self):
        self.tab.filter.setText("phy_calib")
        self.assertEqual(self.shown(), 5)
        self.tab.filter.setText("tx_pkt")
        self.assertEqual(self.shown(), 9)

    def test_filter_is_case_insensitive(self):
        self.tab.filter.setText("TX_POWER")
        self.assertEqual(self.shown(), 1)

    def test_no_match_shows_nothing(self):
        self.tab.filter.setText("zzzz")
        self.assertEqual(self.shown(), 0)

    def test_clearing_restores(self):
        self.tab.filter.setText("phy")
        self.tab.filter.setText("")
        self.assertEqual(self.shown(), 43)
        self.assertEqual(self.tab.count.text(), "43 of 55 on this image")


class TestSendFunnelling(unittest.TestCase):
    def setUp(self):
        self.sent = []
        self.notes = []
        self.tab = CommandTab(wifi.REGISTRY, measured_probe(),
                              lambda l, r, c: self.sent.append((l, r, c)),
                              self.notes.append)

    def row(self, name):
        return next(r for r in self.tab.rows if r.command.name == name)

    def test_the_reply_mode_comes_from_the_table(self):
        self.row("show_config").button.click()
        self.assertIs(self.sent[-1][1], wifi.REGISTRY.by_name("show_config").reply)
        self.row("get_temperature").button.click()
        self.assertIs(self.sent[-1][1], wifi.REGISTRY.by_name("get_temperature").reply)

    def test_a_rejected_row_never_reaches_the_kit(self):
        row = self.row("tx_power")
        row.widgets[0].setText("bad")
        row.button.click()
        self.assertEqual(self.sent, [])
        self.assertTrue(self.notes)


class TestPermanentWrites(unittest.TestCase):
    """OTP cannot be rewritten, so this is the test that matters most."""

    def setUp(self):
        self.sent = []
        self.notes = []
        self._real = ficr_tab_module.confirm_permanent
        self.tab = FicrTab(measured_probe(),
                           lambda l, r, c: self.sent.append((l, r, c)),
                           self.notes.append)

    def tearDown(self):
        ficr_tab_module.confirm_permanent = self._real

    def row(self, name):
        return next(r for r in self.tab.rows if r.command.name == name)

    def _fill(self, row):
        for widget in row.widgets:
            if hasattr(widget, "setText"):
                widget.setText("0x130" if not widget.text() else widget.text())

    def test_no_write_reaches_the_kit_when_confirmation_is_declined(self):
        ficr_tab_module.confirm_permanent = lambda *a, **k: False
        for name in ("otp_write_params", "otp_write_retrim_version",
                     "otp_write_retrim_params"):
            with self.subTest(name):
                row = self.row(name)
                self._fill(row)
                row.button.click()
        self.assertEqual(self.sent, [])
        self.assertEqual(len(self.notes), 3)

    def test_a_write_proceeds_once_confirmed(self):
        ficr_tab_module.confirm_permanent = lambda *a, **k: True
        row = self.row("otp_write_retrim_version")
        row.widgets[0].setText("1")
        row.button.click()
        self.assertEqual(len(self.sent), 1)
        self.assertIn("otp_write_retrim_version", self.sent[0][0])

    def test_reads_are_never_gated(self):
        ficr_tab_module.confirm_permanent = lambda *a, **k: False
        self.row("otp_get_status").button.click()
        self.assertEqual(len(self.sent), 1)

    def test_the_typed_target_is_the_field_the_address_selects(self):
        write = ficr.REGISTRY.by_name("otp_write_params")
        cases = {
            "wifi_radio_ficr_prog otp_write_params 0x130 0x2e": "CALIB_XO",
            "wifi_radio_ficr_prog otp_write_params 0x120 1 2": "MAC0_ADDR",
            "wifi_radio_ficr_prog otp_write_params 0x110 1 2 3 4": "QSPI_KEY",
            "wifi_radio_ficr_prog otp_write_params 0x100 1": "REGION_PROTECT",
        }
        for line, target in cases.items():
            with self.subTest(target):
                self.assertEqual(FicrTab._target_for(write, line), target)

    def test_a_word_offset_is_not_a_target_and_falls_back(self):
        """76 is CALIB_XO's word offset; the shell wants 0x130."""
        write = ficr.REGISTRY.by_name("otp_write_params")
        self.assertEqual(
            FicrTab._target_for(write, "wifi_radio_ficr_prog otp_write_params 76 1"),
            "otp_write_params")

    def test_the_address_reference_is_shown(self):
        titles = [g.title() for g in self.tab.extra_groups()]
        self.assertTrue(any("OTP write" in t for t in titles))


class TestConfirmDialog(unittest.TestCase):
    def setUp(self):
        self.dialog = ConfirmWrite("CALIB_XO",
                                   "wifi_radio_ficr_prog otp_write_params 0x130 0x2e")

    def test_starts_disarmed(self):
        self.assertFalse(self.dialog.ok.isEnabled())

    def test_only_an_exact_match_arms_it(self):
        for text, armed in (("calib_xo", False), ("CALIB_X", False),
                            ("CALIB_XOO", False), ("CALIB_XO", True),
                            ("  CALIB_XO  ", True), ("", False)):
            with self.subTest(repr(text)):
                self.dialog.entry.setText(text)
                self.assertEqual(self.dialog.ok.isEnabled(), armed)

    def test_enter_cannot_fire_it_by_reflex(self):
        self.assertFalse(self.dialog.ok.autoDefault())
        self.assertFalse(self.dialog.ok.isDefault())


if __name__ == "__main__":
    unittest.main()
