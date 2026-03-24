import AppKit
import SwiftUI

enum PillState {
    case recording
    case transcribing
}

/// A floating pill-shaped window at the bottom center of the screen.
@MainActor
final class PillWindow {

    private var panel: NSPanel?
    private var hostingView: NSHostingView<PillView>?
    private var pillViewModel = PillViewModel()

    init() {
        setupPanel()
    }

    private func setupPanel() {
        let width: CGFloat = 40
        let height: CGFloat = 12

        let screen = NSScreen.main ?? NSScreen.screens[0]
        let screenFrame = screen.frame
        let x = screenFrame.midX - width / 2
        let y = screenFrame.minY + 6

        let panel = NSPanel(
            contentRect: NSRect(x: x, y: y, width: width, height: height),
            styleMask: [.borderless, .nonactivatingPanel],
            backing: .buffered,
            defer: true
        )
        panel.level = .floating
        panel.isOpaque = false
        panel.backgroundColor = .clear
        panel.hasShadow = false
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        panel.ignoresMouseEvents = true

        let pillView = PillView(viewModel: pillViewModel)
        let hosting = NSHostingView(rootView: pillView)
        hosting.frame = NSRect(x: 0, y: 0, width: width, height: height)
        panel.contentView = hosting

        self.panel = panel
        self.hostingView = hosting
    }

    func show(state: PillState) {
        pillViewModel.state = state
        pillViewModel.isVisible = true
        panel?.orderFrontRegardless()

        // Animate in
        panel?.alphaValue = 0
        NSAnimationContext.runAnimationGroup { ctx in
            ctx.duration = 0.2
            self.panel?.animator().alphaValue = 1
        }
    }

    func hide() {
        NSAnimationContext.runAnimationGroup({ ctx in
            ctx.duration = 0.2
            self.panel?.animator().alphaValue = 0
        }, completionHandler: { [weak self] in
            Task { @MainActor [weak self] in
                self?.panel?.orderOut(nil)
                self?.pillViewModel.isVisible = false
            }
        })
    }
}

@MainActor
final class PillViewModel: ObservableObject {
    @Published var state: PillState = .recording
    @Published var isVisible: Bool = false
}

struct PillView: View {
    @ObservedObject var viewModel: PillViewModel
    @State private var glow = false

    var body: some View {
        Capsule()
            .fill(viewModel.state == .recording
                  ? Color.red.opacity(glow ? 0.9 : 0.5)
                  : Color.orange.opacity(glow ? 0.9 : 0.5))
            .frame(width: 36, height: 6)
            .shadow(color: viewModel.state == .recording
                    ? Color.red.opacity(glow ? 0.8 : 0.3)
                    : Color.orange.opacity(glow ? 0.8 : 0.3),
                    radius: glow ? 8 : 4)
            .animation(
                Animation.easeInOut(duration: 0.8).repeatForever(autoreverses: true),
                value: glow
            )
            .onAppear { glow = true }
            .onChange(of: viewModel.state) { _ in glow = true }
    }
}
