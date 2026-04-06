import Foundation

/// Manages a persistent Python whisper daemon process.
/// The model is loaded once on first use, then reused for all subsequent transcriptions.
final class Transcriber: @unchecked Sendable {

    private let pythonPath: String
    private let daemonPath: String

    private var process: Process?
    private var stdin: FileHandle?
    private var stdoutPipe: Pipe?
    private var isReady = false
    private let lock = NSLock()

    init() {
        let resources = Bundle.main.resourcePath ?? ""
        let venvInBundle = resources + "/.venv/bin/python3"
        let srcInBundle  = resources + "/src/whisper_daemon.py"

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
            daemonPath = srcInBundle
        } else {
            let binary = Bundle.main.executablePath ?? ""
            let projectRoot = URL(fileURLWithPath: binary)
                .deletingLastPathComponent()
                .deletingLastPathComponent()
                .deletingLastPathComponent()
                .deletingLastPathComponent()
                .path
            daemonPath = projectRoot + "/src/whisper_daemon.py"
        }
    }

    deinit {
        process?.terminate()
    }

    // MARK: - Daemon lifecycle

    private func startDaemon() throws {
        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: pythonPath)
        proc.arguments = [daemonPath]

        let inPipe  = Pipe()
        let outPipe = Pipe()
        let errPipe = Pipe()
        proc.standardInput  = inPipe
        proc.standardOutput = outPipe
        proc.standardError  = errPipe

        // Log stderr from Python
        errPipe.fileHandleForReading.readabilityHandler = { fh in
            let data = fh.availableData
            if !data.isEmpty, let msg = String(data: data, encoding: .utf8) {
                owLog("[Transcriber] stderr: \(msg.trimmingCharacters(in: .whitespacesAndNewlines))")
            }
        }

        try proc.run()

        self.process  = proc
        self.stdin    = inPipe.fileHandleForWriting
        self.stdoutPipe = outPipe

        owLog("[Transcriber] Daemon started (pid \(proc.processIdentifier)), waiting for ready...")

        // Wait for {"ready": true} — model loading happens here (~1-2s first time only)
        if let readyLine = readLine(timeout: 30) {
            owLog("[Transcriber] Daemon ready: \(readyLine)")
            isReady = true
        } else {
            owLog("[Transcriber] Daemon never sent ready signal")
            proc.terminate()
            throw TranscriberError.daemonStartFailed
        }
    }

    private func ensureDaemon() throws {
        if let proc = process, proc.isRunning, isReady { return }
        isReady = false
        process?.terminate()
        process = nil
        try startDaemon()
    }

    // MARK: - Transcription

    func transcribe(wavFile: URL, duration: TimeInterval = 0) async throws -> String {
        return try await withCheckedThrowingContinuation { continuation in
            DispatchQueue.global(qos: .userInitiated).async {
                self.lock.lock()
                defer { self.lock.unlock() }

                do {
                    try self.ensureDaemon()
                    let result = try self.sendJob(wav: wavFile.path, duration: duration, rawOnly: false)
                    continuation.resume(returning: result)
                } catch {
                    continuation.resume(throwing: error)
                }
            }
        }
    }

    func transcribeRawOnly(wavFile: URL) async throws -> String {
        return try await withCheckedThrowingContinuation { continuation in
            DispatchQueue.global(qos: .userInitiated).async {
                self.lock.lock()
                defer { self.lock.unlock() }

                do {
                    try self.ensureDaemon()
                    let result = try self.sendJob(wav: wavFile.path, duration: 0, rawOnly: true)
                    continuation.resume(returning: result)
                } catch {
                    continuation.resume(throwing: error)
                }
            }
        }
    }

    // MARK: - Protocol

    private func sendJob(wav: String, duration: TimeInterval, rawOnly: Bool) throws -> String {
        let job: [String: Any] = [
            "wav": wav,
            "duration": duration,
            "raw_only": rawOnly
        ]
        let data = try JSONSerialization.data(withJSONObject: job)
        guard var line = String(data: data, encoding: .utf8) else {
            throw TranscriberError.encodingFailed
        }
        line += "\n"

        guard let stdinHandle = stdin else { throw TranscriberError.daemonNotRunning }
        stdinHandle.write(line.data(using: .utf8)!)

        guard let responseLine = readLine(timeout: 60) else {
            throw TranscriberError.timeout
        }

        guard
            let responseData = responseLine.data(using: .utf8),
            let json = try? JSONSerialization.jsonObject(with: responseData) as? [String: Any]
        else {
            throw TranscriberError.invalidResponse(responseLine)
        }

        if let error = json["error"] as? String, !error.isEmpty {
            throw TranscriberError.workerError(error)
        }

        return (json["text"] as? String ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private func readLine(timeout: TimeInterval) -> String? {
        guard let pipe = stdoutPipe else { return nil }
        let fh = pipe.fileHandleForReading

        var buffer = Data()
        let deadline = Date().addingTimeInterval(timeout)

        while Date() < deadline {
            let chunk = fh.availableData
            if chunk.isEmpty {
                Thread.sleep(forTimeInterval: 0.01)
                continue
            }
            buffer.append(chunk)
            if let newline = buffer.firstIndex(of: UInt8(ascii: "\n")) {
                let lineData = buffer[buffer.startIndex...newline]
                if let line = String(data: lineData, encoding: .utf8)?
                    .trimmingCharacters(in: .whitespacesAndNewlines),
                   !line.isEmpty {
                    return line
                }
            }
        }
        return nil
    }
}

enum TranscriberError: Error {
    case daemonStartFailed
    case daemonNotRunning
    case encodingFailed
    case timeout
    case invalidResponse(String)
    case workerError(String)
}
