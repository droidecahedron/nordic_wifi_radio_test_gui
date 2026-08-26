# nRF Radio Test GUI

Drive the nRF Connect SDK [radio test shells](https://nrfconnectdocs.nordicsemi.com/ncs/latest/nrf/samples/wifi/radio_test/single_domain/README.html) by clicking instead of typing.

<img width="991" height="734" alt="image" src="https://github.com/user-attachments/assets/a94e76b9-580e-4630-b739-afbdbdf67230" />

*Note* : This is an unofficial pyqt wrapper for the sample.

## Requirements

### Hardware
- `nRF54LM20 DK` (PCA10184)
- `nRF7002-EB II` (PCA63571)

### Software
- `nrfutil 8.2.1` with the `device` subcommand on `PATH`
- `nRF Connect SDK v3.4.0`, only to rebuild the firmware

> [!NOTE]
> Nothing is keyed to that board. The tool asks the kit which commands it has, so
> any image presenting the radio test shell on a VCOM will drive. An nRF54L15 DK
> works, and so do nRF71 and coex builds.

## Install

Download one file and run it. No clone, no Python, no venv.

| platform | file | first run |
| --- | --- | --- |
| Windows | `nrf-radio-test-windows-x86_64.exe` | double-click. SmartScreen: More info, Run anyway |
| macOS Apple silicon | `nrf-radio-test-macos-arm64.app.zip` | unzip, right-click Open |
| macOS Intel | `nrf-radio-test-macos-x86_64.app.zip` | unzip, right-click Open |
| Linux | `nrf-radio-test-linux-x86_64` | `chmod +x`, then run |

One binary per platform in [Releases](../../releases), since PyInstaller has no
cross-compile. Verify a download against a kit:

```
nrf-radio-test --selftest --serial 1051810810
```

> [!NOTE]
> `nrfutil` backs kit enumeration and the Flash button. Driving an already
> flashed kit needs only the serial port.

> [!NOTE]
> Unsigned, so the first launch is blocked. macOS also accepts
> `xattr -d com.apple.quarantine <file>`. No sandbox flag is needed; these are
> plain executables rather than Electron apps.
> The Linux build links its runner's glibc, Ubuntu 22.04, so it needs 22.04 or
> newer. An AppImage would not change that, since it bundles no libc.
> Serial access on Linux wants `sudo usermod -aG dialout $USER` and a fresh login.

## Firmware

`firmware/` holds a prebuilt nRF54LM20 DK image; **Flash** programs it.
`firmware/README.md` has the build command and its two traps: fetch the nRF70
blobs first, and `CONFIG_NRFX_GPPI=y` or `radio_test.c` will not link.

## Usage

The window scans on launch.

| control | effect |
| --- | --- |
| **Kit** | which DK to talk to. Rescan follows this selection |
| **Rescan** | re-enumerate and re-probe |
| **Connect** | open or close the shell port |
| **Flash** | program the bundled hex onto the selected kit |
| state chip | green once a shell answered, otherwise the reason |

One tab per shell registry. `43 of 55 on this image` means the table declares 55
and the probe found 43. **Send** renders the command; replies land in the log.


## Software description

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
| `benchcheck.py` | hardware verification, also `--selftest` |
| `docs/block0_findings.md` | what the bench measured |

Commands are data. Adding a subcommand is a table row, never widget code.

## Testing

| layer | command | covers |
| --- | --- | --- |
| headless | `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover tests` | 137 tests, no hardware, no display |
| bench | `.venv/bin/python tools/bench_check.py --serial 1051810810` | 27 checks on a real kit, reads only |

Both exit non-zero on failure. Hardware checks stay out of `unittest`, since one
that passes with no kit attached is worse than no test.

> [!IMPORTANT]
> Pass `--serial`. With two DKs attached it refuses to guess. Probing the wrong
> kit costs 1.5 s per silent port and its second VCOM reports an access error
> that reads as a fault.


## Notes

> [!NOTE]
> Bench detail. `docs/block0_findings.md` carries the measurements.

| behaviour | consequence |
| --- | --- |
| `get_temperature` returns the prompt at 151 ms and its reading at ~1057 ms | reading until the prompt yields nothing from any readback command |
| an abandoned reading lands in the following command's reply | every deferred command declares a `log_match` naming its own answer |
| `tx_power` reads back 30 where docs say 0-24 | the table gives it no ceiling, since an invented bound blocks a working value |
| `reg_domain` is `00`, a country code | `show_config` values stay strings; as an integer it becomes `0` |
| `init` discards every configuration parameter | configure afterwards. The funnel confirms first |
| OTP writes cannot be undone | each one is gated on typing the target field name |
| the shell takes a byte address, `rpu_if.h` lists word offsets | `CALIB_XO` is word 76 and wants `0x130`. `commands/ficr.py` carries both |
| presence is per-image | nRF54LM20 has 28 of 33 `output_power` steps and 9 of 12 data rates |
| a failed probe learned nothing about the image | only a `READY` probe may hide anything, so a dead port shows every command |

## Reference

- [`wifi_radio_test` subcommands](https://nrfconnectdocs.nordicsemi.com/ncs/latest/nrf/samples/wifi/radio_test/single_domain/radio_test_subcommands.html)
- [single-domain sample](https://nrfconnectdocs.nordicsemi.com/ncs/latest/nrf/samples/wifi/radio_test/single_domain/README.html)
- [short-range Radio test](https://nrfconnectdocs.nordicsemi.com/ncs/latest/nrf/samples/peripheral/radio_test/README.html)

Each file in `nrf_radio_gui/commands/` names its in-tree source at the top.

## Building from source

Only needed to change the tool. Users download a binary instead.

Needs `Python 3.12`, and pip pulls `PyQt6 6.11.0` and `pyserial 3.5`.

```
git clone git@github.com:droidecahedron/nordic_wifi_radio_test_gui.git
cd nordic_wifi_radio_test_gui
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m nrf_radio_gui
```

Windows uses `.venv\Scripts\python.exe`.

> [!IMPORTANT]
> Run `.venv/bin/python`. Plain `python3 -m nrf_radio_gui` picks the system
> interpreter and fails with `ModuleNotFoundError: No module named 'PyQt6'`.
> Ubuntu 24.04 on X11 also needs `sudo apt install libxcb-cursor0` for Qt 6 to
> load its `xcb` plugin. Wayland selects its own plugin and never asks.

Build a standalone binary for the platform you are on:

```
.venv/bin/pyinstaller nrf_radio_gui.spec --noconfirm
```

`NRF_RADIO_GUI_CONSOLE=1` builds a console variant, so a traceback is visible in
a frozen Windows or macOS build.
