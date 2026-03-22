import SwiftUI
import SQLite3

struct Transcript: Identifiable {
    let id: Int
    let text: String
    let rawText: String
    let duration: Double
    let wordCount: Int
    let createdAt: String

    var formattedDate: String {
        let iso = DateFormatter()
        iso.dateFormat = "yyyy-MM-dd'T'HH:mm:ss.SSSSSS"
        iso.locale = Locale(identifier: "en_US_POSIX")
        let iso2 = DateFormatter()
        iso2.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"
        let date = iso.date(from: createdAt) ?? iso2.date(from: createdAt) ?? Date()
        let fmt = DateFormatter()
        if Calendar.current.isDateInToday(date) {
            fmt.dateFormat = "h:mm a"
        } else if Calendar.current.isDateInYesterday(date) {
            return "Yesterday " + DateFormatter.localizedString(from: date, dateStyle: .none, timeStyle: .short)
        } else {
            fmt.dateFormat = "MMM d, h:mm a"
        }
        return fmt.string(from: date)
    }
}

func loadTranscripts() -> [Transcript] {
    let dbPath = FileManager.default.homeDirectoryForCurrentUser
        .appendingPathComponent(".openwhisper/transcripts.db").path

    var db: OpaquePointer?
    guard sqlite3_open(dbPath, &db) == SQLITE_OK else { return [] }
    defer { sqlite3_close(db) }

    var stmt: OpaquePointer?
    let sql = "SELECT id, text, raw_text, duration_seconds, word_count, created_at FROM transcripts ORDER BY created_at DESC LIMIT 100"
    guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK else { return [] }
    defer { sqlite3_finalize(stmt) }

    var results: [Transcript] = []
    while sqlite3_step(stmt) == SQLITE_ROW {
        let id       = Int(sqlite3_column_int(stmt, 0))
        let text     = String(cString: sqlite3_column_text(stmt, 1))
        let rawText  = sqlite3_column_text(stmt, 2).map { String(cString: $0) } ?? text
        let duration = sqlite3_column_double(stmt, 3)
        let wc       = Int(sqlite3_column_int(stmt, 4))
        let date     = sqlite3_column_text(stmt, 5).map { String(cString: $0) } ?? ""
        results.append(Transcript(id: id, text: text, rawText: rawText, duration: duration, wordCount: wc, createdAt: date))
    }
    return results
}

func deleteTranscript(id: Int) {
    let dbPath = FileManager.default.homeDirectoryForCurrentUser
        .appendingPathComponent(".openwhisper/transcripts.db").path
    var db: OpaquePointer?
    guard sqlite3_open(dbPath, &db) == SQLITE_OK else { return }
    defer { sqlite3_close(db) }
    sqlite3_exec(db, "DELETE FROM transcripts WHERE id = \(id)", nil, nil, nil)
}

struct HistoryView: View {
    @State private var transcripts: [Transcript] = []
    @State private var search = ""
    @State private var copiedId: Int? = nil

    var filtered: [Transcript] {
        if search.isEmpty { return transcripts }
        return transcripts.filter { $0.text.localizedCaseInsensitiveContains(search) }
    }

    var body: some View {
        VStack(spacing: 0) {
            // Header
            HStack {
                Text("Transcripts")
                    .font(.title2).fontWeight(.semibold)
                Spacer()
                Button(action: { transcripts = loadTranscripts() }) {
                    Image(systemName: "arrow.clockwise")
                        .foregroundColor(.secondary)
                }
                .buttonStyle(.plain)
                .help("Refresh")
            }
            .padding(.horizontal, 20)
            .padding(.top, 20)
            .padding(.bottom, 12)

            // Search
            HStack {
                Image(systemName: "magnifyingglass").foregroundColor(.secondary)
                TextField("Search…", text: $search)
                    .textFieldStyle(.plain)
                if !search.isEmpty {
                    Button(action: { search = "" }) {
                        Image(systemName: "xmark.circle.fill").foregroundColor(.secondary)
                    }.buttonStyle(.plain)
                }
            }
            .padding(8)
            .background(Color(red: 0.93, green: 0.90, blue: 0.88))
            .cornerRadius(8)
            .padding(.horizontal, 20)
            .padding(.bottom, 12)

            Divider()

            if filtered.isEmpty {
                Spacer()
                Text(search.isEmpty ? "No transcripts yet.\nHold Right ⌘ to record." : "No results.")
                    .multilineTextAlignment(.center)
                    .foregroundColor(.secondary)
                    .font(.callout)
                Spacer()
            } else {
                ScrollView {
                    LazyVStack(spacing: 8) {
                        ForEach(filtered) { t in
                            TranscriptCard(
                                transcript: t,
                                isCopied: copiedId == t.id,
                                onCopy: {
                                    NSPasteboard.general.clearContents()
                                    NSPasteboard.general.setString(t.text, forType: .string)
                                    copiedId = t.id
                                    DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) {
                                        if copiedId == t.id { copiedId = nil }
                                    }
                                },
                                onDelete: {
                                    deleteTranscript(id: t.id)
                                    transcripts = loadTranscripts()
                                }
                            )
                        }
                    }
                    .padding(.horizontal, 16)
                    .padding(.vertical, 12)
                }
            }
        }
        .frame(width: 520, height: 560)
        .background(Color(red: 0.961, green: 0.941, blue: 0.910))
        .onAppear { transcripts = loadTranscripts() }
    }
}

struct TranscriptCard: View {
    let transcript: Transcript
    let isCopied: Bool
    let onCopy: () -> Void
    let onDelete: () -> Void
    @State private var hovered = false

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(alignment: .top) {
                Text(transcript.text)
                    .font(.system(size: 13))
                    .foregroundColor(.primary)
                    .fixedSize(horizontal: false, vertical: true)
                    .lineLimit(4)
                Spacer(minLength: 8)
            }

            HStack(spacing: 12) {
                Text(transcript.formattedDate)
                    .font(.caption)
                    .foregroundColor(.secondary)
                if transcript.wordCount > 0 {
                    Text("\(transcript.wordCount) words")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                if transcript.duration > 0 {
                    Text(String(format: "%.0fs", transcript.duration))
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                Spacer()
                Button(isCopied ? "Copied!" : "Copy") { onCopy() }
                    .font(.caption)
                    .buttonStyle(.plain)
                    .foregroundColor(isCopied ? .green : .accentColor)

                Button(action: onDelete) {
                    Image(systemName: "trash")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                .buttonStyle(.plain)
            }
        }
        .padding(12)
        .background(
            RoundedRectangle(cornerRadius: 10)
                .fill(Color.white.opacity(0.7))
                .overlay(RoundedRectangle(cornerRadius: 10).stroke(Color.black.opacity(0.07), lineWidth: 1))
        )
    }
}
