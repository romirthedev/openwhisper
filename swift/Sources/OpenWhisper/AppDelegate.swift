import AppKit
import SwiftUI
import AVFoundation

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

    func applicationDidFinishLaunching(_ notification: Notification) {
        // Hide dock icon (menu bar app)
        NSApp.setActivationPolicy(.accessory)

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
        menu.addItem(NSMenuItem(title: "OpenWhisper", action: nil, keyEquivalent: ""))
        menu.addItem(NSMenuItem.separator())
        menu.addItem(withTitle: "History", action: #selector(openHistory), keyEquivalent: "h")
        menu.addItem(withTitle: "Settings...", action: #selector(openSettings), keyEquivalent: ",")
        menu.addItem(NSMenuItem.separator())
        menu.addItem(withTitle: "Quit", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
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
            window.setContentSize(NSSize(width: 400, height: 300))
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
                print("[OpenWhisper] Microphone permission denied")
            }
        }

        // Request accessibility / input monitoring
        // Use the string key directly to avoid concurrency warning with kAXTrustedCheckOptionPrompt
        let promptKey = "AXTrustedCheckOptionPrompt" as CFString
        let opts = [promptKey: true] as CFDictionary
        let trusted = AXIsProcessTrustedWithOptions(opts)
        if !trusted {
            print("[OpenWhisper] Accessibility permission not granted yet - please grant in System Settings")
        }
    }

    private func startRecording() {
        guard !isRecording else { return }
        isRecording = true
        recordingStart = Date()
        // Remember which app the user was in before recording
        previousApp = NSWorkspace.shared.frontmostApplication
        pillWindow?.show(state: .recording)
        do {
            try audioCapture?.startRecording()
        } catch {
            print("[OpenWhisper] Failed to start recording: \(error)")
            isRecording = false
            pillWindow?.hide()
        }
    }

    private func stopRecording() {
        guard isRecording else { return }
        isRecording = false
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
                    if !text.isEmpty {
                        let paster = self.textPaster
                        let target = self.previousApp
                        DispatchQueue.global(qos: .userInteractive).async {
                            paster?.paste(text: text, into: target)
                        }
                    }
                } catch {
                    print("[OpenWhisper] Transcription error: \(error)")
                }
                self.pillWindow?.hide()
                try? FileManager.default.removeItem(at: wavURL)
            }
        }
    }
}
