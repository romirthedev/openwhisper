// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "OpenWhisper",
    platforms: [
        .macOS(.v13)
    ],
    targets: [
        .executableTarget(
            name: "OpenWhisper",
            path: "Sources/OpenWhisper",
            swiftSettings: [
                .unsafeFlags(["-strict-concurrency=complete"])
            ]
        )
    ]
)
