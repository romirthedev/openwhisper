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
        let width: CGFloat = 220
        let height: CGFloat = 48

        let screen = NSScreen.main ?? NSScreen.screens[0]
        let screenFrame = screen.visibleFrame
        let x = screenFrame.midX - width / 2
        let y = screenFrame.minY + 40

        let panel = NSPanel(
            contentRect: NSRect(x: x, y: y, width: width, height: height),
            styleMask: [.borderless, .nonactivatingPanel],
            backing: .buffered,
            defer: true
        )
        panel.level = .floating
        panel.isOpaque = false
        panel.backgroundColor = .clear
        panel.hasShadow = true
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
    @State private var pulse = false
    @State private var dotCount = 0

    var body: some View {
        ZStack {
            Capsule()
                .fill(Color.black)
                .shadow(color: .black.opacity(0.3), radius: 12, x: 0, y: 4)

            HStack(spacing: 10) {
                if viewModel.state == .recording {
                    Circle()
                        .fill(Color.red)
                        .frame(width: 10, height: 10)
                        .scaleEffect(pulse ? 1.3 : 1.0)
                        .animation(
                            Animation.easeInOut(duration: 0.6).repeatForever(autoreverses: true),
                            value: pulse
                        )
                    Text("Recording...")
                        .font(.system(size: 14, weight: .medium))
                        .foregroundColor(.white)
                } else {
                    ProgressView()
                        .progressViewStyle(CircularProgressViewStyle(tint: .white))
                        .scaleEffect(0.7)
                    Text("Transcribing...")
                        .font(.system(size: 14, weight: .medium))
                        .foregroundColor(.white)
                }
            }
            .padding(.horizontal, 18)
        }
        .frame(height: 48)
        .onAppear {
            pulse = true
        }
        .onChange(of: viewModel.state) { _ in
            pulse = viewModel.state == .recording
        }
    }
}
