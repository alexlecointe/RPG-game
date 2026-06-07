import SwiftUI

struct LootRevealView: View {
    let mission: Mission
    var onCollect: (() -> Void)?
    @EnvironmentObject private var appState: AppState
    @Environment(\.dismiss) private var dismiss
    @State private var revealed = false
    @State private var xpVisible = false
    @State private var showBetaFeedback = false
    @State private var copied = false

    var body: some View {
        NavigationStack {
            ZStack {
                PixelTheme.bgDark.ignoresSafeArea()

                ScrollView(showsIndicators: false) {
                    VStack(spacing: 20) {
                        Spacer().frame(height: 12)
                        chestAnimation
                        xpBadge
                        qualityBadge
                        deliverableSection
                        actionButtons
                        Spacer().frame(height: 40)
                    }
                    .padding(.horizontal, 16)
                }
            }
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .principal) {
                    Text("LOOT")
                        .font(PixelTheme.headlineFont)
                        .foregroundStyle(PixelTheme.accent)
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button(action: collectLoot) {
                        Text("COLLECTER")
                            .font(PixelTheme.captionFont)
                            .foregroundStyle(PixelTheme.accentGreen)
                    }
                }
            }
            .toolbarBackground(PixelTheme.bgMedium, for: .navigationBar)
            .toolbarBackground(.visible, for: .navigationBar)
            .onAppear {
                // #region agent log
                let dLen = mission.deliverable?.count ?? -1
                let dPreview = mission.deliverable.map { String($0.prefix(100)) } ?? "NIL"
                print("[DEBUG-H2] LootRevealView.onAppear: missionId=\(mission.id) deliverable len=\(dLen) preview='\(dPreview)' format=\(mission.deliverableFormat ?? "nil")")
                // #endregion
                AnalyticsTracker.track("deliverable_viewed", properties: [
                    "mission_type": mission.missionType,
                    "format": mission.deliverableFormat ?? "text",
                ])
                withAnimation(.spring(response: 0.6, dampingFraction: 0.5).delay(0.3)) {
                    revealed = true
                }
                withAnimation(.easeOut(duration: 0.4).delay(0.8)) {
                    xpVisible = true
                }
            }
            .sheet(isPresented: $showBetaFeedback) {
                BetaFeedbackView(mission: mission) {
                    finishCollect()
                }
            }
        }
    }

    private func collectLoot() {
        showBetaFeedback = true
    }

    private func finishCollect() {
        appState.completeQuest("first_deliverable")
        appState.clearJustCompleted(agentType: mission.agentType)
        AnalyticsTracker.track("mission_completed_ui", properties: [
            "mission_type": mission.missionType,
            "quality": mission.qualityScore.map { String(format: "%.0f", $0) } ?? "n/a",
        ])
        onCollect?()
        dismiss()
    }

    // MARK: - Chest

    private var chestAnimation: some View {
        VStack(spacing: 8) {
            Text(revealed ? "🎁" : "📦")
                .font(.system(size: 64))
                .scaleEffect(revealed ? 1.2 : 0.8)
                .rotationEffect(.degrees(revealed ? 0 : -10))
            Text("QUETE TERMINEE !")
                .font(PixelTheme.titleFont)
                .foregroundStyle(PixelTheme.accent)
                .opacity(revealed ? 1 : 0)

            if let title = DeliverableHelper.questStepTitle(for: mission, chain: appState.questChain) {
                Text(title.uppercased())
                    .font(PixelTheme.captionFont)
                    .foregroundStyle(PixelTheme.textSecondary)
            }
        }
    }

    // MARK: - XP

    private var xpBadge: some View {
        Text("+\(mission.xpReward) XP")
            .font(PixelTheme.headlineFont)
            .foregroundStyle(PixelTheme.accentGreen)
            .padding(.horizontal, 20)
            .padding(.vertical, 8)
            .background(PixelTheme.accentGreen.opacity(0.15), in: RoundedRectangle(cornerRadius: PixelTheme.buttonRadius))
            .scaleEffect(xpVisible ? 1.0 : 0.5)
            .opacity(xpVisible ? 1 : 0)
    }

    @ViewBuilder
    private var qualityBadge: some View {
        if let score = mission.qualityScore {
            HStack(spacing: 6) {
                Text("QUALITE")
                    .font(PixelTheme.microFont)
                    .foregroundStyle(PixelTheme.textSecondary)
                Text("\(Int(score.rounded()))/10")
                    .font(PixelTheme.bodyFont)
                    .foregroundStyle(score >= 7 ? PixelTheme.accentGreen : PixelTheme.accent)
                if score >= 9 {
                    Text("EXCELLENT")
                        .font(PixelTheme.microFont)
                        .foregroundStyle(PixelTheme.accentGreen)
                } else if score < 7 {
                    Text("AMELIORABLE")
                        .font(PixelTheme.microFont)
                        .foregroundStyle(PixelTheme.accent)
                }
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 6)
            .background(PixelTheme.bgMedium, in: RoundedRectangle(cornerRadius: 8))
        }
    }

    // MARK: - Content

    private var deliverableSection: some View {
        Group {
            if mission.deliverable != nil {
                VStack(alignment: .leading, spacing: 8) {
                    HStack {
                        Text("LIVRABLE")
                            .font(PixelTheme.captionFont)
                            .foregroundStyle(PixelTheme.textSecondary)
                        Spacer()
                        Text((mission.deliverableFormat ?? "text").uppercased())
                            .font(PixelTheme.microFont)
                            .foregroundStyle(PixelTheme.accent)
                    }
                    DeliverableContentBlock(mission: mission)
                }
                .pixelCard()
            }
        }
    }

    // MARK: - Actions

    private var actionButtons: some View {
        HStack(spacing: 12) {
            if let deliverable = mission.deliverable {
                Button(action: {
                    UIPasteboard.general.string = deliverable
                    copied = true
                    AnalyticsTracker.track("deliverable_copied", properties: [
                        "mission_type": mission.missionType,
                    ])
                }) {
                    HStack(spacing: 4) {
                        Text(copied ? "✓" : "📋")
                        Text(copied ? "COPIE !" : DeliverableHelper.copyButtonLabel(for: mission.missionType))
                    }
                    .frame(maxWidth: .infinity)
                }
                .buttonStyle(PixelButtonStyle(color: PixelTheme.bgLight))

                ShareLink(item: deliverable) {
                    HStack(spacing: 4) {
                        Text("📤")
                        Text("PARTAGER")
                    }
                    .font(PixelTheme.bodyFont)
                    .foregroundStyle(PixelTheme.bgDark)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 10)
                    .background(PixelTheme.accent, in: RoundedRectangle(cornerRadius: PixelTheme.buttonRadius))
                }
            }
        }
    }
}
