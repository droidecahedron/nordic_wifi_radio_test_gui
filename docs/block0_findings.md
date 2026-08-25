# Block 0 — bench smoke

# Hardware
`nRF54LM20 DK` (PCA10184, SN 1051810810) + `nRF7002-EB II` (PCA63571)

An `nRF54H20 DK` (PCA10175, SN 1051159862) shares the bench on `ttyACM0`/`ttyACM1`
and was not touched. Every `nrfutil` call carried `--serial-number 1051810810`
and `--family nrf54l`.

# Software
`nRF Connect SDK v3.4.0`, Zephyr 4.4.0 as reported by the kit, nrfutil 8.2.1
(350d1fd), west v1.5.0, toolchain bundle `fbf7391cab`.

Firmware is `firmware/wifi_radio_test_single_domain_nrf54lm20dk_nrf54lm20a_cpuapp_ncs-v3.4.0.hex`,
sha256 `b04e9f2d…`. See `firmware/README.md` for how it was built.

# Flashing

```
nrfutil device program --firmware <hex> --serial-number 1051810810 \
  --family nrf54l \
  --options chip_erase_mode=ERASE_ALL,verify=VERIFY_READ,reset=RESET_SYSTEM
```

Exit 0, no output on success.

> `verify=VERIFY_HASH` is rejected by nrfutil 8.2.1: `verify=VERIFY_HASH is not
> supported yet in the probe-plugin (NotSupported)`. Nothing is written when it
> fails, so this costs a retry rather than a half-programmed part. Use
> `VERIFY_READ`.

> `reset` defaults to `RESET_NONE` and `verify` to `VERIFY_NONE`. Flash without
> naming them and the kit sits halted with an unverified image.

`chip_erase_mode=ERASE_ALL` completed on RRAM without complaint. That settles
the erase-mode row as "works", not as "is optimal" — `ERASE_RANGES_TOUCHED_BY_FIRMWARE`
was not tried, so there is no comparison to report.

# What answered

| | |
| --- | --- |
| shell | `/dev/ttyACM2`, VCOM0 |
| silent | `/dev/ttyACM3`, VCOM1, zero bytes to a 3 s probe |
| first byte | 100-101 ms, consistent across 9 consecutive commands |

Before flashing, both VCOMs returned zero bytes. That is the negative control for
the probe: silence means no shell, not a dead port.

Prompt is `uart:~$ ` wrapped in SGR colour and followed by cursor moves —
`\x1b[1;32m`, `\x1b[m`, `\x1b[8D`, `\x1b[J`. Stripping ANSI is not optional.

The nRF7002 announces its bus at boot:

```
<inf> wifi_nrf_bus: SPIM spi@c8000: freq = 8 MHz
```

# Readbacks are asynchronous

This is the finding that changes the design. `get_temperature`, arrival times
relative to send:

```
  50 ms   echo of the command
 151 ms   prompt returns
1057 ms   <inf> wifi_nrf: The temperature is = 30 degree celsius
```

The prompt comes back roughly 900 ms before the answer does, and the answer
arrives as a deferred log line rather than as command output. Read until the
prompt reappears and `get_temperature`, `get_voltage`, and `get_rf_rssi` all
return nothing.

Measured twice: 31 °C then 30 °C, and `get_rf_rssi` returned 7. Both values
showed up only on the *following* command in the first run, which is what
prompted the second measurement.

Every reply mode measured so far, by arrival time relative to send:

| command | mode | value arrives |
| --- | --- | --- |
| `get_temperature` | deferred | ~1057 ms, `<inf>` log line |
| `get_voltage` | deferred | ~1008 ms, `battery voltage is = 3690 mV` |
| `get_rf_rssi` | deferred | log line |
| `compute_optimal_xo_val` | deferred | ~1058 ms, `Best XO value is = 0` |
| `show_config` | sync | 50 ms, before the prompt |
| `get_stats` | sync | 50 ms, before the prompt |
| `otp_get_status` | sync | before the prompt |
| `parameters_print` | sync | before the prompt |

So the transport needs both paths and cannot pick one globally.

