# macOS Wi-Fi 探测器

`scripts/AvoWifiProbe.swift` 使用 CoreWLAN 读取 Mac 的当前 SSID 和 BSSID，不读取坐标或密码，也不发出网络请求。macOS 通常要求定位权限才能返回 Wi-Fi 标识；只有用户同意后才请求。不同 macOS 版本的应用签名和定位授权行为可能不同，不能假设下面的构建示例对每台机器均已验证。

以下示例创建一个新的私有应用包；如果目标已存在，先保留并检查原文件：

```bash
probe_app="$HOME/Applications/Avo Wi-Fi Probe Example.app"
if [ -e "$probe_app" ]; then
  echo '目标已存在，请先检查并选择新路径'
else
  mkdir -p "$probe_app/Contents/MacOS"
  cat > "$probe_app/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleExecutable</key><string>AvoWifiProbe</string>
  <key>CFBundleIdentifier</key><string>example.mac-feishu-attendance.wifi-probe</string>
  <key>CFBundleName</key><string>Avo Wi-Fi Probe Example</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>NSLocationWhenInUseUsageDescription</key><string>读取当前 Wi-Fi 名称和接入点，以验证考勤网络。</string>
</dict></plist>
PLIST
  xcrun swiftc mac-feishu-attendance/scripts/AvoWifiProbe.swift -o "$probe_app/Contents/MacOS/AvoWifiProbe"
  codesign --sign - "$probe_app"
fi
```

经用户允许后，可先创建用户可读写的私有目录并请求定位权限。`--watch` 每三秒更新状态；没有输出路径时会拒绝运行。临时状态包含网络标识，应设为仅当前用户可读，并且只保存在本机。

```bash
private_dir="$HOME/Library/Application Support/FeishuAttendancePrivate"
mkdir -p "$private_dir"
chmod 700 "$private_dir"
export AVO_WIFI_PROBE_OUTPUT="$private_dir/wifi-state.json"
"$probe_app/Contents/MacOS/AvoWifiProbe" --request-location
"$probe_app/Contents/MacOS/AvoWifiProbe" --watch
```

可用 `--interface NAME` 明确指定已确认的 Wi-Fi 接口，否则使用 CoreWLAN 默认接口。先检查定位权限、Wi-Fi 开关、SSID/BSSID 和采样时间是否有效；不要把状态文件上传。探测器只提供一次本地观察，不能保证接入点始终未变，也不包含实际加载驱动或断线回退程序。
