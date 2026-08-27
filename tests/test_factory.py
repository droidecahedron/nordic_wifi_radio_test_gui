#
# Copyright (c) 2026 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: Apache-2.0
#
"""Widget factory, row geometry, and the two layout faults that only show in a render."""

import unittest

from PyQt6.QtGui import QFont, QFontMetrics
from PyQt6.QtWidgets import QApplication, QComboBox, QLabel, QLineEdit, QSpinBox

from nrf_radio_gui import theme
from nrf_radio_gui.commands import ficr, shortrange, wifi
from nrf_radio_gui.widgets import factory
from nrf_radio_gui.widgets.factory import (
    CommandRow,
    arg_width,
    fits,
    label_width,
    row_width,
    value_of,
    widget_for,
)

ALL = (wifi, shortrange, ficr)
TOTAL_ARGS = 73


def setUpModule():
    global _app
    _app = QApplication.instance() or QApplication([])
    theme.apply(_app)


class TestBudget(unittest.TestCase):
    """A wide row pushes its own Send button behind a horizontal scroll bar."""

    def test_every_arity_in_the_tables_fits(self):
        for count in range(factory.MAX_ARGS + 1):
            with self.subTest(count):
                self.assertTrue(fits(count), f"{count} args -> {row_width(count)} px")

    def test_widest_command_is_within_max_args(self):
        widest = max((c for m in ALL for c in m.COMMANDS), key=lambda c: len(c.args))
        self.assertLessEqual(len(widest.args), factory.MAX_ARGS)
        self.assertEqual(widest.name, "config_pta")

    def test_the_budget_is_not_vacuous(self):
        """It has to reject something, or it is only decoration."""
        self.assertFalse(fits(factory.MAX_ARGS + 4))

    def test_row_width_grows_with_arity(self):
        widths = [row_width(n) for n in range(factory.MAX_ARGS + 1)]
        self.assertEqual(widths, sorted(widths))


class TestLabelWidth(unittest.TestCase):
    """A clipped command name reads as a different command.

    The width is measured rather than fixed. 232 px fits the longest name in the
    font this machine happens to use and clips it in DejaVu Sans 10pt at 249 px,
    which is how the Windows runner failed while Linux and macOS passed.
    """

    def test_no_command_name_is_clipped(self):
        metrics = QFontMetrics(QLabel().font())
        for module in ALL:
            for command in module.COMMANDS:
                with self.subTest(command.name):
                    self.assertLessEqual(metrics.horizontalAdvance(command.name),
                                         label_width())

    def test_label_never_drops_below_its_floor(self):
        self.assertGreaterEqual(label_width(), factory.LABEL_MIN_W)

    def test_a_wider_font_widens_the_window_instead_of_clipping(self):
        """The Windows case: a bigger UI font must not squeeze the row.

        Scales the font actually in use rather than naming families. Naming
        "DejaVu Sans" got an unpredictable substitute on the Windows runner,
        which measured the longest name at 666 px and left 56 px per argument.
        """
        names = factory._command_names()
        base = QLabel().font()
        start = base.pointSize() if base.pointSize() > 0 else 9
        for scale in (1, 2, 3, 4):
            with self.subTest(f"{start * scale}pt"):
                font = QFont(base)
                font.setPointSize(start * scale)
                widest = max(QFontMetrics(font).horizontalAdvance(n) for n in names)
                label = max(factory.LABEL_MIN_W, widest + factory.LABEL_PAD)
                self.assertGreaterEqual(label, widest,
                                        "label must cover the widest name")

                fixed = (label + factory.button_width()
                         + factory.SPACING * (factory.MAX_ARGS + 1)
                         + factory.MARGINS + factory.SCROLLBAR_W)
                required = fixed + factory.MAX_ARGS * factory.ARG_MIN_W
                window = max(factory.WINDOW_W, required)
                spare = (window - fixed) // factory.MAX_ARGS
                # The window grows to hold the row rather than the argument
                # column shrinking below what a value needs.
                self.assertGreaterEqual(spare, factory.ARG_MIN_W)
                self.assertLessEqual(fixed + factory.MAX_ARGS * spare, window)

    def test_no_button_label_is_clipped(self):
        """A fixed 90 px clipped the bold "Write OTP" to "Nrite OTP".

        Compares against sizeHint, which includes the stylesheet's padding and
        border. A font-metrics estimate missed those and still clipped.
        """
        from PyQt6.QtWidgets import QPushButton
        for text in factory.BUTTON_LABELS:
            for role in ("primary", "danger"):
                with self.subTest(f"{text} {role}"):
                    probe = QPushButton(text)
                    probe.setProperty("role", role)
                    probe.ensurePolished()
                    self.assertLessEqual(probe.sizeHint().width(),
                                         factory.button_width())

    def test_the_window_never_narrows_below_the_preferred_width(self):
        self.assertGreaterEqual(factory.window_width(), factory.WINDOW_W)

    def test_a_three_argument_row_fits_the_window_it_opens_at(self):
        self.assertLessEqual(row_width(factory.MAX_ARGS), factory.window_width())


