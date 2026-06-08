import SwiftUI

struct BuildingDetailView: View {
    @EnvironmentObject private var appState: AppState
    @Environment(\.dismiss) private var dismiss
    let building: Building
    @State private var lootMission: Mission?
    @State private var showPaywall = false

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
            .sheet(isPresented: $showPaywall) {
                if let companyId = appState.company?.id {
                    PaywallView(companyId: companyId)
                        .environmentObject(appState)
                        .onDisappear { Task { await appState.fetchSubscription() } }
                }
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
            AdsLiveDashboard()
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
                let totalCredits = appState.subscription?.totalCredits ?? (appState.company?.wallet.creditsBalance ?? 1)
                let hasCredits = totalCredits > 0

                if hasCredits {
                    VStack(spacing: 4) {
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
                                Text(appState.isLoading ? "AJOUT EN COURS..." : "AJOUTER À LA QUEUE")
                            }
                            .frame(maxWidth: .infinity)
                        }
                        .buttonStyle(PixelButtonStyle(color: PixelTheme.accentGreen))
                        .disabled(appState.isLoading)

                        Text("0 CR maintenant · 1 CR débité à l'exécution")
                            .font(PixelTheme.microFont)
                            .foregroundStyle(PixelTheme.textSecondary)
                    }
                } else {
                    VStack(spacing: 6) {
                        Text("PLUS DE CRÉDITS")
                            .font(PixelTheme.captionFont)
                            .foregroundStyle(PixelTheme.accentRed)
                        Button(action: { showPaywall = true }) {
                            HStack(spacing: 6) {
                                Image(systemName: "bolt.fill")
                                Text("ACHETER DES CRÉDITS")
                            }
                            .frame(maxWidth: .infinity)
                        }
                        .buttonStyle(PixelButtonStyle(color: PixelTheme.accentRed))
                    }
                }
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

// MARK: - AdCampaignCard (reusable)

struct AdCampaignCard: View {
    let campaign: AdCampaign

    private var statusColor: Color {
        switch campaign.status {
        case "active": return PixelTheme.accentGreen
        case "blocked": return PixelTheme.accentRed
        default: return PixelTheme.textSecondary
        }
    }

    var body: some View {
        HStack(spacing: 10) {
            // Thumbnail (AsyncImage if available, grey rect fallback)
            Group {
                if let urlStr = campaign.thumbnailUrl, let url = URL(string: urlStr) {
                    AsyncImage(url: url) { phase in
                        switch phase {
                        case .success(let img):
                            img.resizable().scaledToFill()
                        default:
                            thumbnailPlaceholder
                        }
                    }
                } else {
                    thumbnailPlaceholder
                }
            }
            .frame(width: 52, height: 52)
            .clipShape(RoundedRectangle(cornerRadius: 6))

            VStack(alignment: .leading, spacing: 3) {
                HStack(spacing: 6) {
                    Text(campaign.name)
                        .font(PixelTheme.captionFont)
                        .foregroundStyle(PixelTheme.textPrimary)
                        .lineLimit(1)
                    Text(campaign.statusDisplay)
                        .font(PixelTheme.microFont)
                        .foregroundStyle(statusColor)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(statusColor.opacity(0.12), in: Capsule())

                }
                Text("\(campaign.spendFormatted) spend  \(campaign.impressions.formatted()) impr  \(campaign.clicks) clicks  CTR: \(campaign.ctrFormatted)  CPC: \(campaign.cpcFormatted)")
                    .font(PixelTheme.microFont)
                    .foregroundStyle(PixelTheme.textSecondary)
                    .lineLimit(2)
                if let thruplay = campaign.videoThruplaysWatched, thruplay > 0 {
                    Text("\(thruplay.formatted()) video completions")
                        .font(PixelTheme.microFont)
                        .foregroundStyle(PixelTheme.accentPurple)
                }
            }
            Spacer(minLength: 0)
        }
        .padding(10)
        .background(PixelTheme.bgMedium, in: RoundedRectangle(cornerRadius: 8))
    }

