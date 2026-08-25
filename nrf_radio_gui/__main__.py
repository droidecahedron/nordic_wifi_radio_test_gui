#
# Copyright (c) 2026 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: Apache-2.0
#
"""Entry point, so `python -m nrf_radio_gui` and the frozen binary share a path."""

import sys

from nrf_radio_gui.app import main

if __name__ == "__main__":
    sys.exit(main())
