#
# Copyright (c) 2026 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: Apache-2.0
#
"""Transport parsing and reply modes, against a fake port.

The byte strings here are verbatim captures from an nRF54LM20 DK, not invented
input. The escape-sequence fragments in particular were not something anyone
would think to write by hand.
"""

import unittest

from nrf_radio_gui.commands.spec import Reply
from nrf_radio_gui.transport import Transport, clean, split

# A probe of a freshly reset kit. Begins mid-escape because the ESC went out in
# the previous read, and contains a bare `\x1b[8`, the head of a `\x1b[8D` cursor
# move that the newline cut off.
BOOT_PROBE = (
    b'[m\r\n\x1b[1;32muart:~$ \x1b[m\x1b[8D\x1b[J[01:08:50.195,814] '
    b'\x1b[0m<inf> wifi_nrf_bus: SPIM spi@c8000: freq = 8 MHz\x1b[0m\r\n'
    b'\x1b[1;32muart:~$ \x1b[m\x1b[8\r\n\x1b[1;32muart:~$ \x1b[m'
)

DEFERRED_REPLY = (
    "wifi_radio_test get_temperature\n"
    "uart:~$ [00:02:31.285,348] <inf> wifi_nrf: The temperature is = 30 degree celsius\n"
    "uart:~$ uart:~$ "
)

SHOW_CONFIG = (
    "wifi_radio_test show_config\n"
    "************* Configured Parameters ***********\n"
    "tx_power = 30\nreg_domain = 00\nuart:~$ "
)

# rssi_avg is spaced around its `=` and carries a unit; the counters are not.
GET_STATS = (
    "wifi_radio_test get_stats\n"
    "************* PHY STATS ***********\n"
    "rssi_avg = 0 dBm\nofdm_crc32_pass_cnt=0\nuart:~$ "
)

HELP_LISTING = (
    "wifi_radio_ficr_prog\n"
    "wifi_radio_ficr_prog - nRF Wi-Fi radio FICR commands\n"
    "Subcommands:\n"
    "  otp_get_status            : Read OTP status\n"
    "  otp_read_params           : Read User region status and information on\n"
    "programmed fields\n"
    "  otp_read_retrim_version   : Read Retrim Version\n"
    "uart:~$ "
)


class FakePort:
    """Minimal stand-in for serial.Serial."""

    def __init__(self, port, baud, timeout=None, script=()):
        self.port = port
        self.script = list(script)
        self.written = []

    def read(self, _n):
        return self.script.pop(0) if self.script else b""

    def write(self, data):
        self.written.append(data)

    def flush(self):
        pass

    def close(self):
        pass

    def reset_input_buffer(self):
        pass


def opener_for(*chunks):
    def make(port, baud, timeout=None):
        return FakePort(port, baud, timeout, chunks)
    return make


class TestClean(unittest.TestCase):
    def test_ansi_is_removed(self):
        self.assertNotIn("\x1b", clean(BOOT_PROBE))

    def test_newlines_are_normalised(self):
        self.assertNotIn("\r", clean(b"a\r\nb\rc"))


class TestSplit(unittest.TestCase):
    def test_boot_probe_yields_one_log_and_no_output(self):
        output, logs = split(BOOT_PROBE, "")
        self.assertEqual(output, ())
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].module, "wifi_nrf_bus")
        self.assertEqual(logs[0].level, "inf")
        self.assertEqual(logs[0].text, "SPIM spi@c8000: freq = 8 MHz")

    def test_no_escape_survives_into_output(self):
        output, logs = split(BOOT_PROBE, "")
        joined = "".join(output) + "".join(l.text for l in logs)
        self.assertNotIn("\x1b", joined)
        self.assertNotIn("[8", joined)

    def test_echo_is_dropped(self):
        output, _ = split(SHOW_CONFIG, "wifi_radio_test show_config")
        self.assertNotIn("wifi_radio_test show_config", output)

    def test_synchronous_output_is_kept_in_order(self):
        output, logs = split(SHOW_CONFIG, "wifi_radio_test show_config")
        self.assertEqual(logs, ())
        self.assertIn("tx_power = 30", output)
        self.assertIn("reg_domain = 00", output)

    def test_deferred_value_is_a_log_not_output(self):
        output, logs = split(DEFERRED_REPLY, "wifi_radio_test get_temperature")
        self.assertEqual(output, ())
        self.assertEqual(len(logs), 1)
        self.assertIn("30 degree celsius", logs[0].text)

    def test_both_stat_spacings_survive(self):
        output, _ = split(GET_STATS, "wifi_radio_test get_stats")
        self.assertIn("rssi_avg = 0 dBm", output)
        self.assertIn("ofdm_crc32_pass_cnt=0", output)

    def test_prompt_glued_to_content_leaves_no_gap(self):
        output, _ = split("cmd\nuart:~$ Something real\nuart:~$ ", "cmd")
        self.assertEqual(output, ("Something real",))

    def test_indentation_is_preserved(self):
        """Two leading spaces separate a subcommand from a wrapped help line."""
        output, _ = split(HELP_LISTING, "wifi_radio_ficr_prog")
        indented = [l for l in output if l.startswith("  ")]
        self.assertEqual(len(indented), 3)
        self.assertIn("programmed fields", output)
        self.assertFalse(any(l.startswith("  ") and "programmed fields" in l
                             for l in output))