    private var thumbnailPlaceholder: some View {
        RoundedRectangle(cornerRadius: 6)
            .fill(PixelTheme.bgDark)
            .overlay(
                Image(systemName: "play.rectangle.fill")
                    .font(.system(size: 16))
                    .foregroundStyle(PixelTheme.textSecondary.opacity(0.5))
            )
    }
}

// Extend AdCampaign with thumbnailUrl sourced from its first creative
private extension AdCampaign {
    var thumbnailUrl: String? { nil }
}

// MARK: - AdsLiveDashboard (Polsia-like compact view)

struct AdsLiveDashboard: View {
    @EnvironmentObject private var appState: AppState
    @State private var summary: AdsSummary?
    @State private var isLoading = false
    @State private var isPausingAll = false
    @State private var showDetails = false
    @State private var actionMessage: String?
    @State private var pollingTask: Task<Void, Never>?

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // State header
            stateHeader

            // Contextual message
            if let msg = summary?.stateMessage {
                Text(msg)
                    .font(PixelTheme.microFont)
                    .foregroundStyle(PixelTheme.textSecondary)
                    .fixedSize(horizontal: false, vertical: true)
            }

            // Campaign cards
            if let summary, !summary.campaigns.isEmpty {
                VStack(spacing: 6) {
                    ForEach(summary.campaigns) { campaign in
                        AdCampaignCard(campaign: campaign)
                    }
                }

                // Primary CTA button
                resumeButton(summary: summary)
            }

            // Footer: Details + Refresh
            HStack(spacing: 16) {
                Button("Details →") { showDetails = true }
                    .font(PixelTheme.captionFont)
                    .foregroundStyle(PixelTheme.textSecondary)
                Button("Refresh") { Task { await loadSummary() } }
                    .font(PixelTheme.captionFont)
                    .foregroundStyle(PixelTheme.textSecondary)
                Spacer()
                if isLoading {
                    ProgressView().scaleEffect(0.6).tint(PixelTheme.textSecondary)
                }
            }

            if let actionMessage {
                Text(actionMessage)
                    .font(PixelTheme.microFont)
                    .foregroundStyle(PixelTheme.accentGreen)
            }
        }
        .onAppear { startPolling() }
        .onDisappear { pollingTask?.cancel() }
        .sheet(isPresented: $showDetails) {
            AdsDetailsSheet(summary: summary)
                .environmentObject(appState)
        }
    }

    // MARK: State header

    private var stateHeader: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(spacing: 6) {
                Circle()
                    .fill(stateColor)
                    .frame(width: 8, height: 8)
                Text(summary?.stateDisplay ?? "Ads")
                    .font(PixelTheme.bodyFont)
                    .foregroundStyle(PixelTheme.textPrimary)
            }
            if let summary, !summary.campaigns.isEmpty {
                let paused = summary.pausedCount
                let spend = summary.totalSpendFormatted
                Text("\(paused) paused · \(spend) Meta spend")
                    .font(PixelTheme.microFont)
                    .foregroundStyle(PixelTheme.textSecondary)
            }
        }
    }

    private var stateColor: Color {
        switch summary?.state {
        case "running": return PixelTheme.accentGreen
        case "warming_up": return PixelTheme.accent
        case "delivery_blocked", "stale_no_delivery",
             "card_expired", "payment_method_missing": return PixelTheme.accentRed
        default: return PixelTheme.textSecondary
        }
    }

    // MARK: Resume/Pause button

    private func resumeButton(summary: AdsSummary) -> some View {
        Button(action: { Task { await toggleAllCampaigns(pause: summary.allActive) } }) {
            HStack(spacing: 6) {
                if isPausingAll { ProgressView().scaleEffect(0.7).tint(.white) }
                Text(summary.allActive ? "PAUSE ADS" : "RESUME ADS")
                    .frame(maxWidth: .infinity)
            }
        }
        .buttonStyle(PixelButtonStyle(color: summary.allActive ? PixelTheme.accentRed : PixelTheme.accentGreen))
        .disabled(isPausingAll)
    }

    // MARK: Actions

    private func startPolling() {
        pollingTask?.cancel()
        pollingTask = Task {
            while !Task.isCancelled {
                await loadSummary()
                try? await Task.sleep(nanoseconds: 30_000_000_000)
            }
        }
    }

    func loadSummary() async {
        guard let companyId = appState.company?.id else { return }
        isLoading = summary == nil
        do {
            let s = try await APIClient.shared.fetchAdsSummary(companyId: companyId)
            await MainActor.run { summary = s; isLoading = false }
        } catch {
            await MainActor.run { isLoading = false }
        }
    }

    private func toggleAllCampaigns(pause: Bool) async {
        guard let companyId = appState.company?.id else { return }
        guard let campaigns = summary?.campaigns else { return }
        isPausingAll = true
        defer { Task { @MainActor in isPausingAll = false } }
        do {
            for campaign in campaigns {
                if pause {
                    try await APIClient.shared.pauseAdsCampaign(companyId: companyId, campaignId: campaign.id)
                } else {
                    try await APIClient.shared.resumeAdsCampaign(companyId: companyId, campaignId: campaign.id)
                }
            }
            await loadSummary()
            actionMessage = pause ? "Ads paused" : "Ads resumed"
            Task { try? await Task.sleep(nanoseconds: 2_000_000_000); await MainActor.run { actionMessage = nil } }
        } catch {}
    }
}

