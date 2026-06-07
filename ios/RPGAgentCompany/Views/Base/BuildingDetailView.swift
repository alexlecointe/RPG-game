import SwiftUI

struct BuildingDetailView: View {
    @EnvironmentObject private var appState: AppState
    @Environment(\.dismiss) private var dismiss
    let building: Building
    @State private var lootMission: Mission?

    var body: some View {
        NavigationStack {
            ZStack {
                PixelTheme.bgDark.ignoresSafeArea()

                ScrollView {
                    VStack(spacing: 16) {
                        buildingHeader
                        questList
                    }
                    .padding(16)
                }
            }
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .principal) {
                    Text(building.displayName.uppercased())
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
            .sheet(item: $lootMission) { mission in
                LootRevealView(mission: mission)
                    .environmentObject(appState)
            }
        }
    }

    private var buildingHeader: some View {
        HStack(spacing: 12) {
            ZStack {
                RoundedRectangle(cornerRadius: 8)
                    .fill(agentColor.opacity(0.2))
                    .frame(width: 64, height: 64)
                Text(agentEmoji)
                    .font(.system(size: 32))
            }
            VStack(alignment: .leading, spacing: 4) {
                HStack(spacing: 6) {
                    Text("NIVEAU \(building.level)")
                        .font(PixelTheme.captionFont)
                        .foregroundStyle(agentColor)
                    ForEach(0..<building.level, id: \.self) { _ in
                        Text("★")
                            .font(PixelTheme.microFont)
                            .foregroundStyle(PixelTheme.accent)
                    }
                }
                Text(agentDescription)
                    .font(PixelTheme.captionFont)
                    .foregroundStyle(PixelTheme.textSecondary)
            }
        }
        .pixelCard()
    }

    private var questList: some View {
        let completedSteps = appState.questChain.filter { $0.agentType == building.agentType && $0.isCompleted }
        let lockedSteps = appState.lockedQuestSteps(agentType: building.agentType)

        return VStack(spacing: 10) {
            if let chainStep = appState.questStepForBuilding(agentType: building.agentType) {
                questChainCard(step: chainStep)
            }

            if !lockedSteps.isEmpty {
                Text("— QUÊTES À DÉBLOQUER —")
                    .font(PixelTheme.captionFont)
                    .foregroundStyle(PixelTheme.textSecondary)

                ForEach(lockedSteps, id: \.id) { step in
                    lockedQuestCard(step: step)
                }
            }

            if !completedSteps.isEmpty {
                Text("— QUÊTES TERMINÉES —")
                    .font(PixelTheme.captionFont)
                    .foregroundStyle(PixelTheme.textSecondary)

                ForEach(completedSteps, id: \.id) { step in
                    completedQuestCard(step: step)
                }
            }

            let allSteps = appState.questChain.filter { $0.agentType == building.agentType }
            if allSteps.isEmpty {
                Text("Aucune quête assignée à ce bâtiment.")
                    .font(PixelTheme.captionFont)
                    .foregroundStyle(PixelTheme.textSecondary)
                    .padding(.top, 8)
            }
        }
    }

    @ViewBuilder
    private func lockedQuestCard(step: QuestStep) -> some View {
        let prereqs = appState.prerequisiteNames(for: step)

        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: "lock.fill")
                    .font(.system(size: 12))
                    .foregroundStyle(PixelTheme.textSecondary)

                Text("ETAPE \(step.stepNumber)")
                    .font(PixelTheme.microFont)
                    .foregroundStyle(PixelTheme.textSecondary)

                Spacer()