class TestTransport(unittest.TestCase):
    def test_sync_reply_is_returned(self):
        opener = opener_for(b"kernel uptime\r\nUptime: 1234 ms\r\nuart:~$ ")
        with Transport("/dev/fake", opener=opener) as port:
            exchange = port.send("kernel uptime", Reply.SYNC)
        self.assertEqual(exchange.output, ("Uptime: 1234 ms",))
        self.assertFalse(exchange.timed_out)
        self.assertIsNotNone(exchange.first_byte_ms)

    def test_command_is_written_with_crlf(self):
        opener = opener_for(b"uart:~$ ")
        with Transport("/dev/fake", opener=opener) as port:
            port.send("show_config", Reply.SYNC)
            self.assertEqual(port._ser.written[-1], b"show_config\r\n")

    def test_silent_port_times_out_without_raising(self):
        with Transport("/dev/fake", opener=opener_for()) as port:
            exchange = port.send("anything", Reply.SYNC)
        self.assertTrue(exchange.timed_out)
        self.assertEqual(exchange.output, ())

    def test_silent_deferred_reply_also_times_out(self):
        with Transport("/dev/fake", opener=opener_for()) as port:
            exchange = port.send("wifi_radio_test get_temperature", Reply.DEFERRED)
        self.assertTrue(exchange.timed_out)

    def test_send_before_open_is_an_error(self):
        port = Transport("/dev/fake", opener=opener_for())
        with self.assertRaises(RuntimeError):
            port.send("show_config", Reply.SYNC)

    def test_close_is_idempotent(self):
        port = Transport("/dev/fake", opener=opener_for())
        port.open()
        port.close()
        port.close()
        self.assertFalse(port.is_open)

    def test_expect_keeps_only_this_commands_answer(self):
        """An abandoned reading from an earlier command must not be attributed here."""
        stale_then_real = (
            b"wifi_radio_test get_voltage\r\nuart:~$ "
            b"[00:01:00.000,000] <inf> wifi_nrf: The temperature is = 30 degree celsius\r\n"
            b"[00:01:01.000,000] <inf> wifi_nrf: The battery voltage is = 3690 mV\r\n"
            b"uart:~$ "
        )
        opener = opener_for(stale_then_real)
        with Transport("/dev/fake", opener=opener) as port:
            exchange = port.send("wifi_radio_test get_voltage", Reply.DEFERRED,
                                 "voltage is")
        self.assertEqual(len(exchange.logs), 1)
        self.assertIn("battery voltage", exchange.logs[0].text)
        self.assertFalse(any("temperature" in l.text for l in exchange.logs))

    def test_without_expect_every_log_is_kept(self):
        """The old behaviour, still right for an answer with no distinct wording."""
        both = (
            b"cmd\r\nuart:~$ "
            b"[00:01:00.000,000] <inf> wifi_nrf: The temperature is = 30 degree celsius\r\n"
            b"[00:01:01.000,000] <inf> wifi_nrf: The battery voltage is = 3690 mV\r\n"
            b"uart:~$ "
        )
        with Transport("/dev/fake", opener=opener_for(both)) as port:
            exchange = port.send("cmd", Reply.DEFERRED)
        self.assertEqual(len(exchange.logs), 2)

    def test_expect_is_case_insensitive(self):
        reply = (b"cmd\r\nuart:~$ [00:01:00.000,000] <inf> wifi_nrf: "
                 b"RF RSSI value is = 7\r\nuart:~$ ")
        with Transport("/dev/fake", opener=opener_for(reply)) as port:
            exchange = port.send("cmd", Reply.DEFERRED, "rssi VALUE is")
        self.assertEqual(len(exchange.logs), 1)

    def test_every_deferred_command_declares_what_its_answer_looks_like(self):
        from nrf_radio_gui.commands import wifi
        from nrf_radio_gui.commands.spec import Reply as R
        deferred = [c for c in wifi.COMMANDS if c.reply is R.DEFERRED]
        self.assertTrue(deferred)
        for command in deferred:
            with self.subTest(command.name):
                self.assertTrue(command.log_match,
                                f"{command.name} defers but cannot identify its reply")

    def test_exchange_text_joins_output_and_logs(self):
        opener = opener_for(BOOT_PROBE)
        with Transport("/dev/fake", opener=opener) as port:
            exchange = port.send("", Reply.SYNC)
        self.assertIn("wifi_nrf_bus", exchange.text())


if __name__ == "__main__":
    unittest.main()
