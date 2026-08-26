#
# Copyright (c) 2026 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: Apache-2.0
#
"""Entry point, so `python -m nrf_radio_gui` and the frozen binary share a path.

`--selftest` runs the hardware bench check instead of opening the window. That
exists so a downloaded executable can be verified against a kit without a
checkout, which is the only way to tell a working build from one whose serial or
nrfutil plumbing did not survive being frozen.
"""

import sys


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if "--selftest" in argv:
        from nrf_radio_gui.benchcheck import main as selftest

        return selftest([a for a in argv if a != "--selftest"])
    if "--version" in argv:
        from nrf_radio_gui import __version__

        print(f"nrf_radio_gui {__version__}")
        return 0
    from nrf_radio_gui.app import main as gui

    return gui()


if __name__ == "__main__":
    sys.exit(main())
