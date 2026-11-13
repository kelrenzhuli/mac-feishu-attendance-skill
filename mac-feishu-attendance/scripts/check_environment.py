#!/usr/bin/env python3
"""Read-only Avo/Android health check. It does not start or change anything."""
import argparse
import json
from pathlib import Path
import platform
import shutil
import subprocess
import time


def run(args):
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=12, check=False)
    except (OSError, subprocess.SubprocessError):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--avoctl", help="Avo 安装目录内的官方 avoctl 路径")
    parser.add_argument("--adb", default=shutil.which("adb"), help="本机 adb 路径")
    parser.add_argument("--serial", default="127.0.0.1:5555", help="已连接的 Avo Android 序列号")
    parser.add_argument("--config", type=Path, help="私有 JSON，可含 wifi_ssid 和 wifi_bssid")
    parser.add_argument("--wifi-state", type=Path, help="本机授权探测器写入的 Wi-Fi 状态 JSON")
    args = parser.parse_args()
    result = {"platform": platform.system(), "architecture": platform.machine(),
              "macos": platform.mac_ver()[0] or None, "avo": "not_checked", "adb": "not_checked",
              "android_booted": None, "feishu_installed": None, "host_wifi_matches": None,
              "android_wifi_matches": None}
    expected = {}
    if args.config:
        try:
            expected = json.loads(args.config.read_text(encoding="utf-8"))
            if not isinstance(expected, dict):
                raise ValueError("invalid config")
        except (OSError, ValueError):
            print(json.dumps({"ok": False, "reason": "无法读取配置"}, ensure_ascii=False))
            return 2
    if args.avoctl:
        r = run([args.avoctl, "status"])
        if r and r.returncode == 0:
            try:
                result["avo"] = json.loads(r.stdout).get("state", "unknown")
            except (ValueError, AttributeError):
                result["avo"] = "unknown"
        else:
            result["avo"] = "unavailable"
    if args.wifi_state and expected.get("wifi_ssid") and expected.get("wifi_bssid"):
        try:
            state = json.loads(args.wifi_state.read_text(encoding="utf-8"))
            age = time.time() - float(state["observed_at"])
            result["host_wifi_matches"] = bool(
                0 <= age <= 10 and state.get("location_authorization") in (3, 4)
                and state.get("wifi_power") is True and state.get("ssid") == expected["wifi_ssid"]
                and str(state.get("bssid", "")).lower() == str(expected["wifi_bssid"]).lower())
        except (OSError, ValueError, TypeError, KeyError):
            result["host_wifi_matches"] = False
    if args.adb:
        prefix = [args.adb, "-s", args.serial]
        state = run(prefix + ["get-state"])
        if state and state.returncode == 0 and state.stdout.strip() == "device":
            result["adb"] = "connected"
            boot = run(prefix + ["shell", "getprop", "sys.boot_completed"])
            result["android_booted"] = bool(boot and boot.returncode == 0 and boot.stdout.strip() == "1")
            app = run(prefix + ["shell", "pm", "path", "com.ss.android.lark"])
            result["feishu_installed"] = bool(app and app.returncode == 0 and app.stdout.startswith("package:"))
            if expected.get("wifi_ssid") and expected.get("wifi_bssid"):
                wifi = run(prefix + ["shell", "cmd", "wifi", "status"])
                result["android_wifi_matches"] = bool(
                    wifi and wifi.returncode == 0
                    and f'Wifi is connected to "{expected["wifi_ssid"]}"' in wifi.stdout
                    and str(expected["wifi_bssid"]).lower() in wifi.stdout.lower())
        else:
            result["adb"] = "not_connected"
    print(json.dumps({"ok": True, "checks": result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
