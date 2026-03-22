import AppKit
import CoreGraphics

final class TextPaster: @unchecked Sendable {

    func paste(text: String, into targetApp: NSRunningApplication?) {
        // Write to pasteboard on main thread
        DispatchQueue.main.sync {
            let pb = NSPasteboard.general
            pb.clearContents()
            pb.setString(text, forType: .string)
        }

        // Re-activate the target app and wait for it to be frontmost
        if let app = targetApp, !app.isTerminated {
            app.activate(options: [.activateIgnoringOtherApps])

            // Poll until it becomes frontmost (up to 0.5s)
            var waited = 0
            while !app.isActive && waited < 10 {
                Thread.sleep(forTimeInterval: 0.05)
                waited += 1
            }
        }

        // Extra settle time so the window/cursor is ready
        Thread.sleep(forTimeInterval: 0.05)

        // Send Cmd+V (keyCode 9 = 'v')
        let src = CGEventSource(stateID: .combinedSessionState)
        guard
            let keyDown = CGEvent(keyboardEventSource: src, virtualKey: 9, keyDown: true),
            let keyUp   = CGEvent(keyboardEventSource: src, virtualKey: 9, keyDown: false)
        else {
            print("[TextPaster] Failed to create CGEvent")
            return
        }

        keyDown.flags = .maskCommand
        keyUp.flags   = .maskCommand

        keyDown.post(tap: .cgAnnotatedSessionEventTap)
        Thread.sleep(forTimeInterval: 0.02)
        keyUp.post(tap: .cgAnnotatedSessionEventTap)

        print("[TextPaster] Pasted \(text.count) chars into \(targetApp?.localizedName ?? "unknown")")
    }
}