class TestWidgetChoice(unittest.TestCase):
    def test_every_argument_in_every_table_builds_and_yields_a_string(self):
        built = 0
        for module in ALL:
            for command in module.COMMANDS:
                for arg in command.args:
                    with self.subTest(f"{command.name}:{arg.name}"):
                        widget = widget_for(arg)
                        self.assertIsInstance(value_of(widget), str)
                    built += 1
        self.assertEqual(built, TOTAL_ARGS)

    def test_known_bounds_become_a_spin_box(self):
        widget = widget_for(wifi.REGISTRY.by_name("set_xo_val").args[0])
        self.assertIsInstance(widget, QSpinBox)
        self.assertEqual((widget.minimum(), widget.maximum()), (0, 127))

    def test_an_open_bound_does_not_get_an_invented_ceiling(self):
        """tx_power: a spin box would have to be given one, and 24 would be wrong."""
        self.assertIsInstance(widget_for(wifi.REGISTRY.by_name("tx_power").args[0]),
                              QLineEdit)

    def test_reg_domain_is_a_line_edit_so_00_survives(self):
        self.assertIsInstance(widget_for(wifi.REGISTRY.by_name("reg_domain").args[0]),
                              QLineEdit)

    def test_flags_and_choices_become_combos_carrying_the_shell_wording(self):
        combo = widget_for(wifi.REGISTRY.by_name("tx").args[0])
        self.assertIsInstance(combo, QComboBox)
        self.assertIn("Disable TX", combo.itemText(0))
        self.assertEqual(combo.itemData(0), "0")

    def test_sentinel_label_does_not_repeat_the_value(self):
        combo = widget_for(wifi.REGISTRY.by_name("tx_pkt_rate").args[0])
        self.assertEqual(combo.itemText(0), "-1 leaves legacy rate unused")
        self.assertEqual(combo.itemData(0), "-1")

    def test_argument_widgets_share_one_width_so_the_column_aligns(self):
        widths = set()
        for module in ALL:
            for command in module.COMMANDS:
                for arg in command.args:
                    widths.add(widget_for(arg).width())
        self.assertEqual(widths, {arg_width()})

    def test_argument_width_stays_inside_its_bounds(self):
        self.assertGreaterEqual(arg_width(), factory.ARG_MIN_W)
        self.assertLessEqual(arg_width(), factory.ARG_MAX_W)


class TestArgTooltips(unittest.TestCase):
    """A stepped or typed control shows no bounds on screen, so the tip must."""

    def tip(self, module, name, index=0):
        command = module.REGISTRY.by_name(name)
        return factory.describe_arg(command.args[index], command)

    def test_a_bounded_range_states_both_ends(self):
        self.assertIn("Range: 0 to 127", self.tip(wifi, "set_xo_val"))

    def test_the_unit_rides_along(self):
        self.assertIn("MHz above 2400", self.tip(shortrange, "start_channel"))

    def test_the_default_is_attributed_to_its_source(self):
        self.assertIn("Default: 42 or value programmed in OTP",
                      self.tip(wifi, "set_xo_val"))
        self.assertIn("(SDK docs)", self.tip(wifi, "tx_power"))

    def test_an_unclamped_field_still_shows_the_documented_range(self):
        """tx_power: doc says 0-24, the kit boots at 30 and accepts it."""
        tip = self.tip(wifi, "tx_power")
        self.assertIn("Documented range: 0 to 24", tip)
        self.assertIn("not enforced here", tip)
        self.assertIsNone(wifi.REGISTRY.by_name("tx_power").args[0].validate("30"))

    def test_a_discrete_set_lists_its_members_and_sentinel(self):
        tip = self.tip(wifi, "tx_pkt_rate")
        self.assertIn("5.5", tip)
        self.assertIn("Or -1", tip)

    def test_free_text_says_the_shell_decides(self):
        self.assertIn("Free text", self.tip(wifi, "reg_domain"))

    def test_every_non_dropdown_argument_gets_a_tooltip(self):
        from nrf_radio_gui.commands.spec import Choice, Flag, Keyword
        for module in ALL:
            for command in module.COMMANDS:
                for arg in command.args:
                    if isinstance(arg, (Choice, Flag, Keyword)):
                        continue
                    with self.subTest(f"{command.name}:{arg.name}"):
                        self.assertTrue(factory.describe_arg(arg, command).strip())

    def test_the_widget_carries_it(self):
        command = wifi.REGISTRY.by_name("set_xo_val")
        self.assertIn("0 to 127", widget_for(command.args[0], command).toolTip())


