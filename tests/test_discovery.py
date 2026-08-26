#
# Copyright (c) 2026 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: Apache-2.0
#
"""Discovery, and the rule that only a READY probe may hide anything."""

import unittest

from nrf_radio_gui import discovery
from nrf_radio_gui.commands import ficr, shortrange, wifi
from nrf_radio_gui.discovery import Probe, State, probe_port, subcommands


class SilentPort:
    def __init__(self, *_a, **_k):
        pass

    def read(self, _n):
        return b""

    def write(self, _data):
        pass

    def flush(self):
        pass

    def close(self):
        pass

    def reset_input_buffer(self):
        pass


class TestSubcommands(unittest.TestCase):
    def test_two_space_indent_identifies_a_subcommand(self):
        listing = ("wifi_radio_ficr_prog - nRF Wi-Fi radio FICR commands\n"
                   "Subcommands:\n"
                   "  otp_get_status            : Read OTP status\n"
                   "  otp_read_params           : Read User region status and\n"
                   "programmed fields\n"
                   "  otp_read_retrim_version   : Read Retrim Version\n")
        self.assertEqual(subcommands(listing),
                         ("otp_get_status", "otp_read_params",
                          "otp_read_retrim_version"))

    def test_the_header_is_not_a_command(self):
        self.assertNotIn("Subcommands", subcommands("Subcommands:\n  a : b\n"))

    def test_wrapped_help_at_the_left_margin_is_ignored(self):
        self.assertEqual(subcommands("  a   : x\nwrapped text\n  b   : y"),
                         ("a", "b"))

    def test_empty_input(self):
        self.assertEqual(subcommands(""), ())


class TestMayHide(unittest.TestCase):
    """The handoff's sharpest trap, made structural."""

    def test_only_ready_may_hide(self):
        self.assertTrue(Probe(port="/dev/x", state=State.READY).may_hide)
        for state in (State.NO_SHELL, State.UNREACHABLE, State.ERROR):
            with self.subTest(state.value):
                self.assertFalse(Probe(port="/dev/x", state=state).may_hide)

    def test_a_probe_that_learned_nothing_claims_everything_is_present(self):
        """Otherwise an unreachable kit strands the operator in an empty window."""
        for state in (State.NO_SHELL, State.UNREACHABLE, State.ERROR):
            probe = Probe(port="/dev/x", state=state)
            for prefix, name in ((wifi.PREFIX, "rx_bss_color"),
                                 (shortrange.PREFIX, "fem"),
                                 (ficr.PREFIX, "otp_write_params")):
                with self.subTest(f"{state.value}:{name}"):
                    self.assertTrue(probe.has(prefix, name))

    def test_a_ready_probe_reports_only_what_it_enumerated(self):
        probe = Probe(port="/dev/x", state=State.READY,
                      registries={wifi.PREFIX: ("show_config", "tx_power")})
        self.assertTrue(probe.has(wifi.PREFIX, "show_config"))
        self.assertFalse(probe.has(wifi.PREFIX, "rx_bss_color"))

    def test_ready_probe_with_an_unseen_registry_hides_it(self):
        probe = Probe(port="/dev/x", state=State.READY, registries={})
        self.assertFalse(probe.has(ficr.PREFIX, "otp_get_status"))


class TestClassify(unittest.TestCase):
    def test_no_reply_means_no_shell(self):
        self.assertIs(discovery.classify(None), State.NO_SHELL)

    def test_reply_timeout_leaves_margin_over_the_measured_reply(self):
        """First reply measured 100-101 ms, nine for nine."""
        self.assertGreaterEqual(discovery.REPLY_TIMEOUT_S, 1.0)


class TestProbePort(unittest.TestCase):
    def test_a_port_that_cannot_be_opened_is_a_result_not_an_exception(self):
        probe = probe_port("/dev/definitely-not-a-port")
        self.assertIs(probe.state, State.UNREACHABLE)
        self.assertTrue(probe.detail)
        self.assertFalse(probe.may_hide)

    def test_a_silent_port_is_no_shell(self):
        probe = probe_port("/dev/fake", opener=lambda *a, **k: SilentPort())
        self.assertIs(probe.state, State.NO_SHELL)
        self.assertFalse(probe.may_hide)

    def test_summary_is_readable_for_every_state(self):
        for state in State:
            with self.subTest(state.value):
                self.assertIn(state.value,
                              Probe(port="/dev/x", state=state).summary())


class TestSerialTargeting(unittest.TestCase):
    """A bench with two DKs must not let the wrong one win."""

    def setUp(self):
        from nrf_radio_gui.nrfutil import Device, Port
        self.l15 = Device(serial="1057755632", serial_raw="001057755632",
                          board_version="PCA10156",
                          ports=(Port("/dev/ttyACM0", 0), Port("/dev/ttyACM1", 1)))
        self.lm20 = Device(serial="1051810810", serial_raw="001051810810",
                           board_version="PCA10184",
                           ports=(Port("/dev/ttyACM2", 0), Port("/dev/ttyACM3", 1)))
        self.both = [self.l15, self.lm20]

    def test_without_a_serial_every_port_is_a_candidate(self):
        ports = [p for p, _ in discovery.candidate_ports(self.both)]
        self.assertEqual(ports, ["/dev/ttyACM0", "/dev/ttyACM1",
                                 "/dev/ttyACM2", "/dev/ttyACM3"])

    def test_a_serial_narrows_to_one_kit(self):
        ports = [p for p, _ in discovery.candidate_ports(self.both, serial="1051810810")]
        self.assertEqual(ports, ["/dev/ttyACM2", "/dev/ttyACM3"])

    def test_the_padded_serial_from_json_also_matches(self):
        ports = [p for p, _ in discovery.candidate_ports(self.both,
                                                         serial="001051810810")]
        self.assertEqual(ports, ["/dev/ttyACM2", "/dev/ttyACM3"])

    def test_an_unknown_serial_yields_nothing_rather_than_everything(self):
        self.assertEqual(discovery.candidate_ports(self.both, serial="9999"), ())

    def test_vcom0_is_tried_before_vcom1(self):
        ports = [p for p, _ in discovery.candidate_ports([self.lm20])]
        self.assertEqual(ports[0], "/dev/ttyACM2")

    def test_scan_pinned_to_a_serial_never_touches_the_other_kit(self):
        opened = []

        def opener(port, baud, timeout=None):
            opened.append(port)
            return SilentPort()

        discovery.scan(self.both, opener=opener, serial="1051810810")
        self.assertEqual(set(opened), {"/dev/ttyACM2", "/dev/ttyACM3"})


class TestWitness(unittest.TestCase):
    def test_short_range_is_proven_by_a_command_not_a_prefix(self):
        witnesses = dict(discovery.WITNESS)
        self.assertEqual(witnesses[wifi.PREFIX], wifi.PREFIX)
        self.assertEqual(witnesses[ficr.PREFIX], ficr.PREFIX)
        self.assertEqual(witnesses[shortrange.PREFIX], "parameters_print")


if __name__ == "__main__":
    unittest.main()
