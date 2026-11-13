---
name: mac-feishu-attendance
description: 在 Apple Silicon Mac 上安装或排查 Avo 安卓模拟器、飞书极速打卡、公司 Wi-Fi 识别和受控定时激活。用于用户明确要求本机考勤自动化或验证时；不用于代替一般飞书审批、通讯或考勤记录查询。
---

# Mac 飞书考勤自动化

先确认用户是否已有 Avo、安卓数据、飞书登录和考勤规则；保留现有数据和用户指定的外置盘。读取当前状态，不要把用户名、账号、SSID、BSSID、精确位置、令牌或截图写入仓库或聊天。需要验证登录时，让用户自己输入验证码。

## 工作流程

1. 使用 [Avo 官方版本](https://github.com/nizwar/avo) 和 [飞书官方版本](https://www.feishu.cn/download)；核对芯片、macOS 版本、外置盘挂载和 Avo 实际数据位置。用 Avo 自带的存储迁移功能，不手工替换用户数据盘。用户可指定中文和安装位置。
2. 先在飞书「假勤 → 设置」核对上下班极速打卡、迟到时自动打卡和自动更新下班卡的设置。准确告知用户：[飞书要求在有效时间内将应用重新激活至前台](https://www.feishu.cn/hc/zh-CN/articles/360049067448-%E8%AE%BE%E7%BD%AE%E6%9E%81%E9%80%9F%E6%89%93%E5%8D%A1)，单纯保持应用运行不能证明会打卡。
3. 用只读检查对照 Mac 的实际连接、安卓 Wi-Fi 和飞书显示的考勤范围。SSID/BSSID 或定位缺失时不要臆测。若需要本机 Wi-Fi 同步，先读 [references/wifi-experiment.md](references/wifi-experiment.md)；这里的内核补丁仅适用于特定构建，且不能代替真实无线连接。
4. 如果用户要求定时激活，先确认具体时间、班次、休息日、请假、加班和失败处理；已有明确选择时直接沿用。按 [references/automation.md](references/automation.md) 实施：运行前核验账号、当天班次、实际 Wi-Fi、审批和已有记录，证据不足时跳过；不要盲点打卡按钮或无限重试。
5. 优先在用户提供的测试考勤组验证；分别记录页面是否识别 Wi-Fi、模拟器能否启动、极速打卡是否实际产生记录。按钮可点击不等于打卡成功。无需实际提交时，只做只读预演。
6. 报告持久化边界：用户登录后的 LaunchAgent、Mac 睡眠、外置盘、Wi-Fi 和飞书登录；明确模拟器重启、整机重启及真实公司考勤哪些测试已做、哪些尚未做。

`scripts/page_check.py` 只读取现有安卓无障碍 XML 并检查页面；`scripts/check_environment.py` 只读检查本机与 Avo；`scripts/patch_wifi_module.py` 仅生成版本受限的实验模块，不加载、不启用同步。按需运行并先查看 `--help`，不要把实际 XML、网络信息或配置提交到公开仓库。
