import AppKit
import Carbon

/// Monitors global keyboard events for the push-to-talk hotkey.
/// Default: Right Command key (keyCode 54)
final class KeyMonitor: @unchecked Sendable {

    var onKeyDown: (() -> Void)?
    var onKeyUp: (() -> Void)?

    // Right Command key code
    private let hotkeyCode: UInt16 = 54

    private var downMonitor: Any?
    private var upMonitor: Any?
    private var isHeld = false

    func startMonitoring() {
        downMonitor = NSEvent.addGlobalMonitorForEvents(matching: .keyDown) { [weak self] event in
            guard let self = self else { return }
            if event.keyCode == self.hotkeyCode && !self.isHeld {
                self.isHeld = true
                self.onKeyDown?()
            }
        }

        upMonitor = NSEvent.addGlobalMonitorForEvents(matching: .keyUp) { [weak self] event in
            guard let self = self else { return }
            if event.keyCode == self.hotkeyCode && self.isHeld {
                self.isHeld = false
                self.onKeyUp?()
            }
        }

        // Also monitor flagsChanged for modifier keys (Right Command is a modifier)
        let flagsMonitor = NSEvent.addGlobalMonitorForEvents(matching: .flagsChanged) { [weak self] event in
            guard let self = self else { return }
            if event.keyCode == self.hotkeyCode {
                let isDown = event.modifierFlags.contains(.command)
                if isDown && !self.isHeld {
                    self.isHeld = true
                    self.onKeyDown?()
                } else if !isDown && self.isHeld {
                    self.isHeld = false
                    self.onKeyUp?()
                }
            }
        }
        // Keep the flags monitor alive by capturing it
        _ = flagsMonitor
    }

    func stopMonitoring() {
        if let m = downMonitor { NSEvent.removeMonitor(m) }
        if let m = upMonitor { NSEvent.removeMonitor(m) }
        downMonitor = nil
        upMonitor = nil
        isHeld = false
    }

    deinit {
        stopMonitoring()
    }
}