                Text("VERROUILLÉ")
                    .font(PixelTheme.microFont)
                    .foregroundStyle(PixelTheme.textSecondary)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(PixelTheme.bgDark, in: RoundedRectangle(cornerRadius: 3))
            }

            Text(step.title.uppercased())
                .font(PixelTheme.bodyFont)
                .foregroundStyle(PixelTheme.textSecondary)

            Text(step.description)
                .font(PixelTheme.captionFont)
                .foregroundStyle(PixelTheme.textSecondary.opacity(0.7))

            if !prereqs.isEmpty {
                VStack(alignment: .leading, spacing: 2) {
                    Text("NÉCESSITE :")
                        .font(PixelTheme.microFont)
                        .foregroundStyle(PixelTheme.accentRed)
                    ForEach(prereqs, id: \.self) { prereq in
                        HStack(spacing: 4) {
                            Text("•")
                            Text(prereq)
                        }
                        .font(PixelTheme.microFont)
                        .foregroundStyle(PixelTheme.textSecondary)
                    }
                }
            }
        }
        .pixelCard()
        .opacity(0.5)
    }

    @ViewBuilder
    private func completedQuestCard(step: QuestStep) -> some View {
        Button(action: { openLoot(for: step) }) {
            HStack(spacing: 12) {
                ZStack {
                    Circle()
                        .fill(PixelTheme.accentGreen.opacity(0.2))
                        .frame(width: 36, height: 36)
                    Image(systemName: "checkmark")
                        .font(.system(size: 14, weight: .bold))
                        .foregroundStyle(PixelTheme.accentGreen)
                }

                VStack(alignment: .leading, spacing: 2) {
                    HStack {
                        Text("ETAPE \(step.stepNumber)")
                            .font(PixelTheme.microFont)
                            .foregroundStyle(PixelTheme.accentGreen)
                        Spacer()
                        Text("VOIR LOOT")
                            .font(PixelTheme.microFont)
                            .foregroundStyle(PixelTheme.accent)
                    }
                    Text(step.title.uppercased())
                        .font(PixelTheme.captionFont)
                        .foregroundStyle(PixelTheme.textPrimary)
                }
            }
            .pixelCard()
        }
        .buttonStyle(.plain)
    }

    private func openLoot(for step: QuestStep) {
        if let missionId = step.missionId,
           let mission = appState.missions.first(where: { $0.id == missionId && $0.deliverable != nil }) {
            lootMission = mission
            return
        }
        if let mission = appState.missions.first(where: {
            $0.missionType == step.missionType && $0.status == "completed" && $0.deliverable != nil
        }) {
            lootMission = mission
        }
    }

    @ViewBuilder
    private func questChainCard(step: QuestStep) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text("ETAPE \(step.stepNumber)")
                    .font(PixelTheme.microFont)
                    .foregroundStyle(PixelTheme.bgDark)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 3)
                    .background(PixelTheme.accent, in: RoundedRectangle(cornerRadius: 4))

                Text("QUEST CHAIN")
                    .font(PixelTheme.microFont)
                    .foregroundStyle(PixelTheme.accent)

                Spacer()
            }

            Text(step.title.uppercased())
                .font(PixelTheme.bodyFont)
                .foregroundStyle(PixelTheme.textPrimary)

            Text(step.description)
                .font(PixelTheme.captionFont)
                .foregroundStyle(PixelTheme.textSecondary)

            if step.isAvailable {
                Button(action: {
                    Task {
                        await appState.startQuestStep(stepNumber: step.stepNumber)
                        await appState.fetchQuestChain()
                    }
                }) {
                    HStack {
                        if appState.isLoading {
                            ProgressView().tint(PixelTheme.bgDark).scaleEffect(0.7)
                        }
                        Text(appState.isLoading ? "EN COURS..." : "LANCER L'ÉTAPE")
                    }
                    .frame(maxWidth: .infinity)
                }
                .buttonStyle(PixelButtonStyle(color: PixelTheme.accentGreen))
                .disabled(appState.isLoading)
            } else if step.isRunning {
                HStack(spacing: 6) {
                    ProgressView().scaleEffect(0.7).tint(PixelTheme.accent)
                    Text("MISSION EN COURS...")
                        .font(PixelTheme.captionFont)
                        .foregroundStyle(PixelTheme.accent)
                }
            }
        }
        .pixelCard(highlighted: true)
    }

    private var agentColor: Color {
        switch building.agentType {
        case "builder": return PixelTheme.accentBlue
        case "marketer": return PixelTheme.accentPurple
        case "researcher": return PixelTheme.accentGreen
        case "orchestrator": return PixelTheme.accent
        case "outreach": return Color(red: 0.95, green: 0.55, blue: 0.20)
        case "support": return Color(red: 0.40, green: 0.80, blue: 0.80)
        case "finance": return Color(red: 0.85, green: 0.75, blue: 0.20)
        case "content": return Color(red: 0.80, green: 0.45, blue: 0.65)
        default: return PixelTheme.accent
        }
    }

    private var agentEmoji: String {
        switch building.agentType {
        case "builder": return "🏗"
        case "marketer": return "📣"
        case "researcher": return "🔬"
        case "orchestrator": return "👑"
        case "outreach": return "📬"
        case "support": return "🛎"
        case "finance": return "🏦"
        case "content": return "🎨"
        default: return "🏠"
        }
    }

    private var agentDescription: String {
        switch building.agentType {
        case "builder": return "Code des landings, sites et briefs produit."
        case "marketer": return "Ecrit des pubs, posts et campagnes ads."
        case "researcher": return "Analyse le marche et genere des insights."
        case "orchestrator": return "Coordonne les agents et definit la strategie."
        case "outreach": return "Gere la prospection et les cold emails."
        case "support": return "Repond aux clients et gere le support."
        case "finance": return "Suit les revenus, depenses et budget."
        case "content": return "Cree articles, visuels et documents."
        default: return "Un batiment du village."
        }
    }
}

extension Mission: Hashable {
    static func == (lhs: Mission, rhs: Mission) -> Bool { lhs.id == rhs.id }
    func hash(into hasher: inout Hasher) { hasher.combine(id) }
}
