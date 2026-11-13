import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "mac-feishu-attendance/scripts/patch_wifi_module.py"
spec = importlib.util.spec_from_file_location("patch_wifi_module", SCRIPT)
patch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patch)


class PatcherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = self.root / "state.json"
        self.output = self.root / "output.ko"
        self.write_state()

    def write_state(self, **changes):
        state = {"ssid": "OfficeNet", "bssid": "02:00:00:00:00:01", "wifi_power": True,
                 "location_authorization": 3, "observed_at": time.time()}
        state.update(changes)
        self.state.write_text(json.dumps(state), encoding="utf-8")

    def run_patcher(self, source):
        return subprocess.run([sys.executable, str(SCRIPT), str(source), str(self.output),
                               "--wifi-state", str(self.state)], capture_output=True, text=True)

    def known_source(self):
        source = os.environ.get("AVO_TEST_MODULE")
        if not source:
            self.skipTest("AVO_TEST_MODULE not set; skipping test with a real original driver")
        path = Path(source)
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), patch.EXPECTED)
        return path

    def test_unsupported_binary_is_rejected_without_output(self):
        source = self.root / "unsupported.ko"
        source.write_bytes(b"not the supported driver")
        result = self.run_patcher(source)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.output.exists())

    def test_offline_patch_preserves_source_and_has_private_mode(self):
        source = self.known_source()
        before = source.read_bytes()
        result = self.run_patcher(source)
        self.assertEqual(result.returncode, 0, result.stderr)
        patched = self.output.read_bytes()
        self.assertEqual(source.read_bytes(), before)
        self.assertEqual(len(patched), len(before))
        self.assertNotEqual(patched, before)
        self.assertEqual(self.output.stat().st_mode & 0o777, 0o600)
        rodata, _ = patch.sections(patched)[".rodata"]
        self.assertEqual(patched[rodata + 0x418:rodata + 0x423], b"\x00\x09OfficeNet")
        result = self.run_patcher(source)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.output.read_bytes(), patched)

    def test_stale_unauthorized_and_unsupported_networks_are_rejected(self):
        source = self.known_source()
        for changed in ({"observed_at": time.time() - 30}, {"location_authorization": 2},
                        {"wifi_power": False}, {"ssid": "TooLongNetwork"},
                        {"bssid": "00:00:00:00:00:00"}, {"bssid": "01:00:00:00:00:01"}):
            with self.subTest(changed=changed):
                self.write_state(**changed)
                result = self.run_patcher(source)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