class TestDocumentedBounds(unittest.TestCase):
    """The doc's Argument column is the authority for a range."""

    def test_every_documented_range_matches_the_table(self):
        from nrf_radio_gui.commands import docs
        from nrf_radio_gui.commands.spec import IntRange
        unclamped = {"tx_power"}      # kit boots outside the documented range
        for name, (lo, hi) in docs.RANGES.items():
            command = wifi.REGISTRY.by_name(name)
            if command is None or name in unclamped:
                continue
            ints = [a for a in command.args if isinstance(a, IntRange)]
            if not ints:
                continue
            with self.subTest(name):
                self.assertEqual((ints[0].lo, ints[0].hi), (lo, hi))

    def test_a_wrong_help_string_did_not_win(self):
        """Help claimed tx_pkt_gap min 200 and max 16384 for rx_capture_length."""
        self.assertEqual(wifi.REGISTRY.by_name("tx_pkt_gap").args[0].lo, 0)
        self.assertEqual(wifi.REGISTRY.by_name("rx_capture_length").args[0].hi, 16383)


class TestCommandRow(unittest.TestCase):
    def setUp(self):
        self.seen = []
        self.sink = lambda row, line, errors: self.seen.append((line, errors))

    def _row(self, module, name):
        # Held on self: an unparented QWidget is collected the moment the last
        # Python reference drops, taking its C++ button with it.
        self.row = CommandRow(module.REGISTRY.by_name(name), module.PREFIX, self.sink)
        return self.row

    def test_zero_argument_command(self):
        self._row(wifi, "show_config").button.click()
        self.assertEqual(self.seen[-1][0], "wifi_radio_test show_config")

    def test_three_argument_command(self):
        self._row(wifi, "config_pta").button.click()
        self.assertEqual(self.seen[-1][0], "wifi_radio_test config_pta 0 0 0")

    def test_root_registry_renders_unprefixed(self):
        self._row(shortrange, "parameters_print").button.click()
        self.assertEqual(self.seen[-1][0], "parameters_print")

    def test_keyword_combo_sends_the_keyword(self):
        self._row(shortrange, "data_rate").button.click()
        self.assertEqual(self.seen[-1][0], "data_rate nrf_1Mbit")

    def test_invalid_value_is_refused_and_marked(self):
        row = self._row(wifi, "tx_power")
        row.widgets[0].setText("not a number")
        row.button.click()
        line, errors = self.seen[-1]
        self.assertIsNone(line)
        self.assertTrue(errors)
        self.assertEqual(row.widgets[0].property("state"), "invalid")

    def test_the_invalid_mark_clears_on_a_good_value(self):
        row = self._row(wifi, "tx_power")
        row.widgets[0].setText("nope")
        row.button.click()
        row.widgets[0].setText("30")
        row.button.click()
        self.assertEqual(self.seen[-1][0], "wifi_radio_test tx_power 30")
        self.assertEqual(row.widgets[0].property("state"), "")

    def test_permanent_commands_do_not_look_like_send(self):
        write = self._row(ficr, "otp_write_params")
        self.assertEqual(write.button.text(), "Write OTP")
        self.assertEqual(write.button.property("role"), "danger")

    def test_read_commands_look_ordinary(self):
        read = self._row(ficr, "otp_get_status")
        self.assertEqual(read.button.text(), "Send")
        self.assertEqual(read.button.property("role"), "primary")


if __name__ == "__main__":
    unittest.main()
