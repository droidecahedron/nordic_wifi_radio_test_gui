#
# Copyright (c) 2026 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: Apache-2.0
#
"""nRF Util wrapper: enumerate kits, program, reset.

Verified against nrfutil 8.2.1 (350d1fd) on Linux with an nRF54LM20 DK.

`nrfutil device list --json` emits NDJSON, one JSON object per line, three lines
for a list operation:

    {"type":"task_begin", ...}
    {"type":"task_end",   ..., "data":{..., "data":{"devices":[...]}}}
    {"type":"info",             "data":{"devices":[...]}}

The device array therefore appears twice, nested one level deeper under
`task_end` than under `info`. This reads `info` first and falls back, rather than
walking the tree looking for a key called something like "devices".

> Do not find fields by substring. `serialPorts` contains `ports`, and the
> `traits` object has its own `serialPorts` key, so a loose search fills the port
> list with trait names. Everything below indexes exact keys.

> The JSON zero-pads serial numbers to 12 digits — `001051810810` — while the
> text output and the `--serial-number` argument both use the unpadded
> `1051810810`. `Device.serial` is the unpadded form so it can be passed straight
> back to nrfutil; `Device.serial_raw` keeps what the JSON said.
"""

import json
import shutil
import subprocess
from dataclasses import dataclass, field

EXECUTABLE = "nrfutil"
LIST_TIMEOUT_S = 30
PROGRAM_TIMEOUT_S = 300

# Settled on hardware. See docs/block0_findings.md.
#   verify=VERIFY_HASH is rejected by the probe-plugin: "not supported yet".
#     Nothing is written when it fails, so it costs a retry, not a bad image.
#   reset defaults to RESET_NONE and verify to VERIFY_NONE, so a bare program
#     leaves the kit halted with an unverified image.
#   chip_erase_mode=ERASE_ALL completes on nRF54L RRAM. Not compared against
#     ERASE_RANGES_TOUCHED_BY_FIRMWARE, so this is "works", not "optimal".
ERASE_MODES = ("ERASE_ALL", "ERASE_RANGES_TOUCHED_BY_FIRMWARE",
               "ERASE_CTRL_AP", "ERASE_NONE")
DEFAULT_ERASE = "ERASE_ALL"
DEFAULT_VERIFY = "VERIFY_READ"
DEFAULT_RESET = "RESET_SYSTEM"

# PCA number to a human name. deviceFamily is accurate but only names the family,
# so board identity comes from boardVersion.
# Source: nrf/doc/nrf/app_dev/board_names.rst at NCS v3.4.0.
BOARDS = {
    "PCA10184": "nRF54LM20 DK",
    "PCA10156": "nRF54L15 DK",
    "PCA10175": "nRF54H20 DK",
    "PCA10143": "nRF7002 DK",
    "PCA10188": "nRF54LV10 DK",
    "PCA10214": "nRF54LS05 DK",
}


class NrfutilError(RuntimeError):
    """nrfutil is missing, or a command came back non-zero."""


@dataclass(frozen=True)
class Port:
    path: str
    vcom: int

    def __str__(self):
        return f"{self.path} (VCOM{self.vcom})"


@dataclass(frozen=True)
class Device:
    serial: str
    serial_raw: str = ""
    board_version: str = ""
    family: str = ""
    ports: tuple = ()
    traits: tuple = ()

    @property
    def board_name(self):
        return BOARDS.get(self.board_version, self.board_version or "unknown board")

    @property
    def label(self):
        return f"{self.board_name} · {self.serial}"

    def port_for_vcom(self, vcom):
        for port in self.ports:
            if port.vcom == vcom:
                return port.path
        return None

    @property
    def shell_port(self):
        """VCOM0 carries the radio test shell; VCOM1 was silent on the LM20."""
        return self.port_for_vcom(0)


def available():
    return shutil.which(EXECUTABLE) is not None


def _run(args, timeout):
    if not available():
        raise NrfutilError(f"{EXECUTABLE} is not on PATH")
    try:
        done = subprocess.run([EXECUTABLE, *args], capture_output=True,
                              text=True, timeout=timeout)
    except subprocess.TimeoutExpired as err:
        raise NrfutilError(f"{EXECUTABLE} {' '.join(args)} timed out") from err
    return done


def version():
    done = _run(["--version"], LIST_TIMEOUT_S)
    first = done.stdout.strip().split("\n")[0] if done.stdout else ""
    return first or "unknown"


def _unpad(serial):
    """001051810810 -> 1051810810, the form nrfutil accepts back."""
    stripped = str(serial).lstrip("0")
    return stripped or str(serial)


def _port_from_json(entry):
    # comName and path were identical on Linux; path is the documented one.
    path = entry.get("path") or entry.get("comName")
    if not path:
        return None
    return Port(path=path, vcom=entry.get("vcom", 0))


def _device_from_json(entry):
    devkit = entry.get("devkit") or {}
    ports = tuple(
        p for p in (_port_from_json(e) for e in entry.get("serialPorts") or ())
        if p is not None
    )
    traits = tuple(sorted(k for k, v in (entry.get("traits") or {}).items() if v is True))
    raw = str(entry.get("serialNumber", ""))
    return Device(
        serial=_unpad(raw),
        serial_raw=raw,
        board_version=devkit.get("boardVersion", ""),
        family=devkit.get("deviceFamily", ""),
        ports=tuple(sorted(ports, key=lambda p: p.vcom)),
        traits=traits,
    )


def devices_from_ndjson(text):
    """Parse `nrfutil device list --json` output into Devices.

    Tolerates extra or reordered lines, and unparseable ones, because the NDJSON
    stream is a progress channel as much as a result.
    """
    from_info = None
    from_task = None
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if not isinstance(record, dict):
            continue
        data = record.get("data") or {}
        kind = record.get("type")
        if kind == "info" and isinstance(data.get("devices"), list):
            from_info = data["devices"]
        elif kind == "task_end":
            nested = data.get("data") or {}
            if isinstance(nested.get("devices"), list):
                from_task = nested["devices"]
    entries = from_info if from_info is not None else from_task
    if not entries:
        return ()
    return tuple(_device_from_json(e) for e in entries if isinstance(e, dict))


def list_devices():
    done = _run(["device", "list", "--json"], LIST_TIMEOUT_S)
    # A list with no kits attached still exits 0, so do not treat empty as error.
    devices = devices_from_ndjson(done.stdout)
    if not devices and done.returncode != 0:
        raise NrfutilError(done.stderr.strip() or "device list failed")
    return devices


def program(hex_path, serial, family=None, erase=DEFAULT_ERASE,
            verify=DEFAULT_VERIFY, reset=DEFAULT_RESET):
    """Program `hex_path` onto one kit, named by serial number.

    `family` is worth passing. It makes nrfutil refuse rather than program when
    the attached part is not what was expected, which matters on a bench with
    more than one kit.
    """
    options = f"chip_erase_mode={erase},verify={verify},reset={reset}"
    args = ["device", "program", "--firmware", str(hex_path),
            "--serial-number", str(serial), "--options", options]
    if family:
        args += ["--family", family]
    done = _run(args, PROGRAM_TIMEOUT_S)
    if done.returncode != 0:
        raise NrfutilError((done.stderr or done.stdout or "program failed").strip())
    return (done.stdout or "").strip()


def reset(serial):
    done = _run(["device", "reset", "--serial-number", str(serial)], LIST_TIMEOUT_S)
    if done.returncode != 0:
        raise NrfutilError((done.stderr or done.stdout or "reset failed").strip())
    return (done.stdout or "").strip()
