import SwiftUI

struct MissionBoardView: View {
    @EnvironmentObject private var appState: AppState
    @Environment(\.dismiss) private var dismiss
    @State private var showAdvancedCatalog = false

    var body: some View {
        NavigationStack {
            ZStack {
                PixelTheme.bgDark.ignoresSafeArea()

                ScrollView {
                    VStack(spacing: 16) {
                        questChainCTA

                        if showAdvancedCatalog {
                            advancedCatalogSection
                        } else {
                            advancedToggle
                        }
                    }
                    .padding(16)
                }
            }
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .principal) {
                    Text("QG — MISSIONS")
                        .font(PixelTheme.headlineFont)
                        .foregroundStyle(PixelTheme.textPrimary)
                }
                ToolbarItem(placement: .cancellationAction) {
                    Button(action: { dismiss() }) {
                        Text("✕")
                            .font(PixelTheme.bodyFont)
                            .foregroundStyle(PixelTheme.textSecondary)
                    }
                }
            }
            .toolbarBackground(PixelTheme.bgMedium, for: .navigationBar)
            .toolbarBackground(.visible, for: .navigationBar)
        }
    }

    private var questChainCTA: some View {
        let progress = appState.questChainProgress
        let nextStep = appState.currentQuestStep

        return VStack(alignment: .leading, spacing: 10) {
            Text("PARCOURS PRINCIPAL")
                .font(PixelTheme.captionFont)
                .foregroundStyle(PixelTheme.accent)

            Text("Suis la quest chain pour construire ton business etape par etape. C'est le chemin recommande.")
                .font(PixelTheme.microFont)
                .foregroundStyle(PixelTheme.textSecondary)

            HStack {
                Text("\(progress.completed)/\(progress.total) etapes")
                    .font(PixelTheme.captionFont)
                    .foregroundStyle(PixelTheme.accentGreen)
                Spacer()
            }

            if let step = nextStep {
                VStack(alignment: .leading, spacing: 4) {
                    Text("PROCHAINE QUETE")
                        .font(PixelTheme.microFont)
                        .foregroundStyle(PixelTheme.textSecondary)
                    Text(step.title.uppercased())
                        .font(PixelTheme.bodyFont)
                        .foregroundStyle(PixelTheme.textPrimary)
                }
            }

            Button("OUVRIR LA QUEST CHAIN") {
                dismiss()
            }
            .buttonStyle(PixelButtonStyle(color: PixelTheme.accentGreen))
        }
        .pixelCard(highlighted: true)
    }

    private var advancedToggle: some View {
        Button(action: { withAnimation { showAdvancedCatalog = true } }) {
            HStack {
                Text("MODE AVANCE — CATALOGUE (\(appState.catalog.count) missions)")
                    .font(PixelTheme.microFont)
                    .foregroundStyle(PixelTheme.textSecondary)
                Spacer()
                Text("▸")
                    .foregroundStyle(PixelTheme.textSecondary)
            }
            .padding(12)
            .background(PixelTheme.bgMedium, in: RoundedRectangle(cornerRadius: PixelTheme.cardRadius))
        }
        .buttonStyle(.plain)
    }

    private var advancedCatalogSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("CATALOGUE AVANCE")
                .font(PixelTheme.captionFont)
                .foregroundStyle(PixelTheme.textSecondary)

            Text("Reserve aux missions hors parcours. Peut etre overwhelming — prefere la quest chain.")
                .font(PixelTheme.microFont)
                .foregroundStyle(PixelTheme.textSecondary.opacity(0.8))

            ForEach(appState.catalog) { item in
                HStack(spacing: 10) {
                    Text(item.agentType == "builder" ? "🏗" : "📣")
                        .font(.system(size: 20))
                    VStack(alignment: .leading, spacing: 2) {
                        Text(item.title.uppercased())
                            .font(PixelTheme.captionFont)
                            .foregroundStyle(PixelTheme.textPrimary)
                        HStack(spacing: 8) {
                            Text("◆\(item.creditsCost)")
                                .foregroundStyle(PixelTheme.accent)
                            Text("~\(item.estimatedMinutes)min")
                                .foregroundStyle(PixelTheme.textSecondary)
                        }
                        .font(PixelTheme.microFont)
                    }
                    Spacer()
                }
                .pixelCard()
            }
        }
    }
}

struct MissionStatusView: View {
    let mission: Mission

    var body: some View {
        HStack(spacing: 8) {
            statusIcon
            Text(mission.missionType.replacingOccurrences(of: "_", with: " ").uppercased())
                .font(PixelTheme.microFont)
                .foregroundStyle(PixelTheme.textPrimary)
            Spacer()
            Text(mission.status.uppercased())
                .font(PixelTheme.microFont)
                .foregroundStyle(statusColor)
        }
    }

    @ViewBuilder
    private var statusIcon: some View {
        switch mission.status {
        case "completed":
            Text("✓").foregroundStyle(PixelTheme.accentGreen)
        case "failed":
            Text("✕").foregroundStyle(PixelTheme.accentRed)
        case "running", "pending":
            ProgressView().scaleEffect(0.6)
        default:
            Text("•").foregroundStyle(PixelTheme.textSecondary)
        }
    }

    private var statusColor: Color {
        switch mission.status {
        case "completed": return PixelTheme.accentGreen
        case "failed": return PixelTheme.accentRed
        case "running", "pending": return PixelTheme.accent
        default: return PixelTheme.textSecondary
        }
    }
}
