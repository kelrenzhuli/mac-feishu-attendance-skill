#!/usr/bin/env python3
"""Read-only check of a Feishu attendance UI dump; never interacts with UI."""
import argparse
import datetime as dt
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

PACKAGE = "com.ss.android.lark"
NO_GO = ("请假", "休假", "加班", "换班", "调班", "出差", "外出", "无需打卡", "休息日", "非工作日", "未加入考勤组")


class Ineligible(Exception):
    pass


def text_nodes(node):
    return [(n.get("text") or "").strip() for n in node.iter("node") if (n.get("text") or "").strip()]


def one_card(nodes, name):
    found = [node for node in nodes if node.get("resource-id") == name]
    if len(found) != 1:
        raise Ineligible("考勤卡片结构不明确")
    return found[0]


def check_page(root, config, event, when):
    nodes = list(root.iter("node"))
    if not nodes or any(n.get("package") != PACKAGE for n in nodes):
        raise Ineligible("页面不是唯一的飞书界面")
    texts = text_nodes(root)
    if texts.count(config["account_text"]) != 1 or texts.count(config["organization_text"]) != 1:
        raise Ineligible("账号或组织无法确认")
    groups = [t for t in texts if t in config["group_texts"]]
    if len(groups) != 1:
        raise Ineligible("考勤组无法确认")
    dates = [t for t in texts if re.fullmatch(r"\d{4}\.\d{2}\.\d{2}", t)]
    if dates != [when.strftime("%Y.%m.%d")]:
        raise Ineligible("页面日期不是今天")
    if any(word in text for text in texts for word in NO_GO):
        raise Ineligible("页面显示特殊考勤状态")
    first = text_nodes(one_card(nodes, "card0"))
    last = text_nodes(one_card(nodes, "last_clock_timeline_card"))
    start = [s for s in first if re.fullmatch(r"应上班\s+\d{2}:\d{2}", s)]
    end = [s for s in last if re.fullmatch(r"应下班\s+\d{2}:\d{2}", s)]
    if len(start) != 1 or len(end) != 1:
        raise Ineligible("班次时间无法确认")
    if start[0][-5:] != config["expected_start"] or end[0][-5:] != config["expected_end"]:
        raise Ineligible("班次与配置不符")
    card = first if event == "in" else last
    label = "上班打卡" if event == "in" else "下班打卡"
    if card.count(label) != 1 or any("已打卡" in s for s in card):
        raise Ineligible("打卡状态或按钮不明确")
    if event == "out" and not any(s.startswith("已打卡 ") for s in first):
        raise Ineligible("无法确认今天已有上班卡")
    if not any(s.startswith("已进入打卡范围") and s.endswith(config["wifi_ssid"]) for s in card):
        raise Ineligible("页面未确认指定 Wi-Fi 在范围内")
    clocks = [s for s in card if re.fullmatch(r"\d{2}:\d{2}:\d{2}", s)]
    if len(clocks) != 1:
        raise Ineligible("页面时钟不明确")
    try:
        h, minute, second = map(int, clocks[0].split(":"))
        shown = when.replace(hour=h, minute=minute, second=second, microsecond=0)
    except ValueError as exc:
        raise Ineligible("页面时钟无效") from exc
    if abs((when - shown).total_seconds()) > 45:
        raise Ineligible("页面时钟与当前时间不一致")
    return {"event": event, "start": config["expected_start"], "end": config["expected_end"]}


def load_config(path):
    config = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("配置必须是 JSON 对象")
    for key in ("account_text", "organization_text", "wifi_ssid", "expected_start", "expected_end", "timezone"):
        if not isinstance(config.get(key), str) or not config[key].strip():
            raise ValueError("配置缺少必要字段")
    groups = config.get("group_texts")
    if not isinstance(groups, list) or not groups or not all(isinstance(g, str) and g.strip() for g in groups):
        raise ValueError("配置缺少考勤组")
    for key in ("expected_start", "expected_end"):
        try:
            dt.datetime.strptime(config[key], "%H:%M")
        except ValueError as exc:
            raise ValueError("班次时间必须是 HH:MM") from exc
    return config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xml", required=True, type=Path, help="本地安卓 UI XML；仅供读取")
    parser.add_argument("--config", required=True, type=Path, help="保存在仓库外的私有 JSON 配置")
    parser.add_argument("--event", required=True, choices=("in", "out"))
    parser.add_argument("--at", help="测试用 ISO 时间，必须包含时区；默认使用当前时间")
    args = parser.parse_args()
    try:
        config = load_config(args.config)
        zone = ZoneInfo(config["timezone"])
        when = dt.datetime.fromisoformat(args.at) if args.at else dt.datetime.now(zone)
        if when.tzinfo is None:
            raise ValueError("时间需要包含时区")
        when = when.astimezone(zone)
        if args.xml.stat().st_size > 10 * 1024 * 1024:
            raise ValueError("UI 文件过大")
        result = check_page(ET.parse(args.xml).getroot(), config, args.event, when)
        print(json.dumps({"ok": True, "page": result, "note": "仅页面条件通过；仍需核验实际网络、审批及打卡结果。"}, ensure_ascii=False))
        return 0
    except Ineligible as exc:
        print(json.dumps({"ok": False, "reason": str(exc)}, ensure_ascii=False))
        return 1
    except (OSError, ValueError, KeyError, ZoneInfoNotFoundError, ET.ParseError):
        print(json.dumps({"ok": False, "reason": "配置、时间或页面数据不可用"}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    sys.exit(main())