// MARK: - AdsDetailsSheet

struct AdsDetailsSheet: View {
    @EnvironmentObject private var appState: AppState
    @Environment(\.dismiss) private var dismiss
    let summary: AdsSummary?

    @State private var localSummary: AdsSummary?
    @State private var transactions: [WalletTransaction] = []
    @State private var isLoadingTransactions = false
    @State private var budgetDollars: Double = 10
    @State private var isSavingBudget = false
    @State private var isChargingWallet = false
    @State private var actionMessage: String?
    @State private var isBalanceExplainerOpen = false
    @State private var applyingRecoId: String?

    private var activeSummary: AdsSummary? { localSummary ?? summary }

    private func reloadSummary() async {
        guard let companyId = appState.company?.id else { return }
        if let s = try? await APIClient.shared.fetchAdsSummary(companyId: companyId) {
            await MainActor.run { localSummary = s }
        }
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    // Balance + Daily Budget cards
                    balanceBudgetCards

                    // 7-Day Spend
                    spendRollupSection

                    // AI Agent Activity
                    agentActivitySection

                    // Recommendations
                    if let s = activeSummary, !s.campaigns.isEmpty {
                        let recos = recommendations(campaigns: s.campaigns)
                        if !recos.isEmpty {
                            recommendationsSection(recos: recos)
                        }
                    }

                    // Your Ads
                    if let s = activeSummary, !s.campaigns.isEmpty {
                        adsListSection(summary: s)
                    }

                    // How Your Ads Balance Works accordion
                    balanceExplainerSection

                    // Transaction History
                    transactionHistorySection

                    // Budget controls (moved from main view)
                    budgetControlsSection
                }
                .padding(16)
            }
            .navigationTitle("Ads Details")
            .navigationBarTitleDisplayMode(.large)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Close") { dismiss() }
                        .font(PixelTheme.captionFont)
                }
            }
        }
        .onAppear {
            if let daily = appState.company?.dailyAdsBudgetCents, daily > 0 {
                budgetDollars = max(10, Double(daily / 100))
            }
            Task { await loadTransactions() }
        }
    }

    // MARK: Balance + Daily Budget

    private var balanceBudgetCards: some View {
        HStack(spacing: 12) {
            balanceCard(
                label: "Current Balance",
                value: summary?.walletFormatted ?? "$0.00"
            )
            balanceCard(
                label: "Daily Budget",
                value: (summary?.dailyBudgetFormatted ?? "$0.00") + "/day"
            )
        }
    }

    private func balanceCard(label: String, value: String) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label)
                .font(PixelTheme.microFont)
                .foregroundStyle(PixelTheme.textSecondary)
            Text(value)
                .font(PixelTheme.titleFont)
                .foregroundStyle(PixelTheme.textPrimary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(14)
        .background(PixelTheme.bgMedium, in: RoundedRectangle(cornerRadius: 10))
    }

    // MARK: 7-Day Spend Rollup

    private var spendRollupSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("7-Day Spend")
                .font(PixelTheme.headlineFont)
                .foregroundStyle(PixelTheme.textPrimary)

            if let rollup = summary?.spendRollup7d, rollup.contains(where: { $0 > 0 }) {
                let maxVal = rollup.max() ?? 1
                HStack(alignment: .bottom, spacing: 4) {
                    ForEach(Array(rollup.enumerated()), id: \.offset) { idx, val in
                        let height = maxVal > 0 ? max(4, CGFloat(val) / CGFloat(maxVal) * 40) : 4
                        VStack(spacing: 2) {
                            RoundedRectangle(cornerRadius: 2)
                                .fill(PixelTheme.accentPurple)
                                .frame(height: height)
                            Text(dayLabel(daysAgo: 6 - idx))
                                .font(PixelTheme.microFont)
                                .foregroundStyle(PixelTheme.textSecondary)
                        }
                        .frame(maxWidth: .infinity)
                    }
                }
                .frame(height: 60)
            } else {
                Text("No spend data yet.")
                    .font(PixelTheme.bodyFont)
                    .foregroundStyle(PixelTheme.textSecondary)
            }
        }
    }

    private func dayLabel(daysAgo: Int) -> String {
        let days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
        let cal = Calendar.current
        let date = cal.date(byAdding: .day, value: -daysAgo, to: Date()) ?? Date()
        return days[cal.component(.weekday, from: date) - 1]
    }

    // MARK: AI Agent Activity

    private var agentActivitySection: some View {
        let adsEntries = appState.agentActivityFeed.filter {
            $0.agentType == "marketer" || $0.message.lowercased().contains("ad")
        }.prefix(5)

        return VStack(alignment: .leading, spacing: 8) {
            Text("AI Agent Activity")
                .font(PixelTheme.headlineFont)
                .foregroundStyle(PixelTheme.textPrimary)

            if adsEntries.isEmpty {
                Text("No agent activity yet.")
                    .font(PixelTheme.bodyFont)
                    .foregroundStyle(PixelTheme.textSecondary)
            } else {
                ForEach(Array(adsEntries.enumerated()), id: \.offset) { _, entry in
                    HStack(alignment: .top, spacing: 10) {
                        Text(relativeDate(entry.createdAt))
                            .font(PixelTheme.microFont)
                            .foregroundStyle(PixelTheme.textSecondary)
                            .frame(width: 50, alignment: .leading)
                        Text(entry.message)
                            .font(PixelTheme.microFont)
                            .foregroundStyle(PixelTheme.textPrimary)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    Divider()
                }
            }
        }
    }

    private func relativeDate(_ iso: String?) -> String {
        guard let iso else { return "" }
        let fmt = ISO8601DateFormatter()
        fmt.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        let fmt2 = ISO8601DateFormatter()
        guard let date = fmt.date(from: iso) ?? fmt2.date(from: iso) else { return "" }
        let diff = Date().timeIntervalSince(date)
        if diff < 3600 { return "\(Int(diff / 60))m ago" }
        if diff < 86400 { return "\(Int(diff / 3600))h ago" }
        let df = DateFormatter(); df.dateFormat = "MMM d"
        return df.string(from: date)
    }

    // MARK: Recommendations

    private enum RecoKind { case scale, splitTest }
    private struct Reco: Identifiable {
        let id: String        // campaign.id + kind
        let campaign: AdCampaign
        let kind: RecoKind
        var title: String { kind == .scale ? "Scale budget +20%" : "Apply split test winner" }
        var subtitle: String {
            if kind == .scale {
                let roas = String(format: "%.1f×", campaign.purchaseRoas ?? 0)
                return "\(campaign.name) · ROAS \(roas)"
            } else {
                let days = (campaign.hoursSinceActivation ?? 0) / 24
                return "\(campaign.name) · \(days) days active"
            }
        }
    }

    private func recommendations(campaigns: [AdCampaign]) -> [Reco] {
        var recos: [Reco] = []
        for c in campaigns where c.status == "active" {
            if let roas = c.purchaseRoas, roas >= 2.0 {
                recos.append(Reco(id: c.id + "_scale", campaign: c, kind: .scale))
            }
            if let hours = c.hoursSinceActivation, hours >= 5 * 24 {
                recos.append(Reco(id: c.id + "_split", campaign: c, kind: .splitTest))
            }
        }
        return recos
    }

    private func recommendationsSection(recos: [Reco]) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 6) {
                Image(systemName: "lightbulb.fill")
                    .foregroundStyle(Color.yellow)
                    .font(.system(size: 14))
                Text("AI Recommendations")
                    .font(PixelTheme.headlineFont)
                    .foregroundStyle(PixelTheme.textPrimary)
            }
            ForEach(recos) { reco in
                HStack(alignment: .top, spacing: 12) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text(reco.title)
                            .font(PixelTheme.captionFont)
                            .foregroundStyle(PixelTheme.textPrimary)
                        Text(reco.subtitle)
                            .font(PixelTheme.microFont)
                            .foregroundStyle(PixelTheme.textSecondary)
                    }
                    Spacer()
                    Button {
                        Task { await applyReco(reco) }
                    } label: {
                        if applyingRecoId == reco.id {
                            ProgressView()
                                .scaleEffect(0.8)
                                .frame(width: 64, height: 28)
                        } else {
                            Text("Apply")
                                .font(PixelTheme.captionFont)
                                .foregroundStyle(.white)
                                .padding(.horizontal, 12)
                                .padding(.vertical, 6)
                                .background(PixelTheme.accentGreen, in: RoundedRectangle(cornerRadius: 6))
                        }
                    }
                    .disabled(applyingRecoId != nil)
                }
                .padding(12)
                .background(PixelTheme.bgMedium, in: RoundedRectangle(cornerRadius: 10))
            }
        }
    }

    private func applyReco(_ reco: Reco) async {
        guard let companyId = appState.company?.id else { return }
        applyingRecoId = reco.id
        defer { applyingRecoId = nil }
        do {
            switch reco.kind {
            case .scale:
                try await APIClient.shared.applyScaleCampaign(companyId: companyId, campaignId: reco.campaign.id)
                actionMessage = "Budget scaled +20% ✓"
            case .splitTest:
                try await APIClient.shared.applySplitWinner(companyId: companyId, campaignId: reco.campaign.id)
                actionMessage = "Split winner applied ✓"
            }
            await reloadSummary()
        } catch {
            actionMessage = "Error: \(error.localizedDescription)"
        }
    }

    // MARK: Your Ads list

    private func adsListSection(summary: AdsSummary) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Your Ads (\(summary.campaigns.count))")
                .font(PixelTheme.headlineFont)
                .foregroundStyle(PixelTheme.textPrimary)
            ForEach(summary.campaigns) { campaign in
                AdCampaignCard(campaign: campaign)
            }
        }
    }

    // MARK: Balance Explainer accordion

    private var balanceExplainerSection: some View {
        VStack(alignment: .leading, spacing: 0) {
            Button(action: { withAnimation(.easeInOut(duration: 0.2)) { isBalanceExplainerOpen.toggle() } }) {
                HStack {
                    Text("How Your Ads Balance Works")
                        .font(PixelTheme.captionFont)
                        .foregroundStyle(PixelTheme.textPrimary)
                    Spacer()
                    Image(systemName: isBalanceExplainerOpen ? "chevron.up" : "chevron.down")
                        .font(.system(size: 12))
                        .foregroundStyle(PixelTheme.textSecondary)
                }
                .padding(12)
            }

            if isBalanceExplainerOpen {
                VStack(alignment: .leading, spacing: 10) {
                    explainerRow(
                        title: "Daily top-up",
                        body: "Each morning, your card is charged your daily budget. 80% goes to Meta for ad delivery, 20% is the Polsia platform fee."
                    )
                    explainerRow(
                        title: "Delivery",
                        body: "Meta spreads your budget across the day, optimizing for the best audience. Your AI agent monitors performance and pauses underperforming ads."
                    )
                    explainerRow(
                        title: "Nightly reconciliation",
                        body: "Actual Meta spend is synced hourly. If Meta under-delivered, the unspent portion rolls into tomorrow's balance."
                    )
                    explainerRow(
                        title: "Meta pacing variability",
                        body: "Meta may spend more on some days and less on others to hit your average budget. Daily spend can vary by up to 25%."
                    )
                    explainerRow(
                        title: "Reporting lag",
                        body: "Meta's reporting data lags ~15 minutes behind actual delivery. Today's spend shown here is an estimate until the day ends."
                    )
                }
                .padding(.horizontal, 12)
                .padding(.bottom, 12)
            }
        }
        .background(PixelTheme.bgMedium, in: RoundedRectangle(cornerRadius: 10))
    }

    private func explainerRow(title: String, body: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(title + ":").font(PixelTheme.captionFont).foregroundStyle(PixelTheme.textPrimary) +
            Text(" " + body).font(PixelTheme.microFont).foregroundStyle(PixelTheme.textSecondary)
        }
        .fixedSize(horizontal: false, vertical: true)
    }

    // MARK: Transaction History

    private var transactionHistorySection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Transaction History")
                .font(PixelTheme.headlineFont)
                .foregroundStyle(PixelTheme.textPrimary)

            if isLoadingTransactions {
                ProgressView().tint(PixelTheme.textSecondary)
            } else if transactions.isEmpty {
                Text("No transactions yet.")
                    .font(PixelTheme.bodyFont)
                    .foregroundStyle(PixelTheme.textSecondary)
            } else {
                let grouped = groupedTransactions()
                ForEach(grouped, id: \.date) { group in
                    Text(group.date.uppercased())
                        .font(PixelTheme.microFont)
                        .foregroundStyle(PixelTheme.textSecondary)
                        .padding(.top, 6)
                    ForEach(group.transactions) { txn in
                        HStack {
                            VStack(alignment: .leading, spacing: 1) {
                                Text(txnTimeFormatted(txn.createdAt))
                                    .font(PixelTheme.microFont)
                                    .foregroundStyle(PixelTheme.textSecondary)
                                Text(txn.note.isEmpty ? txn.type.capitalized : txn.note)
                                    .font(PixelTheme.captionFont)
                                    .foregroundStyle(PixelTheme.textPrimary)
                                    .lineLimit(1)
                            }
                            Spacer()
                            Text(txn.amountFormatted)
                                .font(PixelTheme.captionFont)
                                .foregroundStyle(txn.isCredit ? PixelTheme.accentGreen : PixelTheme.textSecondary)
                            Text("bal: \(walletBalanceAfterFormatted(txn))")
                                .font(PixelTheme.microFont)
                                .foregroundStyle(PixelTheme.textSecondary)
                        }
                        Divider()
                    }
                }
            }
        }
    }

    private struct TransactionGroup {
        let date: String
        let transactions: [WalletTransaction]
    }

    private func groupedTransactions() -> [TransactionGroup] {
        let df = DateFormatter(); df.dateStyle = .long; df.timeStyle = .none
        let iso = ISO8601DateFormatter()
        iso.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        var groups: [String: [WalletTransaction]] = [:]
        var order: [String] = []
        for txn in transactions {
            let date = iso.date(from: txn.createdAt) ?? Date()
            let label = df.string(from: date)
            if groups[label] == nil { order.append(label) }
            groups[label, default: []].append(txn)
        }
        return order.map { TransactionGroup(date: $0, transactions: groups[$0] ?? []) }
    }

    private func txnTimeFormatted(_ iso: String) -> String {
        let fmt = ISO8601DateFormatter()
        fmt.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        guard let date = fmt.date(from: iso) else { return "" }
        let df = DateFormatter(); df.timeStyle = .short; df.dateStyle = .none
        return df.string(from: date)
    }

    private func walletBalanceAfterFormatted(_ txn: WalletTransaction) -> String {
        "$\(String(format: "%.2f", Double(abs(txn.amountCents)) / 100))"
    }

    // MARK: Budget Controls (moved from main view)

    private var budgetControlsSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Budget Settings")
                .font(PixelTheme.headlineFont)
                .foregroundStyle(PixelTheme.textPrimary)

            HStack(spacing: 8) {
                Slider(value: $budgetDollars, in: 10...1000, step: 10)
                Text("$\(Int(budgetDollars))")
                    .font(PixelTheme.captionFont)
                    .foregroundStyle(PixelTheme.accent)
                    .frame(width: 50)
            }

            HStack(spacing: 10) {
                Button(action: { Task { await saveBudget() } }) {
                    Text(isSavingBudget ? "Saving..." : "Modify Budget")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(PixelButtonStyle(color: PixelTheme.accentPurple))
                .disabled(isSavingBudget)

                Button(action: { Task { await chargeWallet() } }) {
                    Text(isChargingWallet ? "..." : "Charge Wallet")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(PixelButtonStyle(color: PixelTheme.accentGreen))
                .disabled(isChargingWallet)
            }

            if let actionMessage {
                Text(actionMessage)
                    .font(PixelTheme.microFont)
                    .foregroundStyle(PixelTheme.accentGreen)
            }
        }
    }

    // MARK: Actions

    private func loadTransactions() async {
        guard let companyId = appState.company?.id else { return }
        isLoadingTransactions = true
        do {
            let txns = try await APIClient.shared.fetchWalletTransactions(companyId: companyId)
            await MainActor.run { transactions = txns; isLoadingTransactions = false }
        } catch {
            await MainActor.run { isLoadingTransactions = false }
        }
    }

    private func saveBudget() async {
        guard let companyId = appState.company?.id else { return }
        isSavingBudget = true
        defer { Task { @MainActor in isSavingBudget = false } }
        do {
            try await APIClient.shared.setAdsBudget(companyId: companyId, dailyBudgetCents: Int(budgetDollars) * 100)
            await appState.refreshCompany()
            actionMessage = "Budget saved ✓"
            Task { try? await Task.sleep(nanoseconds: 2_000_000_000); await MainActor.run { actionMessage = nil } }
        } catch {}
    }

    private func chargeWallet() async {
        guard let companyId = appState.company?.id else { return }
        isChargingWallet = true
        defer { Task { @MainActor in isChargingWallet = false } }
        do {
            let result = try await APIClient.shared.chargeAdsWallet(companyId: companyId)
            await appState.refreshCompany()
            let added = result["added_cents"] ?? 0
            actionMessage = "+$\(added / 100) added to wallet ✓"
            await loadTransactions()
            Task { try? await Task.sleep(nanoseconds: 2_000_000_000); await MainActor.run { actionMessage = nil } }
        } catch {}
    }
}

extension Mission: Hashable {
    static func == (lhs: Mission, rhs: Mission) -> Bool { lhs.id == rhs.id }
    func hash(into hasher: inout Hasher) { hasher.combine(id) }
}
