import SwiftUI
import AppKit

struct SetupView: View {
    var onInstallComplete: () -> Void

    @State private var isInstalling = false
    @State private var installStatus = "Ready to install"
    @State private var installComplete = false
    @State private var installFailed = false

    var body: some View {
        VStack(spacing: 20) {
            Image(systemName: "mic.fill")
                .font(.system(size: 40))
                .foregroundColor(.black)

            Text("Welcome to OpenWhisper")
                .font(.system(size: 22, weight: .bold))
                .foregroundColor(.black)

            Text("OpenWhisper needs to install a few dependencies.\nThis takes about 5 minutes on first run.")
                .font(.system(size: 13))
                .foregroundColor(.black.opacity(0.6))
                .multilineTextAlignment(.center)

            VStack(alignment: .leading, spacing: 6) {
                installRow("Xcode Command Line Tools")
                installRow("Homebrew")
                installRow("Python 3.12 + faster-whisper")
                installRow("Ollama + llama3.2 AI model")
            }
            .padding(.vertical, 8)

            if installComplete {
                Text("Installation complete!")
                    .font(.system(size: 14, weight: .medium))
                    .foregroundColor(.green)

                Button("Launch OpenWhisper") {
                    onInstallComplete()
                }
                .buttonStyle(.borderedProminent)
                .tint(.black)
            } else if installFailed {
                Text(installStatus)
                    .font(.system(size: 12))
                    .foregroundColor(.red)
                    .lineLimit(3)

                HStack(spacing: 12) {
                    Button("Retry") {
                        runInstaller()
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(.black)

                    Button("Install via Terminal") {
                        copyTerminalCommand()
                    }
                    .buttonStyle(.bordered)
                }
            } else if isInstalling {
                HStack(spacing: 8) {
                    ProgressView()
                        .scaleEffect(0.8)
                    Text(installStatus)
                        .font(.system(size: 12))
                        .foregroundColor(.black.opacity(0.6))
                }
            } else {
                Button("Install") {
                    runInstaller()
                }
                .buttonStyle(.borderedProminent)
                .tint(.black)
                .controlSize(.large)
            }
        }
        .padding(32)
        .frame(width: 480, height: 320)
        .background(Color(red: 0.961, green: 0.941, blue: 0.910))
    }

    private func installRow(_ name: String) -> some View {
        HStack(spacing: 8) {
            Image(systemName: "circle.fill")
                .font(.system(size: 5))
                .foregroundColor(.black.opacity(0.4))
            Text(name)
                .font(.system(size: 12))
                .foregroundColor(.black.opacity(0.7))
        }
    }

    private func runInstaller() {
        isInstalling = true
        installFailed = false
        installStatus = "Running installer..."

        DispatchQueue.global(qos: .userInitiated).async {
            let proc = Process()
            proc.executableURL = URL(fileURLWithPath: "/bin/bash")
            proc.arguments = ["-c", "curl -fsSL https://raw.githubusercontent.com/romirthedev/openwhisper/main/install.sh | bash"]

            // Set up environment so brew/pyenv are found
            var env = ProcessInfo.processInfo.environment
            let extraPaths = [
                "/opt/homebrew/bin",
                "/usr/local/bin",
                "\(env["HOME"] ?? "")/. pyenv/bin"
            ]
            env["PATH"] = extraPaths.joined(separator: ":") + ":" + (env["PATH"] ?? "")
            proc.environment = env

            let pipe = Pipe()
            let errPipe = Pipe()
            proc.standardOutput = pipe
            proc.standardError = errPipe

            do {
                try proc.run()
                proc.waitUntilExit()

                let status = proc.terminationStatus
                let errOutput = String(data: errPipe.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""

                DispatchQueue.main.async {
                    isInstalling = false
                    if status == 0 {
                        installComplete = true
                        installStatus = "Installation complete!"
                    } else {
                        installFailed = true
                        installStatus = "Install failed (exit \(status)). \(errOutput.prefix(200))"
                    }
                }
            } catch {
                DispatchQueue.main.async {
                    isInstalling = false
                    installFailed = true
                    installStatus = "Failed to start installer: \(error.localizedDescription)"
                }
            }
        }
    }

    private func copyTerminalCommand() {
        let command = "curl -fsSL https://raw.githubusercontent.com/romirthedev/openwhisper/main/install.sh | bash"
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(command, forType: .string)
        installStatus = "Command copied! Open Terminal and paste (Cmd+V)"
        installFailed = false
    }
}
