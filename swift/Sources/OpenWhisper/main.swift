import AppKit
import SwiftUI

// Entry point - must be @main or just top-level code
// We use top-level code for SPM executable targets

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.run()
