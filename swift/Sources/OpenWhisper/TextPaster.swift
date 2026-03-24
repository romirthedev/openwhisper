import AppKit
import CoreGraphics

final class TextPaster: @unchecked Sendable {

    func paste(text: String, into targetApp: NSRunningApplication?) {
        // Set clipboard
        let pb = NSPasteboard.general
        pb.clearContents()
        pb.setString(text, forType: .string)
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

        // Try multiple paste strategies
        // Strategy 1: CGEvent with nil source
        let trusted = AXIsProcessTrusted()
        owLog("[TextPaster] AXIsProcessTrusted = \(trusted)")

        if trusted {
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
            // Strategy 2: Open System Settings to grant permission, then use
            // AX API to set focused element's value directly (no keystroke needed)
            owLog("[TextPaster] No accessibility — trying AX value insertion")
            if let app = targetApp {
                let axApp = AXUIElementCreateApplication(app.processIdentifier)
                var focusedElement: AnyObject?
                let err = AXUIElementCopyAttributeValue(axApp, kAXFocusedUIElementAttribute as CFString, &focusedElement)
                if err == .success, let element = focusedElement {
                    // Get current value and selected text range to insert at cursor
                    var currentValue: AnyObject?
                    var selectedRange: AnyObject?
                    AXUIElementCopyAttributeValue(element as! AXUIElement, kAXValueAttribute as CFString, &currentValue)
                    AXUIElementCopyAttributeValue(element as! AXUIElement, kAXSelectedTextRangeAttribute as CFString, &selectedRange)

                    if let current = currentValue as? String, let rangeValue = selectedRange {
                        var range = CFRange(location: 0, length: 0)
                        AXValueGetValue(rangeValue as! AXValue, .cfRange, &range)
                        let idx = current.index(current.startIndex, offsetBy: min(range.location, current.count))
                        var newValue = current
                        newValue.insert(contentsOf: text, at: idx)
                        AXUIElementSetAttributeValue(element as! AXUIElement, kAXValueAttribute as CFString, newValue as CFTypeRef)
                        owLog("[TextPaster] Inserted via AX value API")
                    } else {
                        // Fallback: just set the whole value
                        AXUIElementSetAttributeValue(element as! AXUIElement, kAXValueAttribute as CFString, text as CFTypeRef)
                        owLog("[TextPaster] Set via AX value API (full replace)")
                    }
                } else {
                    owLog("[TextPaster] AX focused element failed: \(err.rawValue) — please grant Accessibility permission")
                    // Open system settings as last resort
                    let url = URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility")!
                    NSWorkspace.shared.open(url)
                }
            }
        }
    }

    /// Select-all-just-pasted and replace with cleaned version.
    /// Uses: select the raw text length via Shift+Left * n, then type replacement.
    func replace(old: String, with new: String, into targetApp: NSRunningApplication?) {
        if let app = targetApp, !app.isTerminated {
            app.activate(options: [.activateIgnoringOtherApps])
            Thread.sleep(forTimeInterval: 0.1)
        }

        // Put cleaned text on pasteboard
        DispatchQueue.main.sync {
            let pb = NSPasteboard.general
            pb.clearContents()
            pb.setString(new, forType: .string)
        }

        let src = CGEventSource(stateID: .combinedSessionState)

        // Select back over the raw text we just pasted (Shift+Left x char count)
        let charCount = old.count
        for _ in 0..<charCount {
            guard
                let kd = CGEvent(keyboardEventSource: src, virtualKey: 123, keyDown: true),
                let ku = CGEvent(keyboardEventSource: src, virtualKey: 123, keyDown: false)
            else { continue }
            kd.flags = .maskShift
            ku.flags = .maskShift
            kd.post(tap: .cgAnnotatedSessionEventTap)
            ku.post(tap: .cgAnnotatedSessionEventTap)
        }

        Thread.sleep(forTimeInterval: 0.05)

        // Paste the cleaned version over selection
        guard
            let kd = CGEvent(keyboardEventSource: src, virtualKey: 9, keyDown: true),
            let ku = CGEvent(keyboardEventSource: src, virtualKey: 9, keyDown: false)
        else { return }
        kd.flags = .maskCommand
        ku.flags = .maskCommand
        kd.post(tap: .cgAnnotatedSessionEventTap)
        ku.post(tap: .cgAnnotatedSessionEventTap)

        owLog("[TextPaster] Replaced with cleaned \(new.count) chars")
    }
}
