#!/usr/bin/env python3
#
# Copyright (c) 2026 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: Apache-2.0
#
"""Verify the tool against a real kit. Reads only.

    python tools/bench_check.py --serial 1051810810

Deliberately not a unittest: a hardware test that passes when the hardware is
absent is worse than no test. This exits non-zero on failure so it can gate a
release, and it is the only place the claim "it works on hardware" is checked.

Nothing here writes OTP or starts a transmitter. Every command sent is a read or
a query, so it is safe to run on a kit somebody else is using — with the one
caveat that it opens the port exclusively for the duration.

Pass --serial to pin it. A bench with two DKs enumerates in whatever order
nrfutil returns them, and probing the wrong one wastes 1.5 s per silent port.
"""

import argparse
import pathlib
import sys

# Runnable as `python tools/bench_check.py` from the repo root, which does not
# put the root on sys.path the way `python -m` would.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from nrf_radio_gui import discovery, nrfutil
from nrf_radio_gui.commands import ficr, shortrange, wifi
from nrf_radio_gui.commands.spec import Reply
from nrf_radio_gui.discovery import State
from nrf_radio_gui.transport import Transport

# What an nRF54LM20 DK + nRF7002-EB II running single_domain at NCS v3.4.0
# presents. A different image legitimately differs; --loose skips these.
EXPECT = {wifi.PREFIX: 43, shortrange.PREFIX: 20, ficr.PREFIX: 7}

# Measured 100-101 ms, nine for nine. Anything far above this wants investigating
# before the 1.5 s discovery budget is trusted.
REPLY_CEILING_MS = 600
# Deferred values landed at 1008-1058 ms.
DEFERRED_CEILING_MS = 2500

results = []


def check(name, condition, detail=""):
    results.append((bool(condition), name))
    mark = "PASS" if condition else "FAIL"
    print(f"{mark}  {name}" + (f"   {detail}" if detail else ""))
    return bool(condition)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--serial", help="kit to test; required if more than one")
    parser.add_argument("--loose", action="store_true",
                        help="skip the per-image command counts")
    args = parser.parse_args(argv)

    print("=== enumerate ===")
    if not nrfutil.available():
        print("FAIL  nrfutil is not on PATH")
        return 2
    print(f"      {nrfutil.version()}")
    devices = nrfutil.list_devices()
    for device in devices:
        print(f"      {device.serial:14} {device.board_name:18} "
              f"{[p.path for p in device.ports]}")
    if not check("a kit is attached", devices):
        return 2

    serial = args.serial
    if serial is None:
        if len(devices) > 1:
            print("FAIL  more than one kit attached; pass --serial")
            return 2
        serial = devices[0].serial
    wanted = [d for d in devices if d.serial.lstrip("0") == str(serial).lstrip("0")]
    if not check(f"kit {serial} is present", wanted):
        return 2
    device = wanted[0]
    print(f"      testing {device.label}")

    print("\n=== discover ===")
    probes = discovery.scan(devices, serial=device.serial)
    for probe in probes:
        print(f"      {probe.summary()}")
    ready = next((p for p in probes if p.state is State.READY), None)
    if not check("a shell answered", ready):
        print("      no shell. Is the radio test flashed? See firmware/README.md")
        return 1

    check("probe reply is inside the discovery budget",
          ready.reply_ms is not None and ready.reply_ms <= REPLY_CEILING_MS,
          f"{ready.reply_ms} ms, ceiling {REPLY_CEILING_MS} ms")
    check("only a READY probe may hide anything", ready.may_hide)

    if not args.loose:
        print("\n=== registries match the tables ===")
        for prefix, expected in EXPECT.items():
            found = len(ready.registries.get(prefix, ()))
            check(f"{prefix or 'root'}: {expected} commands", found == expected,
                  f"found {found}")

    print("\n=== every command the tables claim is really there ===")
    for module in (wifi, shortrange, ficr):
        claimed = [c.name for c in module.COMMANDS
                   if ready.has(module.PREFIX, c.name)]
        actual = set(ready.registries.get(module.PREFIX, ()))
        missing = [n for n in claimed if n not in actual]
        check(f"{module.PREFIX or 'root'}: no claimed command is absent",
              not missing, f"missing {missing}" if missing else "")

    with Transport(ready.port) as port:
        print("\n=== synchronous replies ===")
        config = port.send(wifi.REGISTRY.by_name("show_config").render(wifi.PREFIX),
                           Reply.SYNC)
        check("show_config returns its block", len(config.output) > 20,
              f"{len(config.output)} lines")
        values = dict(
            line.split("=", 1) for line in
            (l.replace(" ", "") for l in config.output) if "=" in line
        )
        check("tx_power is readable", "tx_power" in values,
              f"tx_power = {values.get('tx_power')}")
        check("reg_domain stays a string", values.get("reg_domain") == "00",
              f"reg_domain = {values.get('reg_domain')!r}")

        stats = port.send(wifi.REGISTRY.by_name("get_stats").render(wifi.PREFIX),
                          Reply.SYNC)
        joined = "\n".join(stats.output)
        check("get_stats is synchronous, not a log line", stats.logs == ())
        check("all five PHY counters present",
              all(counter in joined for counter in wifi.STATS))

        params = port.send("parameters_print", Reply.SYNC)
        check("root registry answers unprefixed",
              any("Data rate" in line for line in params.output))

        otp = port.send(ficr.REGISTRY.by_name("otp_get_status").render(ficr.PREFIX),
                        Reply.SYNC)
        check("FICR answers", any("OTP" in line for line in otp.output))

        print("\n=== deferred replies ===")
        for name in ("get_temperature", "get_voltage", "get_rf_rssi"):
            command = wifi.REGISTRY.by_name(name)
            exchange = port.send(command.render(wifi.PREFIX), command.reply,
                                 command.log_match)
            check(f"{name} returns a value", len(exchange.logs) == 1,
                  f"{exchange.elapsed_ms} ms, "
                  f"{exchange.logs[0].text if exchange.logs else 'NOTHING'}")
            check(f"{name} inside the deferred budget",
                  exchange.elapsed_ms <= DEFERRED_CEILING_MS,
                  f"{exchange.elapsed_ms} ms")

        print("\n=== a deferred value must not leak into the next command ===")
        port.send(wifi.REGISTRY.by_name("get_temperature").render(wifi.PREFIX),
                  Reply.NONE)                      # abandon it on purpose
        volt_cmd = wifi.REGISTRY.by_name("get_voltage")
        voltage = port.send(volt_cmd.render(wifi.PREFIX), Reply.DEFERRED,
                            volt_cmd.log_match)
        leaked = any("temperature" in entry.text for entry in voltage.logs)
        check("no cross-command misattribution", not leaked,
              f"{[e.text for e in voltage.logs]}")

        print("\n=== failure wordings ===")
        bad_root = port.send("this_is_not_a_command", Reply.SYNC)
        check("unknown root command says command not found",
              any(discovery.NOT_FOUND in line for line in bad_root.output))
        bad_sub = port.send("data_rate definitely_not_a_rate", Reply.SYNC)
        check("unknown short-range subcommand says Unknown argument",
              any(discovery.UNKNOWN_ARG in line for line in bad_sub.output))

    failed = [name for good, name in results if not good]
    print(f"\n{len(results) - len(failed)}/{len(results)} passed")
    if failed:
        print("failed:")
        for name in failed:
            print(f"  - {name}")
        return 1
    print(f"bench check clean against {device.label}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
