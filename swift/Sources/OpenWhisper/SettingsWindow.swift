import SwiftUI

/// Simple settings view shown in a standard window from the menu bar.
struct SettingsView: View {
    @AppStorage("modelSize") private var modelSize = "base.en"
    @AppStorage("language") private var language = "en"
    @AppStorage("hotkeyCode") private var hotkeyCode = 54

    private let modelOptions = ["tiny.en", "base.en", "small.en", "medium.en", "large-v3"]
    private let languageOptions = ["en", "es", "fr", "de", "it", "pt", "zh", "ja", "ko"]

    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            Text("OpenWhisper Settings")
                .font(.title2)
                .fontWeight(.semibold)

            Divider()

            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    Text("Whisper Model:")
                        .frame(width: 130, alignment: .leading)
                    Picker("", selection: $modelSize) {
                        ForEach(modelOptions, id: \.self) { model in
                            Text(model).tag(model)
                        }
                    }
                    .frame(width: 160)
                    .labelsHidden()
                }

                HStack {
                    Text("Language:")
                        .frame(width: 130, alignment: .leading)
                    Picker("", selection: $language) {
                        ForEach(languageOptions, id: \.self) { lang in
                            Text(lang).tag(lang)
                        }
                    }
                    .frame(width: 160)
                    .labelsHidden()
                }

                HStack {
                    Text("Push-to-talk key:")
                        .frame(width: 130, alignment: .leading)
                    Text("Right ⌘ (fixed)")
                        .foregroundColor(.secondary)
                }
            }

            Divider()

            VStack(alignment: .leading, spacing: 8) {
                Text("Permissions Required:")
                    .fontWeight(.medium)
                HStack(spacing: 6) {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundColor(.green)
                    Text("Accessibility – for global key monitoring")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                HStack(spacing: 6) {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundColor(.green)
                    Text("Microphone – for audio capture")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }

            Spacer()

            HStack {
                Spacer()
                Button("Save Config") {
                    saveConfig()
                }
                .buttonStyle(.borderedProminent)
            }
        }
        .padding(24)
        .frame(width: 400, height: 300)
        .background(Color(red: 0.961, green: 0.941, blue: 0.910))
    }

    private func saveConfig() {
        let config: [String: String] = [
            "model_size": modelSize,
            "language": language
        ]
        let configDir = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".openwhisper")
        try? FileManager.default.createDirectory(at: configDir, withIntermediateDirectories: true)
        let configFile = configDir.appendingPathComponent("config.json")
        if let data = try? JSONSerialization.data(withJSONObject: config, options: .prettyPrinted) {
            try? data.write(to: configFile)
        }
    }
}
