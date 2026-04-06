import AppKit
import SwiftUI
import AVFoundation

func owLog(_ msg: String) {
    let ts = ISO8601DateFormatter().string(from: Date())
    let line = "[\(ts)] \(msg)\n"
    let logPath = FileManager.default.homeDirectoryForCurrentUser
        .appendingPathComponent(".openwhisper/app.log")
    if let fh = try? FileHandle(forWritingTo: logPath) {
        fh.seekToEndOfFile()
        fh.write(line.data(using: .utf8)!)
        fh.closeFile()
    } else {
        try? line.data(using: .utf8)?.write(to: logPath)
    }
    print(msg)
}

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {

    private var statusItem: NSStatusItem?
    private var pillWindow: PillWindow?
    private var keyMonitor: KeyMonitor?
    private var audioCapture: AudioCapture?
    private var transcriber: Transcriber?
    private var textPaster: TextPaster?
    private var settingsWindowController: NSWindowController?
    private var historyWindowController: NSWindowController?
    private var isRecording = false
    private var recordingStart: Date = Date()
    private var previousApp: NSRunningApplication?

    // Live dictation state
    private var liveTimer: Timer?
    private var liveTranscribedText = ""  // what we've pasted so far in live mode
    private var liveTranscribing = false  // prevents overlapping transcriptions
    private var liveCharsPasted = 0       // total chars pasted in this live session

    func applicationDidFinishLaunching(_ notification: Notification) {
        // Hide dock icon (menu bar app)
        NSApp.setActivationPolicy(.accessory)

        // Check if dependencies are installed — if not, run installer
        if !depsInstalled() {
            showSetupWindow()
            return
        }

        launchApp()
    }

    private func depsInstalled() -> Bool {
        let home = FileManager.default.homeDirectoryForCurrentUser.path
        let repoDir = home + "/openwhisper"
        let venvPython = repoDir + "/.venv/bin/python3"
        let workerScript = repoDir + "/src/whisper_worker.py"

        // Also check inside the app bundle (symlinks from Makefile)
        let resources = Bundle.main.resourcePath ?? ""
        let bundledPython = resources + "/.venv/bin/python3"
        let bundledWorker = resources + "/src/whisper_worker.py"

        let hasPython = FileManager.default.fileExists(atPath: venvPython)
            || FileManager.default.fileExists(atPath: bundledPython)
        let hasWorker = FileManager.default.fileExists(atPath: workerScript)
            || FileManager.default.fileExists(atPath: bundledWorker)

        owLog("[OpenWhisper] Deps check — python: \(hasPython), worker: \(hasWorker)")
        return hasPython && hasWorker
    }

    private var setupWindowController: NSWindowController?

    private func showSetupWindow() {
        NSApp.setActivationPolicy(.regular)

        let setupView = SetupView(onInstallComplete: { [weak self] in
            self?.setupWindowController?.close()
            NSApp.setActivationPolicy(.accessory)
            self?.launchApp()
        })
        let hc = NSHostingController(rootView: setupView)
        let window = NSWindow(contentViewController: hc)
        window.title = "OpenWhisper Setup"
        window.styleMask = [.titled, .closable]
        window.setContentSize(NSSize(width: 480, height: 320))
        window.center()
        setupWindowController = NSWindowController(window: window)
        setupWindowController?.showWindow(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    private func launchApp() {
        setupMenuBar()
        requestPermissions()

        audioCapture = AudioCapture()
        transcriber = Transcriber()
        textPaster = TextPaster()

        pillWindow = PillWindow()

        keyMonitor = KeyMonitor()
        keyMonitor?.onKeyDown = { [weak self] in
            Task { @MainActor in
                self?.startRecording()
            }
        }
        keyMonitor?.onKeyUp = { [weak self] in
            Task { @MainActor in
                self?.stopRecording()
            }
        }
        keyMonitor?.startMonitoring()
    }

    private func setupMenuBar() {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.squareLength)
        if let button = statusItem?.button {
            button.image = NSImage(systemSymbolName: "mic.fill", accessibilityDescription: "OpenWhisper")
        }

        let menu = NSMenu()
        let attrs: [NSAttributedString.Key: Any] = [.foregroundColor: NSColor.black]

        let header = NSMenuItem()
        header.attributedTitle = NSAttributedString(string: "OpenWhisper", attributes: [
            .foregroundColor: NSColor.black,
            .font: NSFont.boldSystemFont(ofSize: 13)
        ])
        menu.addItem(header)
        menu.addItem(NSMenuItem.separator())

        let history = NSMenuItem(title: "History", action: #selector(openHistory), keyEquivalent: "h")
        history.attributedTitle = NSAttributedString(string: "History", attributes: attrs)
        menu.addItem(history)

        let settings = NSMenuItem(title: "Settings...", action: #selector(openSettings), keyEquivalent: ",")
        settings.attributedTitle = NSAttributedString(string: "Settings...", attributes: attrs)
        menu.addItem(settings)

        menu.addItem(NSMenuItem.separator())

        let quit = NSMenuItem(title: "Quit", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        quit.attributedTitle = NSAttributedString(string: "Quit", attributes: attrs)
        menu.addItem(quit)

        statusItem?.menu = menu
    }

    @objc private func openHistory() {
        if historyWindowController == nil {
            let view = HistoryView()
            let hc = NSHostingController(rootView: view)
            let window = NSWindow(contentViewController: hc)
            window.title = "OpenWhisper — History"
            window.styleMask = [.titled, .closable, .resizable]
            window.setContentSize(NSSize(width: 520, height: 560))
            window.center()
            historyWindowController = NSWindowController(window: window)
        }
        historyWindowController?.showWindow(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    @objc private func openSettings() {
        if settingsWindowController == nil {
            let settingsView = SettingsView()
            let hostingController = NSHostingController(rootView: settingsView)
            let window = NSWindow(contentViewController: hostingController)
            window.title = "OpenWhisper Settings"
            window.styleMask = [.titled, .closable]
            window.setContentSize(NSSize(width: 340, height: 340))
            window.center()
            settingsWindowController = NSWindowController(window: window)
        }
        settingsWindowController?.showWindow(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    private func requestPermissions() {
        // Request microphone permission
        AVCaptureDevice.requestAccess(for: .audio) { granted in
            if !granted {
                owLog("[OpenWhisper] Microphone permission denied")
            }
        }

        // Check accessibility — only prompt if not already granted
        let trusted = AXIsProcessTrusted()
        if !trusted {
            let promptKey = "AXTrustedCheckOptionPrompt" as CFString
            let opts = [promptKey: true] as CFDictionary
            _ = AXIsProcessTrustedWithOptions(opts)
            owLog("[OpenWhisper] Accessibility permission not granted yet - please grant in System Settings")
        }
    }

    private var isLiveMode: Bool {
        UserDefaults.standard.string(forKey: "dictationMode") == "live"
    }

    private func startRecording() {
        guard !isRecording else { return }
        isRecording = true
        recordingStart = Date()
        previousApp = NSWorkspace.shared.frontmostApplication
        pillWindow?.show(state: .recording)
        do {
            try audioCapture?.startRecording()
        } catch {
            owLog("[OpenWhisper] Failed to start recording: \(error)")
            isRecording = false
            pillWindow?.hide()
            return
        }

        // Start live transcription loop if in live mode
        if isLiveMode {
            liveTranscribedText = ""
            liveCharsPasted = 0
            liveTranscribing = false
            startLiveLoop()
        }
    }

    private func stopRecording() {
        guard isRecording else { return }
        isRecording = false
        liveTimer?.invalidate()
        liveTimer = nil

        let target = self.previousApp
        let wasLive = isLiveMode
        let liveChars = liveCharsPasted
        owLog("[OpenWhisper] stopRecording — target: \(target?.localizedName ?? "nil"), live: \(wasLive), liveChars: \(liveChars)")

        if wasLive {
            // Live mode: just stop — no final transcription, no post-processing
            audioCapture?.stopRecording { [weak self] wavURL in
                if let wavURL = wavURL {
                    try? FileManager.default.removeItem(at: wavURL)
                }
                Task { @MainActor in
                    self?.pillWindow?.hide()
                    self?.liveTranscribedText = ""
                    self?.liveCharsPasted = 0
                }
            }
        } else {
            // Standard mode: unchanged
            pillWindow?.show(state: .transcribing)
            let duration = Date().timeIntervalSince(recordingStart)
            audioCapture?.stopRecording { [weak self] wavURL in
                guard let self = self, let wavURL = wavURL else {
                    Task { @MainActor in self?.pillWindow?.hide() }
                    return
                }
                Task { @MainActor in
                    do {
                        let text = try await self.transcriber?.transcribe(wavFile: wavURL, duration: duration) ?? ""
                        owLog("[OpenWhisper] Transcribed: '\(text)' (\(text.count) chars)")
                        if !text.isEmpty {
                            let paster = self.textPaster
                            DispatchQueue.global(qos: .userInteractive).async {
                                owLog("[OpenWhisper] About to paste into \(target?.localizedName ?? "nil")")
                                paster?.paste(text: text, into: target)
                            }
                        }
                    } catch {
                        owLog("[OpenWhisper] Transcription error: \(error)")
                    }
                    self.pillWindow?.hide()
                    try? FileManager.default.removeItem(at: wavURL)
                }
            }
        }
    }

    // MARK: - Live Dictation

    private func startLiveLoop() {
        liveTimer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { [weak self] _ in
            Task { @MainActor in
                self?.liveTranscribeChunk()
            }
        }
    }

    private func liveTranscribeChunk() {
        guard isRecording, !liveTranscribing else { return }
        guard let snapshot = audioCapture?.snapshotAudio() else { return }

        liveTranscribing = true
        let target = self.previousApp

        Task {
            do {
                let fullText = try await self.transcriber?.transcribeRawOnly(wavFile: snapshot) ?? ""
                try? FileManager.default.removeItem(at: snapshot)

                await MainActor.run {
                    self.liveTranscribing = false

                    // Word-based diff: only paste words beyond what we've already pasted
                    let prevWords = self.liveTranscribedText.split(separator: " ").map(String.init)
                    let fullWords = fullText.split(separator: " ").map(String.init)
                    guard fullWords.count > prevWords.count else { return }

                    let newWords = Array(fullWords.dropFirst(prevWords.count))
                    let newText = newWords.joined(separator: " ")
                    guard !newText.isEmpty else { return }

                    let textToType = (self.liveCharsPasted > 0 ? " " : "") + newText
                    self.liveTranscribedText = fullWords.joined(separator: " ")
                    self.liveCharsPasted += textToType.count

                    owLog("[OpenWhisper] Live chunk: +'\(textToType)' (total \(self.liveCharsPasted) chars)")

                    let paster = self.textPaster
                    DispatchQueue.global(qos: .userInteractive).async {
                        paster?.typeText(textToType, into: target)
                    }
                }
            } catch {
                await MainActor.run {
                    self.liveTranscribing = false
                }
                try? FileManager.default.removeItem(at: snapshot)
                owLog("[OpenWhisper] Live chunk error: \(error)")
            }
        }
    }
}
