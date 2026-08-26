# nRF Radio Test GUI

Drive the nRF Connect SDK [radio test shells](https://nrfconnectdocs.nordicsemi.com/ncs/latest/nrf/samples/wifi/radio_test/single_domain/README.html) by clicking instead of typing.

<img width="991" height="734" alt="image" src="https://github.com/user-attachments/assets/a94e76b9-580e-4630-b739-afbdbdf67230" />

*Note* : This is an unofficial pyqt wrapper for the sample.

# Hardware
`nRF54LM20 DK` (PCA10184) + `nRF7002-EB II` (PCA63571)

> Nothing is keyed to that board. The tool asks the kit which commands it has, so
> any image presenting the radio test shell on a VCOM will drive. An nRF54L15 DK
> works, and so does an nRF71 or coex build — those commands are in the tables
> already, waiting for an image that has them.

# Software
`nRF Connect SDK v3.4.0` for the firmware. Host side: Python 3.12, PyQt6 6.11.0,
pyserial 3.5. `nrfutil` 8.2.1 with the `device` subcommand on `PATH`, needed for
enumerating kits and for the Flash button — not for driving a kit you have
already flashed.

# Install

```
git clone git@github.com:droidecahedron/nordic_wifi_radio_test_gui.git
cd nordic_wifi_radio_test_gui
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m nrf_radio_gui
```

On Windows the interpreter is `.venv\Scripts\python.exe`; everything else is the
same.

> Use `.venv/bin/python`, not `python3`. Activating the venv works too, but a
> plain `python3 -m nrf_radio_gui` picks the system interpreter, which has no
> PyQt6, and fails with `ModuleNotFoundError: No module named 'PyQt6'`.

> Ubuntu 24.04 on X11 also needs `sudo apt install libxcb-cursor0`, or Qt 6
> cannot load its `xcb` platform plugin. On Wayland it is not needed — Qt selects
> the wayland plugin and the missing library never comes up.

Serial access needs your user in `dialout` on Linux:

```
sudo usermod -aG dialout $USER    # log out and back in
```

# Firmware

The tool drives a kit; it does not require you to build anything. A prebuilt
image for the nRF54LM20 DK is in `firmware/`, and the **Flash** button programs
it over `nrfutil`.

To build it yourself, `firmware/README.md` has the exact command and the two
traps in it — the nRF70 blobs must be fetched first, and `CONFIG_NRFX_GPPI=y` is
mandatory on the LM20 or `radio_test.c` will not link.

# Usage

The window scans on launch; there is nothing to press first.

| control | what it does |
| --- | --- |
| **Kit** | which DK to talk to. Rescan is pinned to whatever is picked here |
| **Rescan** | re-enumerate and re-probe |
| **Connect** | open or close the shell port |
| **Flash** | program the bundled hex onto the picked kit |
| state chip | green when a shell answered, otherwise why not |

Each tab is one shell registry. The count on the right reads `43 of 55 on this
image`: the table holds every command the SDK declares, and the probe decided
which of them this build actually has. The filter box narrows the list by name.

Clicking **Send** renders the command from the table and sends it. Replies land
in the log pane below.

# Testing

Two layers, because they answer different questions.

**Does the logic hold?** 135 tests, no hardware, no display:

```
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover tests
```

**Does it work on a kit?** One script, reads only — no OTP write, no
transmitter:

```
.venv/bin/python tools/bench_check.py --serial 1051810810
```

27 checks: the shell answers inside the discovery budget, every command the
tables claim is really present, `show_config` round-trips, `get_stats` is
synchronous, the deferred readings arrive, a deferred value does not leak into
the next command, and both failure wordings are what the code expects. Exits
non-zero on failure, so it can gate a release.

> Pass `--serial`. With more than one DK attached it refuses to guess, because
> probing the wrong kit wastes 1.5 s per silent port and its second VCOM tends to
> report an access error that reads as a fault.

Hardware checks are deliberately not `unittest` cases. A hardware test that
quietly passes when the hardware is absent is worse than no test.

# Overview

| file | responsibility |
| --- | --- |
| `commands/spec.py` | argument types the tables are built from |
| `commands/wifi.py` | `wifi_radio_test`, 55 names |
| `commands/shortrange.py` | root-level short-range table, 23 names |
| `commands/ficr.py` | FICR table, 7 commands, 6 OTP targets |
| `transport.py` | pyserial, ANSI and prompt stripping, reply modes |
| `nrfutil.py` | nRF Util wrapper, NDJSON parsing, programming |
| `discovery.py` | port scan, shell probe, `classify()` |
| `theme.py` | palette sampled from nRF Connect for Desktop |
| `widgets/factory.py` | argument spec to widget, row geometry |
| `widgets/command_tab.py` | generic tab, `request()` and `extra_groups()` hooks |
| `widgets/ficr_tab.py` | OTP writes behind typed confirmation |
| `app.py` | window, wiring, the `send_command` funnel |
| `tools/bench_check.py` | hardware verification |
| `docs/block0_findings.md` | what the bench actually said |

Commands are data. Adding a subcommand means adding a row to a table, not
placing a widget.

# Notes

> [!NOTE]
> Hard-won detail, not core to using the tool.

A reply does not always end when the prompt comes back. `get_temperature`
returns the prompt at 151 ms and the reading at about 1057 ms, as a deferred log
line, so reading until the prompt gets you nothing from any readback command. An
abandoned reading then lands in the *next* command's reply, which is why each
deferred command carries a `log_match` string naming its own answer.

`tx_power` reads back 30 where the published range is 0-24, so the table gives it
no ceiling. An invented bound blocks a value the device accepts.

`reg_domain` is `00`, a country code. Everything from `show_config` stays a
string; parsing that as an integer makes it `0`, a different thing to send back.

`init` discards every configuration parameter, so configure after it. The funnel
confirms before sending it: the natural order leaves a radio at defaults while
the screen still shows what you typed.

OTP writes are permanent, so every write is gated on typing the target field's
name. The shell takes a byte address while `rpu_if.h` names fields by word
offset, so `CALIB_XO` is word 76 but wants `0x130`. Pass the word offset and you
program a field four times lower in the map. `commands/ficr.py` carries both
numbers so nothing does that arithmetic by hand.

Presence is per-image, never per-board. The FICR shell is compiled out under
`CONFIG_NRF71_RADIO_TEST`, FEM commands need `CONFIG_FEM`, and nRF54LM20 has 28
of the 33 `output_power` steps and 9 of the 12 data rates its source declares.
Only a `READY` probe may hide anything; a probe that could not open the port
learned nothing about the image, so it shows everything rather than stranding you
in an empty window.

`docs/block0_findings.md` has the measurements these came from.

# Reference

- [`wifi_radio_test` subcommands](https://nrfconnectdocs.nordicsemi.com/ncs/latest/nrf/samples/wifi/radio_test/single_domain/radio_test_subcommands.html)
- [single-domain sample](https://nrfconnectdocs.nordicsemi.com/ncs/latest/nrf/samples/wifi/radio_test/single_domain/README.html)
- [short-range Radio test](https://nrfconnectdocs.nordicsemi.com/ncs/latest/nrf/samples/peripheral/radio_test/README.html)

In-tree sources for the three registries are named at the top of each file in
`nrf_radio_gui/commands/`.
