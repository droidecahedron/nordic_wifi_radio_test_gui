# firmware

# Hardware
`nRF54LM20 DK` (PCA10184) + `nRF7002-EB II` (PCA63571)

# Software
`nRF Connect SDK v3.4.0`, toolchain bundle `fbf7391cab`, west v1.5.0.

# Provenance

Source is `nrf/samples/wifi/radio_test/single_domain`. Single domain, not multi:
both the Wi-Fi and short-range radio tests run on the application core, and
`multi_domain/sample.yaml` only allows nRF7002 DK, nRF5340 DK, nRF52840 DK, and
nRF9160 DK — all either two-core or not a 54L.

nRF70 blobs must be fetched before the first build, or the Wi-Fi driver has
nothing to link:

```
west blobs fetch nrf_wifi
```

`modules/lib/nrf_wifi/zephyr/module.yml` declares five, and the radio test uses
`wifi_fw_bins/radio_test/nrf70.bin`, version 1.2.14.9, sha256 `e2f03b42…`.

```
west build -b nrf54lm20dk/nrf54lm20a/cpuapp \
  -- -DSHIELD=nrf7002eb2 -DSNIPPET=nrf70-wifi -Dsingle_domain_CONFIG_NRFX_GPPI=y
```

> `CONFIG_NRFX_GPPI=y` is not optional on the LM20. Without it `radio_test.c`
> fails to link with undefined references to `nrfx_gppi_ep_attach`,
> `nrfx_gppi_conn_enable`, and `nrfx_gppi_domain_conn_alloc`. The L15 gets the
> symbol from `single_domain/boards/nrf54l15dk_nrf54l15_cpuapp.conf`; there is no
> LM20 counterpart in that directory, which is why `single_domain/sample.yaml`
> passes it as an extra arg for the LM20 targets and not for the L15.

> `SNIPPET=nrf70-wifi` is a no-op here, kept only to match the documented L15
> command. `nrf/snippets/nrf70-wifi/snippet.yml` keys on board target and lists
> `nrf54h20dk` cpuapp/cpurad and `nrf54l15dk/nrf54l15/cpuapp` — no
> `nrf54lm20dk`, so it contributes nothing.

Sysbuild turns itself on without `--sysbuild`; the build tree comes out with
`_sysbuild/`, `domains.yaml`, and an image directory named `single_domain`.

# Artifact

| | |
| --- | --- |
| file | `wifi_radio_test_single_domain_nrf54lm20dk_nrf54lm20a_cpuapp_ncs-v3.4.0.hex` |
| built from | `build/single_domain/zephyr/zephyr.hex` |
| size | 537916 B |
| sha256 | `b04e9f2db797a00ed3e85179cd60fe709f27af44366b28ab93fd8363ffdb4285` |

There is no `merged.hex`. It only appears when `SB_CONFIG_MERGED_HEX_FILES` is
set, and `single_domain/sysbuild.conf` does not set it — one image, one core.
`domains.yaml` lists a single domain with `flash_order: single_domain`.

Link-time footprint, from the build that produced this hex:

| region | used | size | % |
| --- | --- | --- | --- |
| FLASH | 191196 B | 2036 KB | 9.17 |
| RAM | 139688 B | 511 KB | 26.70 |

# Notes

> Built for the `nrf54lm20a` variant. `single_domain/sample.yaml` also allows
> `nrf54lm20dk/nrf54lm20b/cpuapp`; a `b`-variant kit needs its own build.

Flashed to SN 1051810810 and driven. The shell answers on VCOM0 with all three
registries present, and the nRF7002 brings its bus up at 8 MHz. Full capture is
in `docs/block0_findings.md`.

```
nrfutil device program --firmware <hex> --serial-number 1051810810 \
  --family nrf54l \
  --options chip_erase_mode=ERASE_ALL,verify=VERIFY_READ,reset=RESET_SYSTEM
```

> `verify=VERIFY_HASH` is rejected by nrfutil 8.2.1 — `not supported yet in the
> probe-plugin`. Nothing is written when it fails. Use `VERIFY_READ`.

> `reset` defaults to `RESET_NONE` and `verify` to `VERIFY_NONE`. Omit them and
> the kit sits halted with an unverified image.

UNVERIFIED: no transmitter was exercised. `tx`, `rx`, `tx_tone`, and the sweep
commands were left alone, so nothing here says the radio radiates.
