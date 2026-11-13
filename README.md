# Mac 飞书考勤自动化 Skill

一个面向 Codex 的 Skill，总结 Apple Silicon Mac、Avo 安卓模拟器和飞书原生极速打卡的配置与验证方法。它帮助操作人员区分“页面显示在范围内”“测试组打卡成功”和“真实考勤已成功”，并提供只读检查及一个受版本限制的 Wi-Fi 实验工具。

> **项目状态：实验性 Skill，不是一键安装器。** 不包含用户数据、考勤记录、原始安卓内核模块，也不提供开机后保证自动打卡的完整守护程序。只有确认实际班次、账号、网络、申请状态和用户意图后，才应配置真实考勤自动化。

> **兼容性风险：** 飞书可能识别模拟器环境或位置数据并给出虚拟定位、设备异常等提示；测试组成功和页面显示在范围内，都不能证明正式考勤会被认可。出现此类提示时应停止定时触发，改用真实手机或组织允许的飞书桌面端核对考勤。[飞书说明了考勤防作弊能力](https://www.feishu.cn/hc/zh-CN/articles/360049067437-%E4%B8%8D%E5%90%8C%E8%80%83%E5%8B%A4%E6%96%B9%E5%BC%8F%E7%9A%84%E5%8C%BA%E5%88%AB)。

## 我们验证过什么

1. 在外置盘安装 Avo 并保存安卓数据，配置中文与飞书登录。模拟器最初显示虚拟 Wi-Fi，飞书没有识别为指定网络。
2. 在 Mac 实际连接指定接入点时，使用本机 Wi-Fi 观察程序和临时虚拟驱动让安卓报告对应的标识；飞书页面随后显示进入范围。**只是界面识别，不等于真实无线桥接或真实考勤成功。**
3. 测试考勤组中，上班极速打卡成功；下班时一直保持飞书运行没有触发，重新打开飞书后测试组下班极速打卡成功。测试使用的是测试组的考勤条件，不能据此证明其他公司的 Wi-Fi 打卡成功。
4. 已验证模拟器停止后的启动、Wi-Fi 恢复和后台脚本打开飞书。首次真实公司定时打卡、整台 Mac 重启后的端到端恢复仍未验证；打开飞书可能立即触发极速打卡，因此不能在班次或账号未知时盲目启动。

Wi-Fi 驱动实验仅适用于特定 Android 模块和 9 字节 SSID；详见 [实验说明](mac-feishu-attendance/references/wifi-experiment.md)。飞书对极速打卡的条件以[官方说明](https://www.feishu.cn/hc/zh-CN/articles/360049067448-%E8%AE%BE%E7%BD%AE%E6%9E%81%E9%80%9F%E6%89%93%E5%8D%A1)及所在公司的规则为准。

## 安装 Skill

克隆本仓库到希望保存的位置，然后在 macOS 上创建 Codex Skill 链接：

```bash
git clone https://github.com/kelrenzhuli/mac-feishu-attendance-skill.git
mkdir -p ~/.codex/skills
ln -s "$(pwd)/mac-feishu-attendance-skill/mac-feishu-attendance" ~/.codex/skills/mac-feishu-attendance
```

如果同名 Skill 已存在，先检查并保留原内容。仓库位于外置盘时，使用前要先挂载该盘。新建 Codex 会话后，可通过 `$mac-feishu-attendance` 调用，或直接描述要安装、检查或排查的任务。

## 检查工具

```bash
python3 mac-feishu-attendance/scripts/check_environment.py --help
python3 mac-feishu-attendance/scripts/page_check.py --help
python3 mac-feishu-attendance/scripts/patch_wifi_module.py --help
```

页面检查需要自己采集的安卓 UI XML 和本地配置文件；这些可能包含个人信息，**不要提交或分享**。离线补丁工具不加载驱动；实际应用前必须解决版本校验、真实接入点同步、断线保护和恢复。

例如，复制 [示例页面配置](mac-feishu-attendance/references/page-config.example.json) 到仓库外的私有位置，改成本机的账号、班次和网络，采集当前飞书考勤页面的安卓 UI XML，再运行：

```bash
python3 mac-feishu-attendance/scripts/page_check.py \
  --xml /private/path/attendance.xml --config /private/path/config.json --event in
```

脚本只检查该版本页面上的部分条件；必须另行确认真实网络、审批、触发时间和结果。页面结构因飞书版本或考勤设置不同而变化时，无法识别就会拒绝通过。macOS Wi-Fi 探测程序的构建方式见 [探测器说明](mac-feishu-attendance/references/probe-build.md)。

离线测试无需登录飞书，也不会实际打卡：

```bash
python3 -m unittest discover -s tests -v
```

未提供原始模块时，驱动补丁的实文件测试会跳过。要对本机已验证的原始模块做离线测试，可将其路径放入 `AVO_TEST_MODULE` 环境变量；测试不会加载它。

```bash
AVO_TEST_MODULE=/private/path/virt_wifi-original.ko python3 -m unittest discover -s tests -v
```

## 组成

- [Skill 指令](mac-feishu-attendance/SKILL.md)：安装、检查和授权边界。
- [自动化与重启](mac-feishu-attendance/references/automation.md)：时段、审批、状态检查和恢复边界。
- [Wi-Fi 实验](mac-feishu-attendance/references/wifi-experiment.md)：已验证构建、探测与回退要求。
- [探测器说明](mac-feishu-attendance/references/probe-build.md)：macOS 权限和私有状态文件。
- `scripts/`：只读环境/页面检查、macOS Wi-Fi 探测源码和离线模块补丁工具。

本项目与 Avo、飞书均无官方隶属关系。请按所在组织的考勤制度使用；模拟器无法判断本人是否到岗。
