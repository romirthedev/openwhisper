import AppKit
import CoreGraphics
import Foundation

final class TextPaster: @unchecked Sendable {

    func paste(text: String, into targetApp: NSRunningApplication?) {
        // Set clipboard on main thread
        DispatchQueue.main.sync {
            let pb = NSPasteboard.general
            pb.clearContents()
            pb.setString(text, forType: .string)
        }
        owLog("[TextPaster] Clipboard set with \(text.count) chars")

        // Re-activate the target app
        if let app = targetApp, !app.isTerminated {
            app.activate()
            var waited = 0
            while !app.isActive && waited < 20 {
                Thread.sleep(forTimeInterval: 0.05)
                waited += 1
            }
            owLog("[TextPaster] App activated after \(waited) polls: \(app.localizedName ?? "?")")
        }

        Thread.sleep(forTimeInterval: 0.3)

        // Try CGEvent first (needs Accessibility permission)
        if AXIsProcessTrusted() {
            guard
                let keyDown = CGEvent(keyboardEventSource: nil, virtualKey: 9, keyDown: true),
                let keyUp   = CGEvent(keyboardEventSource: nil, virtualKey: 9, keyDown: false)
            else {
                owLog("[TextPaster] Failed to create CGEvent")
                return
            }
            keyDown.flags = .maskCommand
            keyUp.flags   = .maskCommand
            keyDown.post(tap: .cghidEventTap)
            Thread.sleep(forTimeInterval: 0.05)
            keyUp.post(tap: .cghidEventTap)
            owLog("[TextPaster] Pasted via CGEvent into \(targetApp?.localizedName ?? "unknown")")
        } else {
            // Fallback: use osascript subprocess (has its own TCC entry)
            owLog("[TextPaster] No accessibility, using osascript fallback")
            let proc = Process()
            proc.executableURL = URL(fileURLWithPath: "/usr/bin/osascript")
            proc.arguments = ["-e", "tell application \"System Events\" to keystroke \"v\" using command down"]
            let errPipe = Pipe()
            proc.standardError = errPipe
            do {
                try proc.run()
                proc.waitUntilExit()
                if proc.terminationStatus != 0 {
                    let errMsg = String(data: errPipe.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
                    owLog("[TextPaster] osascript failed: \(errMsg)")
                } else {
                    owLog("[TextPaster] Pasted via osascript into \(targetApp?.localizedName ?? "unknown")")
                }
            } catch {
                owLog("[TextPaster] osascript launch failed: \(error)")
            }
        }
    }

    /// Type text character-by-character using CGEvent (for live dictation — no clipboard clobbering).
    func typeText(_ text: String, into targetApp: NSRunningApplication?) {
        guard !text.isEmpty else { return }

        // Use clipboard + paste for reliability (same as paste but without re-activating)
        DispatchQueue.main.sync {
            let pb = NSPasteboard.general
            pb.clearContents()
            pb.setString(text, forType: .string)
        }

        if AXIsProcessTrusted() {
            guard
                let keyDown = CGEvent(keyboardEventSource: nil, virtualKey: 9, keyDown: true),
                let keyUp   = CGEvent(keyboardEventSource: nil, virtualKey: 9, keyDown: false)
            else { return }
            keyDown.flags = .maskCommand
            keyUp.flags   = .maskCommand
            keyDown.post(tap: .cghidEventTap)
            Thread.sleep(forTimeInterval: 0.03)
            keyUp.post(tap: .cghidEventTap)
        } else {
            let proc = Process()
            proc.executableURL = URL(fileURLWithPath: "/usr/bin/osascript")
            proc.arguments = ["-e", "tell application \"System Events\" to keystroke \"v\" using command down"]
            try? proc.run()
            proc.waitUntilExit()
        }
    }

    /// Select and delete N characters behind the cursor (for replacing live text with cleaned version).
    func selectAndReplace(charCount: Int, with text: String, into targetApp: NSRunningApplication?) {
        guard charCount > 0 else {
            paste(text: text, into: targetApp)
            return
        }

        if let app = targetApp, !app.isTerminated {
            app.activate()
            var waited = 0
            while !app.isActive && waited < 20 {
                Thread.sleep(forTimeInterval: 0.05)
                waited += 1
            }
        }
        Thread.sleep(forTimeInterval: 0.1)

        // Select backwards: Shift+Cmd+Left would select to line start — instead use Shift+Left * n
        // But that's slow for many chars. Use: set clipboard, select all typed text via shift+left, paste.
        // Better: use Cmd+A won't work. Use programmatic approach:
        // 1. Move cursor left by charCount with Shift held (selects text)
        // 2. Paste replacement

        // For efficiency, select with Shift+Home-like approach:
        // Actually, just do Shift+Left in batches or use osascript
        let selectScript = """
            tell application "System Events"
                repeat \(charCount) times
                    key code 123 using shift down
                end repeat
            end tell
        """
        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: "/usr/bin/osascript")
        proc.arguments = ["-e", selectScript]
        try? proc.run()
        proc.waitUntilExit()

        Thread.sleep(forTimeInterval: 0.05)

        // Now paste the replacement
        DispatchQueue.main.sync {
            let pb = NSPasteboard.general
            pb.clearContents()
            pb.setString(text, forType: .string)
        }

        if AXIsProcessTrusted() {
            guard
                let keyDown = CGEvent(keyboardEventSource: nil, virtualKey: 9, keyDown: true),
                let keyUp   = CGEvent(keyboardEventSource: nil, virtualKey: 9, keyDown: false)
            else { return }
            keyDown.flags = .maskCommand
            keyUp.flags   = .maskCommand
            keyDown.post(tap: .cghidEventTap)
            Thread.sleep(forTimeInterval: 0.03)
            keyUp.post(tap: .cghidEventTap)
        } else {
            let p = Process()
            p.executableURL = URL(fileURLWithPath: "/usr/bin/osascript")
            p.arguments = ["-e", "tell application \"System Events\" to keystroke \"v\" using command down"]
            try? p.run()
            p.waitUntilExit()
        }
        owLog("[TextPaster] Replaced \(charCount) chars with cleaned text (\(text.count) chars)")
    }
}
