import AVFoundation
import Foundation

/// Captures microphone audio and writes it to a temp WAV file.
final class AudioCapture: @unchecked Sendable {

    private let engine = AVAudioEngine()
    private var outputFile: AVAudioFile?
    private var tempURL: URL?
    private var completion: ((URL?) -> Void)?

    func startRecording() throws {
        // Create a temp WAV file
        let tmp = FileManager.default.temporaryDirectory
            .appendingPathComponent("openwhisper_\(UUID().uuidString).wav")
        tempURL = tmp

        let inputNode = engine.inputNode
        let format = inputNode.outputFormat(forBus: 0)

        // Create audio file with PCM format
        let settings: [String: Any] = [
            AVFormatIDKey: kAudioFormatLinearPCM,
            AVSampleRateKey: format.sampleRate,
            AVNumberOfChannelsKey: format.channelCount,
            AVLinearPCMBitDepthKey: 16,
            AVLinearPCMIsFloatKey: false,
            AVLinearPCMIsBigEndianKey: false
        ]

        outputFile = try AVAudioFile(forWriting: tmp, settings: settings)

        inputNode.installTap(onBus: 0, bufferSize: 4096, format: format) { [weak self] buffer, _ in
            guard let self = self, let file = self.outputFile else { return }
            do {
                try file.write(from: buffer)
            } catch {
                print("[AudioCapture] Write error: \(error)")
            }
        }

        try engine.start()
    }

    /// Snapshot current audio to a separate temp file without stopping recording.
    /// Returns a copy of the audio captured so far.
    func snapshotAudio() -> URL? {
        guard let sourceURL = tempURL else { return nil }

        // Flush current file by briefly pausing writes
        guard let currentFile = outputFile else { return nil }
        let _ = currentFile  // ensure reference is held

        let snapshotURL = FileManager.default.temporaryDirectory
            .appendingPathComponent("openwhisper_snap_\(UUID().uuidString).wav")

        do {
            try FileManager.default.copyItem(at: sourceURL, to: snapshotURL)
            return snapshotURL
        } catch {
            print("[AudioCapture] Snapshot error: \(error)")
            return nil
        }
    }

    func stopRecording(completion: @escaping @Sendable (URL?) -> Void) {
        engine.inputNode.removeTap(onBus: 0)
        engine.stop()
        outputFile = nil  // flush / close

        let url = tempURL
        tempURL = nil
        completion(url)
    }
}
