#!/usr/bin/env python3
#
# Copyright (c) 2026 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: Apache-2.0
#
"""Run the hardware bench check from a checkout.

    python tools/bench_check.py --serial 1051810810

The checks live in `nrf_radio_gui/benchcheck.py` so a frozen executable carries
them too, and can verify itself with `--selftest`. This is the path a repo user
runs; both call the same code.
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from nrf_radio_gui.benchcheck import main

if __name__ == "__main__":
    sys.exit(main())
