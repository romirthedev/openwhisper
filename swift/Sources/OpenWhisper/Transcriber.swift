import Foundation

final class Transcriber: @unchecked Sendable {

    private let pythonPath: String
    private let workerPath: String

    init() {
        let resources = Bundle.main.resourcePath ?? ""
        let venvInBundle = resources + "/.venv/bin/python3"
        let srcInBundle  = resources + "/src/whisper_worker.py"

        if FileManager.default.fileExists(atPath: venvInBundle) {
            pythonPath = venvInBundle
        } else {
            let binary = Bundle.main.executablePath ?? ""
            let projectRoot = URL(fileURLWithPath: binary)
                .deletingLastPathComponent()
                .deletingLastPathComponent()
                .deletingLastPathComponent()
                .deletingLastPathComponent()
                .path
            pythonPath = projectRoot + "/.venv/bin/python3"
        }

        if FileManager.default.fileExists(atPath: srcInBundle) {
            workerPath = srcInBundle
        } else {
            let binary = Bundle.main.executablePath ?? ""
            let projectRoot = URL(fileURLWithPath: binary)
                .deletingLastPathComponent()
                .deletingLastPathComponent()
                .deletingLastPathComponent()
                .deletingLastPathComponent()
                .path
            workerPath = projectRoot + "/src/whisper_worker.py"
        }
    }

    func transcribe(wavFile: URL, duration: TimeInterval = 0) async throws -> String {
        return try await withCheckedThrowingContinuation { continuation in
            DispatchQueue.global(qos: .userInitiated).async {
                let process = Process()
                process.executableURL = URL(fileURLWithPath: self.pythonPath)
                process.arguments = [self.workerPath, wavFile.path, String(format: "%.2f", duration)]

                let pipe    = Pipe()
                let errPipe = Pipe()
                process.standardOutput = pipe
                process.standardError  = errPipe

                do {
                    try process.run()
                    process.waitUntilExit()

                    let out = String(data: pipe.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
                    let err = String(data: errPipe.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
                    if !err.isEmpty { print("[Transcriber] \(err)") }

                    let text = out.trimmingCharacters(in: .whitespacesAndNewlines)
                    continuation.resume(returning: text)
                } catch {
                    continuation.resume(throwing: error)
                }
            }
        }
    }
}
