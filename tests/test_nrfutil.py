#
# Copyright (c) 2026 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: Apache-2.0
#
"""nrfutil NDJSON parsing.

The fixture is real output from nrfutil 8.2.1 with an nRF54LM20 DK attached. The
synthetic cases below exist to document shapes we are not currently running, so
they should stay even when the fixture is refreshed.
"""

import json
import pathlib
import unittest

from nrf_radio_gui import nrfutil

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "nrfutil_device_list.ndjson"


class TestFixture(unittest.TestCase):
    """Against captured output from nrfutil 8.2.1, nRF54LM20 DK, Linux."""

    @classmethod
    def setUpClass(cls):
        cls.raw = FIXTURE.read_text()
        cls.devices = nrfutil.devices_from_ndjson(cls.raw)

    def test_one_device_parsed(self):
        self.assertEqual(len(self.devices), 1)

    def test_serial_is_unpadded_for_handing_back_to_nrfutil(self):
        """The JSON pads to 12 digits; --serial-number takes the unpadded form."""
        device = self.devices[0]
        self.assertEqual(device.serial, "1051810810")
        self.assertEqual(device.serial_raw, "001051810810")

    def test_board_comes_from_board_version(self):
        device = self.devices[0]
        self.assertEqual(device.board_version, "PCA10184")
        self.assertEqual(device.board_name, "nRF54LM20 DK")

    def test_family_is_accurate_but_coarse(self):
        self.assertEqual(self.devices[0].family, "NRF54L_FAMILY")

    def test_two_vcoms_in_order(self):
        ports = self.devices[0].ports
        self.assertEqual(len(ports), 2)
        self.assertEqual([p.vcom for p in ports], [0, 1])

    def test_vcom0_is_the_shell_port(self):
        self.assertEqual(self.devices[0].shell_port,
                         self.devices[0].port_for_vcom(0))

    def test_no_trait_name_leaks_into_the_port_list(self):
        """`serialPorts` contains `ports`, and traits has its own serialPorts key.

        A substring search fills the port list with trait names. This is the
        regression that gives the test its name.
        """
        device = self.devices[0]
        paths = {p.path for p in device.ports}
        self.assertIn("serialPorts", device.traits)
        self.assertFalse(paths & set(device.traits))
        for path in paths:
            self.assertTrue(path.startswith("/dev/"), path)

    def test_task_end_is_used_when_info_is_absent(self):
        """The device array appears twice, nested deeper under task_end."""
        without_info = "\n".join(
            line for line in self.raw.splitlines()
            if '"type":"info"' not in line
        )
        devices = nrfutil.devices_from_ndjson(without_info)
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0].serial, self.devices[0].serial)

    def test_trailing_junk_is_tolerated(self):
        self.assertEqual(
            nrfutil.devices_from_ndjson(self.raw + "\nnot json\n"),
            self.devices,
        )


class TestSynthetic(unittest.TestCase):
    """Shapes worth handling that the attached kit does not produce."""

    def test_empty_and_unparseable_input(self):
        for text in ("", "\n\n", "not json", "{}", "[]", "null"):
            with self.subTest(repr(text)):
                self.assertEqual(nrfutil.devices_from_ndjson(text), ())

    def test_no_kits_attached_is_not_an_error(self):
        """`device list` exits 0 with nothing attached."""
        empty = json.dumps({"type": "info", "data": {"devices": []}})
        self.assertEqual(nrfutil.devices_from_ndjson(empty), ())

    def test_device_with_no_ports(self):
        payload = json.dumps({"type": "info", "data": {"devices": [
            {"serialNumber": "000123456789",
             "devkit": {"boardVersion": "PCA10156", "deviceFamily": "NRF54L_FAMILY"}}
        ]}})
        device = nrfutil.devices_from_ndjson(payload)[0]
        self.assertEqual(device.ports, ())
        self.assertIsNone(device.shell_port)
        self.assertEqual(device.board_name, "nRF54L15 DK")

    def test_unknown_board_falls_back_to_the_pca_number(self):
        payload = json.dumps({"type": "info", "data": {"devices": [
            {"serialNumber": "1", "devkit": {"boardVersion": "PCA99999"}}
        ]}})
        self.assertEqual(nrfutil.devices_from_ndjson(payload)[0].board_name,
                         "PCA99999")

    def test_missing_devkit_block(self):
        payload = json.dumps({"type": "info", "data": {"devices": [
            {"serialNumber": "1"}
        ]}})
        device = nrfutil.devices_from_ndjson(payload)[0]
        self.assertEqual(device.board_name, "unknown board")

    def test_comname_is_used_when_path_is_absent(self):
        payload = json.dumps({"type": "info", "data": {"devices": [
            {"serialNumber": "1",
             "serialPorts": [{"comName": "COM7", "vcom": 0}]}
        ]}})
        device = nrfutil.devices_from_ndjson(payload)[0]
        self.assertEqual(device.shell_port, "COM7")


class TestProgrammingDefaults(unittest.TestCase):
    """Settled on hardware. Changing these needs a bench result, not an opinion."""

    def test_verify_read_not_verify_hash(self):
        """VERIFY_HASH is unimplemented in the 8.2.1 probe-plugin."""
        self.assertEqual(nrfutil.DEFAULT_VERIFY, "VERIFY_READ")

    def test_reset_is_not_none(self):
        """The nrfutil default is RESET_NONE, which leaves the kit halted."""
        self.assertEqual(nrfutil.DEFAULT_RESET, "RESET_SYSTEM")

    def test_erase_all_is_the_default_and_alternatives_are_offered(self):
        self.assertEqual(nrfutil.DEFAULT_ERASE, "ERASE_ALL")
        self.assertIn("ERASE_RANGES_TOUCHED_BY_FIRMWARE", nrfutil.ERASE_MODES)


if __name__ == "__main__":
    unittest.main()
