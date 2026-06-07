import SwiftUI
import WebKit

// MARK: - HTML Preview

struct HTMLPreviewView: UIViewRepresentable {
    let html: String

    func makeUIView(context: Context) -> WKWebView {
        let webView = WKWebView()
        webView.isOpaque = false
        webView.backgroundColor = .clear
        webView.scrollView.backgroundColor = .clear
        return webView
    }

    func updateUIView(_ webView: WKWebView, context: Context) {
        webView.loadHTMLString(html, baseURL: nil)
    }
}

// MARK: - Deliverable helpers

enum DeliverableHelper {
    static func executiveSummary(from content: String, maxLines: Int = 6) -> String {
        let lines = content
            .components(separatedBy: .newlines)
            .map { $0.trimmingCharacters(in: .whitespaces) }
            .filter { !$0.isEmpty && !$0.hasPrefix("#") && !$0.hasPrefix("---") }
        return lines.prefix(maxLines).joined(separator: "\n")
    }

    static func copyButtonLabel(for missionType: String) -> String {
        switch missionType {
        case "landing_page": return "COPIER LE HTML"
        case "market_scan", "product_brief": return "COPIER LE PITCH"
        case "ad_copy_pack", "ad_creation", "cold_email_sequence", "cold_outbound":
            return "COPIER POUR ADS"
        case "social_batch": return "COPIER LES POSTS"
        default: return "COPIER"
        }
    }

    static func questStepTitle(for mission: Mission, chain: [QuestStep]) -> String? {
        chain.first { $0.missionId == mission.id || $0.missionType == mission.missionType }?.title
    }
}

// MARK: - Deliverable content block (shared by Loot + Journal)

struct DeliverableContentBlock: View {
    let mission: Mission
    @State private var showPreview = true

    var body: some View {
        // #region agent log
        let _ = {
            let dLen = mission.deliverable?.count ?? -1
            let dPreview = mission.deliverable.map { String($0.prefix(80)) } ?? "NIL"
            print("[DEBUG-H4] DeliverableContentBlock.body: deliverable len=\(dLen) preview='\(dPreview)'")
        }()
        // #endregion
        VStack(alignment: .leading, spacing: 10) {
            if let content = mission.deliverable {
                let summary = DeliverableHelper.executiveSummary(from: content)
                if !summary.isEmpty && mission.deliverableFormat != "html" {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("RESUME")
                            .font(PixelTheme.microFont)
                            .foregroundStyle(PixelTheme.accentGreen)
                        Text(summary)
                            .font(PixelTheme.captionFont)
                            .foregroundStyle(PixelTheme.textPrimary)
                    }
                    .padding(10)
                    .background(PixelTheme.bgMedium, in: RoundedRectangle(cornerRadius: 8))
                }

                if mission.deliverableFormat == "html" {
                    Picker("", selection: $showPreview) {
                        Text("Apercu").tag(true)
                        Text("Code").tag(false)
                    }
                    .pickerStyle(.segmented)

                    if showPreview {
                        HTMLPreviewView(html: content)
                            .frame(minHeight: 280)
                            .clipShape(RoundedRectangle(cornerRadius: 8))
                            .overlay(
                                RoundedRectangle(cornerRadius: 8)
                                    .stroke(PixelTheme.cardBorder, lineWidth: 1)
                            )
                    } else {
                        ScrollView {
                            Text(content)
                                .font(.system(size: 11, design: .monospaced))
                                .foregroundStyle(PixelTheme.textPrimary)
                                .textSelection(.enabled)
                                .frame(maxWidth: .infinity, alignment: .leading)
                        }
                        .frame(maxHeight: 280)
                    }
                } else {
                    ScrollView {
                        Text(content)
                            .font(PixelTheme.captionFont)
                            .foregroundStyle(PixelTheme.textPrimary)
                            .textSelection(.enabled)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                    .frame(maxHeight: 320)
                }
            }
        }
    }
}
