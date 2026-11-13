#!/usr/bin/env python3
"""Prepare a temporary experimental virt_wifi module from this Avo build.

This writes a separate file and never changes the original. The replacement
is tied to this exact driver build; it is not a general-purpose ELF patcher.
"""

import argparse
import hashlib
import json
import os
import re
import struct
import time
from pathlib import Path


EXPECTED = "51e82f889a7c4037099ac7f23c92322a36b31e953894ab4bf9c2967833833daa"


def sections(data):
    if data[:6] != b"\x7fELF\x02\x01":
        raise ValueError("Expected a little-endian ELF64 file")
    shoff = struct.unpack_from("<Q", data, 40)[0]
    entsize, count, names_index = struct.unpack_from("<HHH", data, 58)
    if entsize != 64:
        raise ValueError("Unexpected ELF section-header size")
    entries = [struct.unpack_from("<IIQQQQIIQQ", data, shoff + i * entsize) for i in range(count)]
    names = entries[names_index]
    strings = data[names[4] : names[4] + names[5]]
    result = {}
    for ent in entries:
        start = ent[0]
        end = strings.find(b"\0", start)
        name = strings[start:end].decode("ascii")
        result[name] = (ent[4], ent[5])
    return result


def replace_word(data, offset, expected, replacement):
    actual = struct.unpack_from("<I", data, offset)[0]
    if actual != expected:
        raise ValueError(f"Unexpected instruction at {offset:#x}: {actual:#x}")
    struct.pack_into("<I", data, offset, replacement)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--wifi-state", type=Path, required=True,
                        help="private, freshly observed CoreWLAN JSON; never a hard-coded identity")
    args = parser.parse_args()
    raw = args.source.read_bytes()
    if hashlib.sha256(raw).hexdigest() != EXPECTED:
        raise ValueError("The driver is not the exact build this experiment supports")
    state = json.loads(args.wifi_state.read_text(encoding="utf-8"))
    age = time.time() - float(state["observed_at"])
    if not (0 <= age <= 10 and state.get("wifi_power") is True
            and state.get("location_authorization") in (3, 4)
            and isinstance(state.get("ssid"), str)):
        raise ValueError("Host Wi-Fi observation is missing, stale or unauthorized")
    ssid = state["ssid"].encode("utf-8")
    if len(ssid) != 9:
        raise ValueError("This experiment supports only the tested nine-byte SSID")
    address = state.get("bssid")
    if not isinstance(address, str) or not re.fullmatch(r"(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}", address):
        raise ValueError("Invalid BSSID")
    bssid = bytes(int(part, 16) for part in address.split(":"))
    if bssid == bytes(6) or bssid[0] & 1:
        raise ValueError("BSSID is not a unicast access point")
    data = bytearray(raw)
    offsets = sections(data)
    init, _ = offsets[".init.text"]
    text, _ = offsets[".text"]
    rodata, _ = offsets[".rodata"]
    rela, rela_size = offsets[".rela.init.text"]

    # Initialize the fake access-point address with the supplied six bytes.
    first, last = struct.unpack("<IH", bssid)
    patches = {
        0x1C: (0x528000C1, 0x52800008 | ((first & 0xFFFF) << 5)),
        0x20: (0xAA1303E0, 0x72A00008 | ((first >> 16) << 5)),
        0x24: (0x94000000, 0xB9000268),  # str w8, [x19]
        0x28: (0x39400268, 0x52800008 | (last << 5)),
        0x34: (0x121E1508, 0x79000A68),  # strh w8, [x19, #4]
        0x38: (0x321F0108, 0xD503201F),
        0x3C: (0x39000268, 0xD503201F),
    }
    for at, (old, new) in patches.items():
        replace_word(data, init + at, old, new)

    # Remove the original get_random_bytes relocation from the new store.
    found = 0
    for at in range(rela, rela + rela_size, 24):
        location, info, _ = struct.unpack_from("<QQq", data, at)
        if location == 0x24:
            if (info & 0xFFFFFFFF) != 283:  # R_AARCH64_CALL26
                raise ValueError("Unexpected init relocation")
            struct.pack_into("<Q", data, at + 8, 0)  # R_AARCH64_NONE
            found += 1
    if found != 1:
        raise ValueError("Could not identify the init relocation")

    # The nine-byte name fits in existing padding before the next object.
    name_at = rodata + 0x418
    if data[name_at : name_at + 10] != b"\x00\x08VirtWifi":
        raise ValueError("Unexpected original SSID object")
    if any(data[name_at + 10 : name_at + 16]):
        raise ValueError("The expected SSID padding is in use")
    data[name_at : name_at + 11] = bytes((0, len(ssid))) + ssid
    replace_word(data, text + 0x828, 0x52800149, 0x52800169)  # IE length: 10 -> 11
    replace_word(data, text + 0x2B0, 0x52800149, 0x52800169)  # inlined scan path
    replace_word(data, text + 0xE28, 0x7100217F, 0x7100257F)  # name length: 8 -> 9

    # The connection check compares the first eight bytes after its length check.
    value = int.from_bytes(ssid[:8], "little")
    for at, old, shift in [
        (0xE30, 0xD28D2ACC, 0),
        (0xE38, 0xF2AE8E4C, 16),
        (0xE3C, 0xF2CD2AEC, 32),
        (0xE40, 0xF2ED2CCC, 48),
    ]:
        immediate = (value >> shift) & 0xFFFF
        base = 0xD280000C if shift == 0 else 0xF280000C | ((shift // 16) << 21)
        replace_word(data, text + at, old, base | (immediate << 5))

    # Recheck immediately before writing: a stale observation is not evidence
    # that the host is still on this access point. Runtime guards are still
    # required before loading and while using the resulting module.
    if not 0 <= time.time() - float(state["observed_at"]) <= 10:
        raise ValueError("Host Wi-Fi observation became stale")
    fd = os.open(args.destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as output:
        output.write(data)
    print(f"Prepared temporary driver: {args.destination}")
    print(f"SHA-256: {hashlib.sha256(data).hexdigest()}")
    print("Original driver remains unchanged. Loading it is a separate step.")


if __name__ == "__main__":
    main()