> `get_stats` is **not** log-only. It returns the five PHY counters as ordinary
> command output ahead of the prompt:
>
> ```
> ************* PHY STATS ***********
> rssi_avg = 0 dBm
> ofdm_crc32_pass_cnt=0
> ofdm_crc32_fail_cnt=0
> dsss_crc32_pass_cnt=0
> dsss_crc32_fail_cnt=0
> ```
>
> Note the formatting is inconsistent — `rssi_avg` is spaced around its `=` and
> carries a unit, the four counters are not. Anything parsing this must tolerate
> both.

# The shell advertises a rate it will not take

`tx_pkt_rate` help lists `1, 2, 5.5, 11, 6, 9, 12, 18, 24, 36, 48, 54`. Send the
one non-integer and it is refused:

```
wifi_radio_test tx_pkt_rate 5.5
Invalid Legacy Rate value: 5
Invalid value 5
```

The parser truncates `5.5` to `5`, then rejects `5` because 5 is not a legacy
rate. Readback confirms nothing changed — `tx_pkt_rate = 6`, its prior value.
5.5 Mbps is a real 802.11b rate, so the help is right and the parser is short an
integer scaling step.

`tx_power 30` and `reg_domain 00` were both accepted in the same run and read
back unchanged, so this is specific to `tx_pkt_rate` rather than general argument
handling.

# Two different failure wordings

A bad root command is terse:

```
this_is_not_a_command: command not found
```

A bad *subcommand* dumps the entire help tree instead — 4572 bytes for
`wifi_radio_test not_a_subcommand`. Anything that logs raw replies needs to
expect a screenful from a single typo.

# Runtime command tables

The image gates large parts of all three tables, so what the kit has is not what
the sources list.

| registry | in source | on this image |
| --- | --- | --- |
| `wifi_radio_test` | 56 | 43 |
| root, unprefixed | 23 | present, `parameters_print` verified |
| `wifi_radio_ficr_prog` | 7 | present |

What the runtime help proves about the build:

- `CONFIG_NRF71_RADIO_TEST` is **not** set — `init` takes one arg (primary
  channel), `set_ant_gain` and `set_edge_bo` are present, and none of
  `rx_bss_color`, `rx_station_id`, `tx_dcm`, `tx_doppler`, `tx_106_tone`,
  `tx_fec_coding` appear.
- `CONFIG_NRF70_2_4G_ONLY` is **not** set — `tx_pkt_tput_mode` offers `2 - VHT mode`.
- `CONFIG_NRF70_SR_COEX` and `..._RF_SWITCH` are **not** set — `config_pta` and
  `sr_ant_switch_ctrl` are both absent.

Gate the UI on the probe, never on the board name.

# show_config

31 parameters, verbatim:

```
tx_pkt_tput_mode = 0        tx_pkt_num = -1             rx_capture_length = 0
tx_pkt_sgi = 0              tx_pkt_len = 1400           rx_capture_timeout = 0
tx_pkt_preamble = 0         tx_power = 30               wlan_ant_switch_ctrl = 0
tx_pkt_mcs = 0              he_ltf = 2                  tx_pkt_cw = 15
tx_pkt_rate = 6             he_gi = 2                   reg_domain = 00
tx_pkt_gap = 0              xo_val = 46                 bypass_reg_domain = 0
phy_calib_rxdc = 1          init = 1                    ru_tone = 26
phy_calib_txdc = 1          tx = 0                      ru_index = 1
phy_calib_txpow = 0         rx = 0
phy_calib_rxiq = 1          tx_tone_freq = 0
phy_calib_txiq = 1          rx_lna_gain = 0
```

> `tx_power = 30`. The subcommand help says only `<val> - Value in dBm`, and the
> published table says 0-24. The device reports 30. Prefer the readback and do
> not clamp to 24.

> `reg_domain = 00` is a country code. Parse it as an integer and it becomes `0`,
> which is a different value to send back. Keep everything from `show_config` as
> a string.

Two `show_config` keys do not match a command name, so readback cannot map
one-to-one:

| `show_config` key | command |
| --- | --- |
| `xo_val` | `set_xo_val` |
| `init` | `init`, but the field is state and the command takes a channel |

# FICR

Present, and the OTP is writable on this part:

