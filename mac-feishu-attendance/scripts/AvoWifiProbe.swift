import AppKit
import CoreLocation
import CoreWLAN
import Darwin
import Foundation

// CoreWLAN identity only: no coordinates, passwords, or network requests.
// Use a signed app bundle with NSLocationWhenInUseUsageDescription to request
// access. The identity belongs in a private file, never a shared log or repo.
final class LocationAuthorization: NSObject, CLLocationManagerDelegate {
    private let manager = CLLocationManager()
    private(set) var completed = false

    override init() {
        super.init()
        manager.delegate = self
    }

    func request() {
        manager.requestWhenInUseAuthorization()
    }

    func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        if manager.authorizationStatus != .notDetermined {
            completed = true
        }
    }
}

let arguments = Array(CommandLine.arguments.dropFirst())
if arguments.contains("--help") {
    print("Usage: AvoWifiProbe [--request-location] [--watch] [--interface NAME]")
    print("Set AVO_WIFI_PROBE_OUTPUT to a private local file; --watch requires it.")
    exit(0)
}

let watching = arguments.contains("--watch")
let outputPath = ProcessInfo.processInfo.environment["AVO_WIFI_PROBE_OUTPUT"]
if watching && (outputPath == nil || outputPath!.isEmpty) {
    fputs("--watch requires AVO_WIFI_PROBE_OUTPUT\n", stderr)
    exit(2)
}

var interfaceName: String?
if let index = arguments.firstIndex(of: "--interface") {
    guard index + 1 < arguments.count else {
        fputs("--interface requires a name\n", stderr)
        exit(2)
    }
    interfaceName = arguments[index + 1]
}

// Set a restrictive mode on the temporary file created by atomic writes.
umask(0o077)
let app = NSApplication.shared
app.setActivationPolicy(.accessory)
app.finishLaunching()
let authorization = LocationAuthorization()
if arguments.contains("--request-location") {
    app.activate(ignoringOtherApps: true)
    authorization.request()
    let deadline = Date().addingTimeInterval(45)
    while !authorization.completed && Date() < deadline {
        RunLoop.current.run(until: Date().addingTimeInterval(0.2))
    }
}
RunLoop.current.run(until: Date().addingTimeInterval(1.5))

repeat {
    let client = CWWiFiClient.shared()
    let wifi = interfaceName.map { client.interface(withName: $0) } ?? client.interface()
    let info: [String: Any] = [
        "location_authorization": CLLocationManager().authorizationStatus.rawValue,
        "wifi_power": wifi?.powerOn() ?? false,
        "interface": wifi?.interfaceName as Any? ?? NSNull(),
        "ssid": wifi?.ssid() as Any? ?? NSNull(),
        "bssid": wifi?.bssid() as Any? ?? NSNull(),
        "observed_at": Date().timeIntervalSince1970,
    ]
    let json = try JSONSerialization.data(withJSONObject: info, options: [.sortedKeys])
    if let path = outputPath, !path.isEmpty {
        try json.write(to: URL(fileURLWithPath: path), options: .atomic)
    } else {
        FileHandle.standardOutput.write(json)
        FileHandle.standardOutput.write(Data([0x0a]))
    }
    if watching {
        RunLoop.current.run(until: Date().addingTimeInterval(3))
    }
} while watching
