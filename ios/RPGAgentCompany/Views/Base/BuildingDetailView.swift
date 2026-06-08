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
                        polisiaProductPanel
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

    @ViewBuilder
    private var polisiaProductPanel: some View {
        if building.agentType == "builder", let url = appState.company?.siteUrl, !url.isEmpty {
            WebsiteLivePanel(siteUrl: url)
        } else if building.agentType == "finance" {
            SetupPaymentsPanel()
                .environmentObject(appState)
        } else if building.agentType == "marketer" {
            AdsBudgetPanel()
                .environmentObject(appState)
        }
    }

    private var questList: some View {
        let completedSteps = appState.completedQuestSteps(agentType: building.agentType)
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

            let allSteps = appState.allQuestStepsForBuilding(agentType: building.agentType)
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
        case "orchestrator": return "Recherche marche, docs et strategie business."
        case "builder": return "Genere et heberge ton site web live."
        case "marketer": return "Videos ads et campagnes Meta."
        case "finance": return "Stripe Connect et payouts."
        default: return "Un batiment du village."
        }
    }
}

// MARK: - Polsia product panels

struct WebsiteLivePanel: View {
    let siteUrl: String
    @State private var copied = false

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("SITE LIVE")
                .font(PixelTheme.captionFont)
                .foregroundStyle(PixelTheme.accentGreen)
            Text(siteUrl)
                .font(PixelTheme.microFont)
                .foregroundStyle(PixelTheme.textSecondary)
                .lineLimit(2)
            HStack(spacing: 10) {
                if let url = URL(string: siteUrl) {
                    Link(destination: url) {
                        Text("OUVRIR")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(PixelButtonStyle(color: PixelTheme.accentGreen))
                }
                Button(action: {
                    UIPasteboard.general.string = siteUrl
                    copied = true
                }) {
                    Text(copied ? "COPIE !" : "COPIER")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(PixelButtonStyle(color: PixelTheme.bgLight))
            }
        }
        .pixelCard(highlighted: true)
    }
}

struct SetupPaymentsPanel: View {
    @EnvironmentObject private var appState: AppState
    @State private var isLoading = false
    @State private var error: String?

    private var statusLabel: String {
        switch appState.company?.stripeConnectStatus ?? "not_started" {
        case "ready": return "Connecte"
        case "pending": return "En attente"
        default: return "Non configure"
        }
    }

    private var statusColor: Color {
        switch appState.company?.stripeConnectStatus ?? "not_started" {
        case "ready": return PixelTheme.accentGreen
        case "pending": return PixelTheme.accent
        default: return PixelTheme.textSecondary
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text("PAIEMENTS")
                    .font(PixelTheme.captionFont)
                    .foregroundStyle(PixelTheme.textSecondary)
                Spacer()
                Text(statusLabel.uppercased())
                    .font(PixelTheme.microFont)
                    .foregroundStyle(statusColor)
            }
            if let error {
                Text(error)
                    .font(PixelTheme.microFont)
                    .foregroundStyle(PixelTheme.accentRed)
            }
            if appState.company?.stripeConnectStatus != "ready" {
                Button(action: { Task { await setupPayments() } }) {
                    HStack {
                        if isLoading { ProgressView().scaleEffect(0.7) }
                        Text(isLoading ? "CHARGEMENT..." : "SETUP PAYMENTS")
                    }
                    .frame(maxWidth: .infinity)
                }
                .buttonStyle(PixelButtonStyle(color: PixelTheme.accent))
                .disabled(isLoading)
            }
        }
        .pixelCard(highlighted: true)
    }

    private func setupPayments() async {
        guard let companyId = appState.company?.id else { return }
        isLoading = true
        error = nil
        defer { isLoading = false }
        do {
            let urlString = try await APIClient.shared.startStripeOnboarding(companyId: companyId)
            guard let url = URL(string: urlString), !urlString.isEmpty else {
                error = "Lien onboarding indisponible"
                return
            }
            await UIApplication.shared.open(url)
            await appState.refreshCompany()
        } catch {
            self.error = error.localizedDescription
        }
    }
}

struct AdsBudgetPanel: View {
    @EnvironmentObject private var appState: AppState
    @State private var budgetEuros: Double = 10
    @State private var isSaving = false
    @State private var message: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("BUDGET ADS")
                .font(PixelTheme.captionFont)
                .foregroundStyle(PixelTheme.textSecondary)
            if let daily = appState.company?.dailyAdsBudgetCents, daily > 0 {
                Text("Budget : \(daily / 100) EUR/jour")
                    .font(PixelTheme.bodyFont)
                    .foregroundStyle(PixelTheme.textPrimary)
            }
            if let balance = appState.company?.adsWalletBalanceCents {
                Text("Wallet : \(balance / 100) EUR")
                    .font(PixelTheme.captionFont)
                    .foregroundStyle(PixelTheme.textSecondary)
            }
            HStack {
                Slider(value: $budgetEuros, in: 5...100, step: 5)
                Text("\(Int(budgetEuros))€")
                    .font(PixelTheme.captionFont)
                    .foregroundStyle(PixelTheme.accent)
                    .frame(width: 36)
            }
            Button(action: { Task { await saveBudget() } }) {
                Text(isSaving ? "..." : "DEFINIR BUDGET")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(PixelButtonStyle(color: PixelTheme.accentPurple))
            .disabled(isSaving)
            if let message {
                Text(message)
                    .font(PixelTheme.microFont)
                    .foregroundStyle(PixelTheme.accentGreen)
            }
        }
        .pixelCard()
        .onAppear {
            if let daily = appState.company?.dailyAdsBudgetCents, daily > 0 {
                budgetEuros = Double(daily / 100)
            }
        }
    }

    private func saveBudget() async {
        guard let companyId = appState.company?.id else { return }
        isSaving = true
        defer { isSaving = false }
        do {
            try await APIClient.shared.setAdsBudget(companyId: companyId, dailyBudgetCents: Int(budgetEuros) * 100)
            await appState.refreshCompany()
            message = "Budget enregistre"
        } catch {
            message = error.localizedDescription
        }
    }
}

extension Mission: Hashable {
    static func == (lhs: Mission, rhs: Mission) -> Bool { lhs.id == rhs.id }
    func hash(into hasher: inout Hasher) { hasher.combine(id) }
}
