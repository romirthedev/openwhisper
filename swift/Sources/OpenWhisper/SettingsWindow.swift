import SwiftUI

/// Simple settings view shown in a standard window from the menu bar.
struct SettingsView: View {
    @AppStorage("modelSize") private var modelSize = "base.en"
    @AppStorage("language") private var language = "en"
    @AppStorage("hotkeyCode") private var hotkeyCode = 54

    private let modelOptions = ["tiny.en", "base.en", "small.en", "medium.en", "large-v3"]
    private let languageOptions = ["en", "es", "fr", "de", "it", "pt", "zh", "ja", "ko"]

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("Settings")
                .font(.system(size: 16, weight: .semibold))
                .foregroundColor(.black)

            VStack(alignment: .leading, spacing: 10) {
                HStack {
                    Text("Whisper Model")
                        .font(.system(size: 13))
                        .foregroundColor(.black)
                    Spacer()
                    Picker("", selection: $modelSize) {
                        ForEach(modelOptions, id: \.self) { model in
                            Text(model).tag(model)
                        }
                    }
                    .frame(width: 140)
                    .labelsHidden()
                }

                HStack {
                    Text("Language")
                        .font(.system(size: 13))
                        .foregroundColor(.black)
                    Spacer()
                    Picker("", selection: $language) {
                        ForEach(languageOptions, id: \.self) { lang in
                            Text(lang).tag(lang)
                        }
                    }
                    .frame(width: 140)
                    .labelsHidden()
                }

                HStack {
                    Text("Push-to-talk")
                        .font(.system(size: 13))
                        .foregroundColor(.black)
                    Spacer()
                    Text("Right ⌘")
                        .font(.system(size: 13))
                        .foregroundColor(.black.opacity(0.5))
                }
            }

            Divider()

            VStack(alignment: .leading, spacing: 4) {
                Text("Permissions")
                    .font(.system(size: 12, weight: .medium))
                    .foregroundColor(.black)
                Text("Accessibility + Microphone required")
                    .font(.system(size: 11))
                    .foregroundColor(.black.opacity(0.5))
            }

            Spacer()

            HStack {
                Spacer()
                Button("Save") {
                    saveConfig()
                }
                .buttonStyle(.borderedProminent)
                .tint(.black)
            }
        }
        .padding(20)
        .frame(width: 340, height: 260)
        .background(Color(red: 0.961, green: 0.941, blue: 0.910))
    }

    private func saveConfig() {
        let configDir = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".openwhisper")
        try? FileManager.default.createDirectory(at: configDir, withIntermediateDirectories: true)
        let configFile = configDir.appendingPathComponent("config.json")

        // Read existing config so we don't clobber other keys
        var existing: [String: Any] = [:]
        if let data = try? Data(contentsOf: configFile),
           let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
            existing = json
        }
        existing["whisper_model"] = modelSize
        existing["language"] = language

        if let data = try? JSONSerialization.data(withJSONObject: existing, options: .prettyPrinted) {
            try? data.write(to: configFile)
        }
    }
}
