import Foundation

/// Calls the Python whisper_worker.py subprocess to transcribe a WAV file.
final class Transcriber: @unchecked Sendable {

    private let pythonPath: String
    private let workerPath: String

    init() {
        // Resources are symlinked into the app bundle's Contents/Resources/
        let resources = Bundle.main.resourcePath ?? ""
        let venvInBundle = resources + "/.venv/bin/python3"
        let srcInBundle  = resources + "/src/whisper_worker.py"

        if FileManager.default.fileExists(atPath: venvInBundle) {
            pythonPath = venvInBundle
        } else {
            // Fallback: walk up from binary to project root
            let binary = Bundle.main.executablePath ?? ""
            let projectRoot = URL(fileURLWithPath: binary)
                .deletingLastPathComponent()   // MacOS
                .deletingLastPathComponent()   // Contents
                .deletingLastPathComponent()   // OpenWhisper.app
                .deletingLastPathComponent()   // swift/
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

        print("[Transcriber] python=\(pythonPath)")
        print("[Transcriber] worker=\(workerPath)")
    }

    func transcribe(wavFile: URL, duration: TimeInterval = 0) async throws -> String {
        return try await withCheckedThrowingContinuation { continuation in
            DispatchQueue.global(qos: .userInitiated).async {
                let process = Process()
                process.executableURL = URL(fileURLWithPath: self.pythonPath)
                process.arguments = [self.workerPath, wavFile.path, String(format: "%.2f", duration)]

                let pipe = Pipe()
                let errorPipe = Pipe()
                process.standardOutput = pipe
                process.standardError = errorPipe

                do {
                    try process.run()
                    process.waitUntilExit()

                    let data = pipe.fileHandleForReading.readDataToEndOfFile()
                    let output = String(data: data, encoding: .utf8)?
                        .trimmingCharacters(in: .whitespacesAndNewlines) ?? ""

                    if process.terminationStatus != 0 {
                        let errData = errorPipe.fileHandleForReading.readDataToEndOfFile()
                        let errStr = String(data: errData, encoding: .utf8) ?? "Unknown error"
                        print("[Transcriber] Python error: \(errStr)")
                    }

                    continuation.resume(returning: output)
                } catch {
                    continuation.resume(throwing: error)
                }
            }
        }
    }
}
