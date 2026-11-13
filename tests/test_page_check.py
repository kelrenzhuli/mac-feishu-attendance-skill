import datetime as dt
import importlib.util
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo


SCRIPT = Path(__file__).resolve().parents[1] / "mac-feishu-attendance/scripts/page_check.py"
spec = importlib.util.spec_from_file_location("page_check", SCRIPT)
page_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(page_check)

CONFIG = {
    "account_text": "你好，示例用户",
    "organization_text": "示例组织",
    "group_texts": ["示例工作日打卡"],
    "wifi_ssid": "ExampleNet",
    "expected_start": "09:00",
    "expected_end": "18:00",
    "timezone": "Asia/Shanghai",
}
NOW = dt.datetime(2030, 4, 15, 8, 55, 0, tzinfo=ZoneInfo("Asia/Shanghai"))


def fake_page(event="in"):
    root = ET.Element("hierarchy")

    def add(parent, text="", rid="", package=page_check.PACKAGE):
        return ET.SubElement(parent, "node", {"text": text, "resource-id": rid, "package": package})

    for text in (CONFIG["account_text"], CONFIG["organization_text"], CONFIG["group_texts"][0], "2030.04.15"):
        add(root, text)
    first = add(root, rid="card0")
    last = add(root, rid="last_clock_timeline_card")
    add(first, "应上班 09:00")
    add(last, "应下班 18:00")
    if event == "in":
        add(first, "上班打卡")
        active = first
    else:
        add(first, "已打卡 08:55")
        add(last, "下班打卡")
        active = last
    add(active, "已进入打卡范围 ExampleNet")
    add(active, "08:55:00")
    return root


def find_text(root, text):
    return next(node for node in root.iter("node") if node.get("text") == text)


class PageCheckTests(unittest.TestCase):
    def assert_skipped(self, root, event="in"):
        with self.assertRaises(page_check.Ineligible):
            page_check.check_page(root, CONFIG, event, NOW)

    def test_matching_in_and_out_pages_pass(self):
        for event in ("in", "out"):
            with self.subTest(event=event):
                result = page_check.check_page(fake_page(event), CONFIG, event, NOW)
                self.assertEqual(result["event"], event)

    def test_wrong_account_date_shift_or_wifi_skip(self):
        for old, new in (
            (CONFIG["account_text"], "其他用户"),
            ("2030.04.15", "2030.04.14"),
            ("应下班 18:00", "应下班 17:30"),
            ("已进入打卡范围 ExampleNet", "不在打卡范围"),
        ):
            with self.subTest(value=old):
                root = fake_page()
                find_text(root, old).set("text", new)
                self.assert_skipped(root)

    def test_stale_clock_and_special_day_skip(self):
        root = fake_page()
        find_text(root, "08:55:00").set("text", "08:53:00")
        self.assert_skipped(root)
        root = fake_page()
        ET.SubElement(root, "node", {"package": page_check.PACKAGE, "text": "今日请假"})
        self.assert_skipped(root)

    def test_ambiguous_ui_skips(self):
        root = fake_page()
        find_text(root, "上班打卡").set("package", "another.app")
        self.assert_skipped(root)
        root = fake_page()
        ET.SubElement(root, "node", {"package": page_check.PACKAGE, "resource-id": "card0"})
        self.assert_skipped(root)

    def test_existing_punch_or_missing_morning_punch_skip(self):
        root = fake_page()
        ET.SubElement(find_text(root, "上班打卡"), "node", {"package": page_check.PACKAGE, "text": "已打卡 08:54"})
        self.assert_skipped(root)
        root = fake_page("out")
        find_text(root, "已打卡 08:55").set("text", "待打卡")
        self.assert_skipped(root, "out")


if __name__ == "__main__":
    unittest.main()
