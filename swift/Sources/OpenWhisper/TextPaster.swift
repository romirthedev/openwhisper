import AppKit
import CoreGraphics

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

        // Always try CGEvent paste — works if accessibility is granted
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
    }
}