```
Checking OTP PROTECT Region......
OTP Region is open for R/W

QSPI Keys are not programmed in OTP
MAC0 Address is programmed in OTP
MAC1 Address is programmed in OTP
CALIB_XO is programmed in OTP
```

MAC0, MAC1, and CALIB_XO are already burned. Nothing in this session wrote OTP.

# Short range

Root-level registry answers, confirming the unprefixed table on hardware:

```
Data rate: NRF_RADIO_MODE_BLE_1MBIT
TX power : 0 dBm
Transmission pattern: TRANSMIT_PATTERN_RANDOM
Start Channel: 0
End Channel: 80
Time on each channel: 10 ms
Duty cycle: 50 percent
```

# nrfutil device list

Raw, both kits attached:

```
1051159862
Product         J-Link
Board version   PCA10175
Ports           /dev/ttyACM0, vcom: 0
                /dev/ttyACM1, vcom: 1
Traits          boardController, devkit, jlink, seggerUsb, serialPorts, usb

1051810810
Product         J-Link
Board version   PCA10184
Ports           /dev/ttyACM2, vcom: 0
                /dev/ttyACM3, vcom: 1
Traits          boardController, devkit, jlink, seggerUsb, serialPorts, usb

Supported devices found: 2
```

`--json` in trailing position works. Output is NDJSON, three lines:
`{"type":"task_begin"}`, `{"type":"task_end", …}`, `{"type":"info", …}`. Devices
appear twice — under `task_end` at `data.data.devices` and under `info` at
`data.devices`.

Per-device keys actually present:

```
serialNumber, id, probe
boardController { productId, serialNumber, vendorId }
devkit          { boardVersion, deviceFamily }
serialPorts[]   { comName, path, vcom, interfaceNumber,
                  manufacturer, productId, serialNumber, vendorId }
traits          { boardController, broken, devkit, jlink, mcuBoot, modem,
                  nordicDfu, nordicUsb, seggerUsb, serialPorts, usb, ... }
usb             { device{...}, interfaces[], manufacturer, osDevicePath,
                  product, serialNumber }
```

> The substring trap is real. `serialPorts` contains `ports`, and `traits` has
> its own `serialPorts` key. Match field labels on word boundaries or the port
> list fills with trait names.

> `devkit.deviceFamily` reports `NRF54H_FAMILY` for the PCA10175 and is the only
> family field in the payload. Board identity is more reliably read from
> `devkit.boardVersion` — PCA10175 is the nRF54H20 DK and PCA10184 the nRF54LM20
> DK, per `nrf/doc/nrf/app_dev/board_names.rst`.

# Handoff "Not verified" table, resolved

| assumption | outcome |
| --- | --- |
| 1.5 s probe reply window is enough | **confirmed with margin.** 100-101 ms measured, 9 for 9. No retune needed |
| 1.5 s post-flash reprobe delay | **not measured.** No reprobe path exists yet |
| `ERASE_ALL` right for nRF54L RRAM | **works.** Not compared against the alternatives |
| `nrfutil device list --json` key names | **captured**, above |
| `--json` position | **trailing works.** Leading not tried |
| `tx_power` clamp, doc 0-24 vs 30 | **confirmed 30 on hardware.** Do not clamp to 24 |
| Zephyr not-found wording | **captured.** `<cmd>: command not found`, and a bad subcommand dumps help instead |
| every `output_power` step on nRF54L | **not tested.** Needs stepping the short-range table |

# Open

Log timestamps and `kernel uptime` do not share an epoch. Two samples:

| uptime | log stamp | offset |
| --- | --- | --- |
| 193825 ms | 30554 ms | 163.3 s |
| 313044 ms | 151285 ms | 161.8 s |

Rates agree — both advanced ~120 s across the same interval — so the offset looks
constant at roughly 162 s rather than a clock running at the wrong speed. Cause
not established, and two samples is not enough to call it fixed. Log stamps are
usable for relative timing between lines; do not treat them as uptime.

UNVERIFIED: nothing here exercised a transmitter. `tx`, `rx`, `tx_tone`,
`get_stats`, and the sweep commands were all left alone, so this says nothing
about whether the radio actually radiates.
