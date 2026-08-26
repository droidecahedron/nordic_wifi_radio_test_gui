#
# Copyright (c) 2026 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: Apache-2.0
#
"""Tests. No hardware, no display.

Run with:

    QT_QPA_PLATFORM=offscreen python -m unittest discover tests

Anything needing a kit lives in tools/bench_check.py instead, because a test
that silently passes when the hardware is absent is worse than no test.
"""
