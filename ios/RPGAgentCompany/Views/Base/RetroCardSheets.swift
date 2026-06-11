import SwiftUI

// MARK: - Shared retro helpers

private func mono(_ size: CGFloat) -> Font {
    .system(size: size, weight: .bold, design: .monospaced)
}

private var retroScanlines: some View {
    GeometryReader { _ in
        Canvas { ctx, size in
            var y: CGFloat = 0
            while y < size.height {
                ctx.stroke(Path { p in p.move(to: .init(x: 0, y: y)); p.addLine(to: .init(x: size.width, y: y)) },
                           with: .color(.white.opacity(0.04)), lineWidth: 1)
                y += 4
            }
        }
    }.ignoresSafeArea().allowsHitTesting(false)
}

private func sheetHeader(icon: String, title: String, subtitle: String, dismiss: DismissAction) -> some View {
    ZStack {
        HStack {
            Button(action: { dismiss() }) {
                Text("✕").font(mono(14)).foregroundStyle(.white.opacity(0.5))
            }
            Spacer()
        }
        VStack(spacing: 2) {
            Text("\(icon)  \(title)").font(mono(14)).foregroundStyle(.white)
            Text(subtitle).font(mono(8)).foregroundStyle(.white.opacity(0.3))
        }
    }
    .padding(.horizontal, 16).padding(.vertical, 12)
}

private func retroSection<C: View>(_ title: String, @ViewBuilder content: () -> C) -> some View {
    VStack(alignment: .leading, spacing: 0) {
        Text(title).font(mono(9)).foregroundStyle(.white.opacity(0.4))
            .padding(.horizontal, 12).padding(.top, 10).padding(.bottom, 6)
        Rectangle().frame(height: 1).foregroundStyle(.white.opacity(0.2))
        content()
    }
    .background(Color.black)
    .overlay(Rectangle().stroke(.white.opacity(0.35), lineWidth: 1))
}

private func retroEmpty(_ text: String) -> some View {
    VStack(spacing: 10) {
        Spacer()
        Text("◇").font(mono(36)).foregroundStyle(.white.opacity(0.1))
        Text(text).font(mono(10)).foregroundStyle(.white.opacity(0.35))
        Spacer()
    }
    .frame(maxWidth: .infinity)
}

// MARK: ─────────────────────────────────────────────────────────
// MARK: - RetroAdsSheet
// MARK: ─────────────────────────────────────────────────────────

struct RetroAdsSheet: View {
    @EnvironmentObject private var appState: AppState
    @Environment(\.dismiss) private var dismiss

    @State private var summary: AdsSummary?
    @State private var isLoading = false
    @State private var launchingStep: Int?

    // Budget editor
    @State private var showBudgetEditor = false
    @State private var budgetInput = ""
    @State private var isSavingBudget = false
    @State private var budgetError: String?

    // Per-campaign action loading: [campaignId: actionName]
    @State private var campaignLoading: [String: String] = [:]
    @State private var campaignError: String?

    private var companyId: String? { appState.company?.id }

    private var adsStep: QuestStep? {
        appState.questChain.first { ($0.agentType == "marketer") && !$0.isCompleted }
    }

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()
            retroScanlines

            VStack(spacing: 0) {
                sheetHeader(icon: "◈", title: "ADS", subtitle: "MÉTA ADS — CAMPAGNES & BUDGET", dismiss: dismiss)
                    .overlay(alignment: .bottom) { Rectangle().frame(height: 1).foregroundStyle(.white.opacity(0.2)) }

                ScrollView(showsIndicators: false) {
                    VStack(spacing: 12) {

                        if let step = adsStep, step.isAvailable {
                            questBanner(step: step)
                        } else if let step = adsStep, step.isRunning {
                            runningBanner(step: step)
                        }

                        if let s = summary {
                            balanceBudgetSection(s)
                            budgetEditorSection(s)
                            spendRollupSection(s)
                            campaignsSection(s)
                        } else if isLoading {
                            loadingView
                        } else {
                            retroEmpty("AUCUNE DONNÉE ADS").frame(height: 200)
                        }
                    }
                    .padding(.horizontal, 14).padding(.top, 14).padding(.bottom, 24)
                }
            }
        }
        .task { await loadData() }
    }

    // MARK: - Quest banners

    private func questBanner(step: QuestStep) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text("ÉTAPE \(step.stepNumber)  ·  DISPONIBLE")
                    .font(mono(9)).foregroundStyle(.white.opacity(0.5))
                Spacer()
            }
            Text(step.title.uppercased()).font(mono(12)).foregroundStyle(.white)
            Text(step.description).font(mono(10)).foregroundStyle(.white.opacity(0.6)).lineLimit(3)
            Button(action: { startStep(step) }) {
                HStack(spacing: 6) {
                    if launchingStep == step.stepNumber { ProgressView().tint(.black).scaleEffect(0.7) }
                    Text(launchingStep == step.stepNumber ? "LANCEMENT..." : "▶  LANCER LA MISSION")
                }
                .font(mono(11)).foregroundStyle(.black)
                .frame(maxWidth: .infinity).padding(.vertical, 11)
                .background(launchingStep == step.stepNumber ? Color.white.opacity(0.7) : Color.white)
            }
            .disabled(launchingStep != nil)
        }
        .padding(12).background(Color.black)
        .overlay(Rectangle().stroke(.white.opacity(0.7), lineWidth: 1))
    }

    private func runningBanner(step: QuestStep) -> some View {
        HStack(spacing: 10) {
            ProgressView().tint(.white).scaleEffect(0.8)
            VStack(alignment: .leading, spacing: 2) {
                Text("EN COURS — ÉTAPE \(step.stepNumber)").font(mono(9)).foregroundStyle(.white.opacity(0.5))
                Text(step.title.uppercased()).font(mono(11)).foregroundStyle(.white)
            }
            Spacer()
        }
        .padding(12).background(Color.black)
        .overlay(Rectangle().stroke(.white.opacity(0.5), lineWidth: 1))
    }

    // MARK: - Balance + budget stats

    private func balanceBudgetSection(_ s: AdsSummary) -> some View {
        HStack(spacing: 10) {
            statBox(label: "SOLDE", value: s.walletFormatted)
            statBox(label: "BUDGET/JOUR", value: String(format: "$%.2f", Double(s.dailyBudgetCents) / 100))
            statBox(label: "DÉPENSÉ TOTAL", value: String(format: "$%.2f", Double(s.totalSpendCents) / 100))
        }
    }

    private func statBox(label: String, value: String) -> some View {
        VStack(spacing: 4) {
            Text(value).font(mono(16)).foregroundStyle(.white)
            Text(label).font(mono(8)).foregroundStyle(.white.opacity(0.35))
        }
        .frame(maxWidth: .infinity).padding(.vertical, 14)
        .background(Color.black)
        .overlay(Rectangle().stroke(.white.opacity(0.3), lineWidth: 1))
    }

    // MARK: - Budget editor

    private func budgetEditorSection(_ s: AdsSummary) -> some View {
        retroSection("PARAMÈTRES BUDGET") {
            VStack(spacing: 0) {
                // Current budget row + edit toggle
                HStack {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("BUDGET QUOTIDIEN").font(mono(10)).foregroundStyle(.white)
                        Text(s.dailyBudgetCents > 0
                             ? String(format: "$%.2f / jour", Double(s.dailyBudgetCents) / 100)
                             : "NON DÉFINI — requis pour lancer les ads")
                            .font(mono(9))
                            .foregroundStyle(s.dailyBudgetCents > 0 ? .white.opacity(0.5) : .white.opacity(0.3))
                    }
                    Spacer()
                    Button(action: {
                        budgetInput = s.dailyBudgetCents > 0
                            ? String(format: "%.0f", Double(s.dailyBudgetCents) / 100)
                            : ""
                        budgetError = nil
                        withAnimation { showBudgetEditor.toggle() }
                    }) {
                        Text(showBudgetEditor ? "ANNULER" : "MODIFIER")
                            .font(mono(9)).foregroundStyle(.white)
                            .padding(.horizontal, 8).padding(.vertical, 5)
                            .overlay(Rectangle().stroke(.white.opacity(0.4), lineWidth: 1))
                    }
                }
                .padding(12)

                if showBudgetEditor {
                    Rectangle().frame(height: 1).foregroundStyle(.white.opacity(0.1))
                    VStack(spacing: 8) {
                        HStack(spacing: 8) {
                            Text("$")
                                .font(mono(14)).foregroundStyle(.white)
                            TextField("0", text: $budgetInput)
                                .font(.system(size: 14, weight: .bold, design: .monospaced))
                                .foregroundStyle(.white)
                                .keyboardType(.numberPad)
                                .frame(maxWidth: .infinity)
                            Text("/ JOUR")
                                .font(mono(9)).foregroundStyle(.white.opacity(0.4))
                        }
                        .padding(10)
                        .overlay(Rectangle().stroke(.white.opacity(0.5), lineWidth: 1))

                        if let err = budgetError {
                            Text(err).font(mono(9)).foregroundStyle(.white.opacity(0.5))
                        }

                        Button(action: { Task { await saveBudget() } }) {
                            HStack(spacing: 6) {
                                if isSavingBudget { ProgressView().tint(.black).scaleEffect(0.7) }
                                Text(isSavingBudget ? "ENREGISTREMENT..." : "▶  CONFIRMER LE BUDGET")
                            }
                            .font(mono(11)).foregroundStyle(.black)
                            .frame(maxWidth: .infinity).padding(.vertical, 11)
                            .background(isSavingBudget ? Color.white.opacity(0.7) : Color.white)
                        }
                        .disabled(isSavingBudget || budgetInput.isEmpty)
                    }
                    .padding(12)
                }
            }
        }
    }

    // MARK: - 7-day spend rollup

    private func spendRollupSection(_ s: AdsSummary) -> some View {
        retroSection("DÉPENSES 7 JOURS") {
            if s.spendRollup7d.allSatisfy({ $0 == 0 }) {
                Text("AUCUNE DÉPENSE SUR 7 JOURS")
                    .font(mono(10)).foregroundStyle(.white.opacity(0.3))
                    .padding(12)
            } else {
                HStack(alignment: .bottom, spacing: 4) {
                    let maxVal = Double(s.spendRollup7d.max() ?? 1)
                    ForEach(Array(s.spendRollup7d.enumerated()), id: \.offset) { _, val in
                        let frac = maxVal > 0 ? CGFloat(val) / CGFloat(maxVal) : 0
                        VStack(spacing: 2) {
                            Rectangle()
                                .foregroundStyle(.white.opacity(0.7))
                                .frame(height: max(4, 48 * frac))
                            Text(String(format: "$%.0f", Double(val) / 100))
                                .font(mono(7)).foregroundStyle(.white.opacity(0.35))
                        }
                        .frame(maxWidth: .infinity)
                    }
                }
                .padding(.horizontal, 12).padding(.vertical, 10)
            }
        }
    }

    // MARK: - Campaigns list

    private func campaignsSection(_ s: AdsSummary) -> some View {
        retroSection("VOS ADS  (\(s.campaigns.count))") {
            VStack(spacing: 0) {
                if s.campaigns.isEmpty {
                    Text("AUCUNE CAMPAGNE CRÉÉE")
                        .font(mono(10)).foregroundStyle(.white.opacity(0.3))
                        .padding(12)
                } else {
                    if let err = campaignError {
                        Text(err).font(mono(9)).foregroundStyle(.white.opacity(0.5))
                            .padding(.horizontal, 12).padding(.vertical, 6)
                        Rectangle().frame(height: 1).foregroundStyle(.white.opacity(0.1))
                    }
                    ForEach(Array(s.campaigns.enumerated()), id: \.element.id) { idx, camp in
                        if idx > 0 { Rectangle().frame(height: 1).foregroundStyle(.white.opacity(0.1)) }
                        campaignRow(camp)
                    }
                }
            }
        }
    }

    private func campaignRow(_ c: AdCampaign) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            // Name + status
            HStack(spacing: 8) {
                VStack(alignment: .leading, spacing: 2) {
                    Text(c.name).font(mono(11)).foregroundStyle(.white).lineLimit(1)
                    Text(c.status.uppercased())
                        .font(mono(8))
                        .foregroundStyle(c.status == "active" ? .white : .white.opacity(0.4))
                        .padding(.horizontal, 5).padding(.vertical, 2)
                        .overlay(Rectangle().stroke(c.status == "active" ? Color.white.opacity(0.8) : Color.white.opacity(0.2), lineWidth: 1))
                }
                Spacer()
                // Pause / Resume
                if let action = campaignLoading[c.id] {
                    HStack(spacing: 4) {
                        ProgressView().tint(.white).scaleEffect(0.6)
                        Text(action.uppercased()).font(mono(8)).foregroundStyle(.white.opacity(0.4))
                    }
                } else {
                    Button(action: { Task { await toggleCampaign(c) } }) {
                        Text(c.status == "active" ? "⏸  PAUSE" : "▶  RESUME")
                            .font(mono(9)).foregroundStyle(c.status == "active" ? .white : .white.opacity(0.7))
                            .padding(.horizontal, 8).padding(.vertical, 5)
                            .overlay(Rectangle().stroke(.white.opacity(0.4), lineWidth: 1))
                    }
                }
            }

            // Metrics
            HStack(spacing: 0) {
                metricCell("DÉPENSÉ", c.spendFormatted)
                metricCell("IMPR.", "\(c.impressions)")
                metricCell("CTR", c.ctrFormatted)
                metricCell("CPC", c.cpcFormatted)
            }

            // Scale + Split actions (only for active campaigns with some spend)
            if c.status == "active" && c.spendCents > 0 {
                HStack(spacing: 8) {
                    campaignActionBtn("⬆  SCALE +20%", loading: campaignLoading[c.id] == "scale") {
                        Task { await scaleCampaign(c) }
                    }
                    campaignActionBtn("🏆  APPLIQUER WINNER", loading: campaignLoading[c.id] == "split") {
                        Task { await splitCampaign(c) }
                    }
                }
            }
        }
        .padding(.horizontal, 12).padding(.vertical, 10)
    }

    private func campaignActionBtn(_ label: String, loading: Bool, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack(spacing: 4) {
                if loading { ProgressView().tint(.white).scaleEffect(0.55) }
                Text(label).font(mono(9)).foregroundStyle(.white.opacity(0.8))
            }
            .frame(maxWidth: .infinity).padding(.vertical, 7)
            .overlay(Rectangle().stroke(.white.opacity(0.3), lineWidth: 1))
        }
        .disabled(loading || !campaignLoading.isEmpty)
    }

    private func metricCell(_ label: String, _ value: String) -> some View {
        VStack(spacing: 2) {
            Text(value).font(mono(11)).foregroundStyle(.white)
            Text(label).font(mono(7)).foregroundStyle(.white.opacity(0.35))
        }
        .frame(maxWidth: .infinity)
    }

    private var loadingView: some View {
        VStack(spacing: 10) {
            ProgressView().tint(.white)
            Text("CHARGEMENT...").font(mono(10)).foregroundStyle(.white.opacity(0.4))
        }
        .frame(maxWidth: .infinity).padding(.vertical, 40)
    }

    // MARK: - Data & actions

    private func loadData() async {
        guard let id = companyId else { return }
        isLoading = true
        defer { isLoading = false }
        summary = try? await APIClient.shared.fetchAdsSummary(companyId: id)
    }

    private func startStep(_ step: QuestStep) {
        guard launchingStep == nil else { return }
        launchingStep = step.stepNumber
        Task {
            await appState.startQuestStep(stepNumber: step.stepNumber)
            launchingStep = nil
            await loadData()
        }
    }

    private func saveBudget() async {
        guard let id = companyId, let dollars = Double(budgetInput), dollars > 0 else {
            budgetError = "Montant invalide"
            return
        }
        isSavingBudget = true
        budgetError = nil
        defer { isSavingBudget = false }
        do {
            try await APIClient.shared.setAdsBudget(companyId: id, dailyBudgetCents: Int(dollars * 100))
            withAnimation { showBudgetEditor = false }
            await loadData()
        } catch {
            budgetError = error.localizedDescription
        }
    }

    private func toggleCampaign(_ c: AdCampaign) async {
        guard let id = companyId else { return }
        campaignLoading[c.id] = c.status == "active" ? "pause" : "resume"
        campaignError = nil
        defer { campaignLoading.removeValue(forKey: c.id) }
        do {
            if c.status == "active" {
                try await APIClient.shared.pauseAdsCampaign(companyId: id, campaignId: c.id)
            } else {
                try await APIClient.shared.resumeAdsCampaign(companyId: id, campaignId: c.id)
            }
            await loadData()
        } catch {
            campaignError = error.localizedDescription
        }
    }

    private func scaleCampaign(_ c: AdCampaign) async {
        guard let id = companyId else { return }
        campaignLoading[c.id] = "scale"
        campaignError = nil
        defer { campaignLoading.removeValue(forKey: c.id) }
        do {
            try await APIClient.shared.applyScaleCampaign(companyId: id, campaignId: c.id)
            await loadData()
        } catch {
            campaignError = error.localizedDescription
        }
    }

    private func splitCampaign(_ c: AdCampaign) async {
        guard let id = companyId else { return }
        campaignLoading[c.id] = "split"
        campaignError = nil
        defer { campaignLoading.removeValue(forKey: c.id) }
        do {
            try await APIClient.shared.applySplitWinner(companyId: id, campaignId: c.id)
            await loadData()
        } catch {
            campaignError = error.localizedDescription
        }
    }
}

// MARK: ─────────────────────────────────────────────────────────
// MARK: - RetroWebsiteSheet
// MARK: ─────────────────────────────────────────────────────────

struct RetroWebsiteSheet: View {
    @EnvironmentObject private var appState: AppState
    @Environment(\.dismiss) private var dismiss

    @State private var launchingStep: Int?
    @State private var websiteLogs: [MissionLogEntry] = []
    @State private var logPollingTask: Task<Void, Never>?
    @State private var siteStatusPollingTask: Task<Void, Never>?

    private var company: Company? { appState.company }
    private var siteUrl: String? { company?.siteUrl }
    private var slug: String? { company?.slug }
    private var displayUrl: String {
        if let url = siteUrl, !url.isEmpty { return url }
        return "—"
    }
    private var websiteStep: QuestStep? {
        appState.questChain.first { $0.agentType == "builder" && !$0.isCompleted }
    }

    private var siteStatus: (label: String, color: Color) {
        switch company?.siteStatus {
        case "live":       return ("LIVE ◉", Color.green)
        case "publishing": return ("EN COURS ▶", Color.yellow)
        case "failed":     return ("ERREUR ✕", Color.red)
        default:
            // Fallback: infer from running quest step
            if let step = websiteStep, step.isRunning {
                return ("EN COURS ▶", Color.yellow)
            }
            return ("PAS ENCORE CRÉÉ ○", Color.white.opacity(0.4))
        }
    }

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()
            retroScanlines

            VStack(spacing: 0) {
                sheetHeader(icon: "◈", title: "WEBSITE", subtitle: "SITE WEB — DOMAINE & DÉPLOIEMENT", dismiss: dismiss)
                    .overlay(alignment: .bottom) { Rectangle().frame(height: 1).foregroundStyle(.white.opacity(0.2)) }

                // Status badge bar
                HStack {
                    Spacer()
                    Text(siteStatus.label)
                        .font(mono(9))
                        .foregroundStyle(siteStatus.color)
                        .padding(.horizontal, 10).padding(.vertical, 5)
                        .overlay(Rectangle().stroke(siteStatus.color.opacity(0.4), lineWidth: 1))
                }
                .padding(.horizontal, 14).padding(.vertical, 8)
                .overlay(alignment: .bottom) { Rectangle().frame(height: 1).foregroundStyle(.white.opacity(0.1)) }

                ScrollView(showsIndicators: false) {
                    VStack(spacing: 12) {

                        // Quest step banner
                        if let step = websiteStep, step.isActionable {
                            websiteQuestBanner(step)
                        } else if let step = websiteStep, step.isRunning {
                            websiteRunningBanner(step)
                        }

                        // Polsia URL section
                        urlSection

                        // Product image section
                        productImageSection

                        // Custom domains (placeholder)
                        customDomainsSection
                    }
                    .padding(.horizontal, 14).padding(.top, 14).padding(.bottom, 24)
                }
            }
        }
    }

    // MARK: - Quest banners

    private func websiteQuestBanner(_ step: QuestStep) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("ÉTAPE \(step.stepNumber)  ·  DISPONIBLE")
                .font(mono(9)).foregroundStyle(.white.opacity(0.5))
            Text(step.title.uppercased()).font(mono(12)).foregroundStyle(.white)
            Text(step.description).font(mono(10)).foregroundStyle(.white.opacity(0.6)).lineLimit(3)
            Button(action: { startWebsiteStep(step) }) {
                HStack(spacing: 6) {
                    if launchingStep == step.stepNumber { ProgressView().tint(.black).scaleEffect(0.7) }
                    Text(launchingStep == step.stepNumber ? "LANCEMENT..." : "▶  LANCER LA MISSION")
                }
                .font(mono(11)).foregroundStyle(.black)
                .frame(maxWidth: .infinity).padding(.vertical, 11)
                .background(Color.white)
            }
            .disabled(launchingStep != nil)
        }
        .padding(12)
        .background(Color.black)
        .overlay(Rectangle().stroke(.white.opacity(0.7), lineWidth: 1))
    }

    private func websiteRunningBanner(_ step: QuestStep) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 8) {
                ProgressView().tint(.white).scaleEffect(0.75)
                Text("EN COURS — GÉNÉRATION SITE WEB").font(mono(9)).foregroundStyle(.white.opacity(0.5))
                Spacer()
            }

            VStack(alignment: .leading, spacing: 6) {
                ForEach(websiteGenerationSteps, id: \.key) { stage in
                    let done = websiteLogs.contains { stage.matchSteps.contains($0.step) }
                    let current = !done && websiteLogs.last.map { stage.matchSteps.contains($0.step) } ?? false
                    HStack(spacing: 8) {
                        if done {
                            Text("✓").font(mono(9)).foregroundStyle(.white.opacity(0.7)).frame(width: 12)
                        } else if current {
                            ProgressView().tint(.white).scaleEffect(0.5).frame(width: 12)
                        } else {
                            Text("○").font(mono(9)).foregroundStyle(.white.opacity(0.2)).frame(width: 12)
                        }
                        Text(stage.label)
                            .font(mono(9))
                            .foregroundStyle(done ? .white.opacity(0.7) : current ? .white : .white.opacity(0.25))
                    }
                }
            }

            if let lastLog = websiteLogs.last {
                Text(lastLog.message.prefix(60))
                    .font(mono(8))
                    .foregroundStyle(.white.opacity(0.35))
                    .lineLimit(1)
            }
        }
        .padding(12)
        .background(Color.black)
        .overlay(Rectangle().stroke(.white.opacity(0.5), lineWidth: 1))
        .onAppear { startLogPolling(step) }
        .onDisappear {
            logPollingTask?.cancel()
            siteStatusPollingTask?.cancel()
        }
    }

    private struct WebsiteStage {
        let key: String
        let label: String
        let matchSteps: [String]
    }

    private var websiteGenerationSteps: [WebsiteStage] { [
        WebsiteStage(key: "brief",    label: "DIRECTION CRÉATIVE",      matchSteps: ["website_brief", "website_brief_ready"]),
        WebsiteStage(key: "context",  label: "CONTEXTE & MARCHÉ",       matchSteps: ["context_loaded", "memory_loaded"]),
        WebsiteStage(key: "image",    label: "IMAGE PRODUIT",           matchSteps: ["product_image", "product_image_generating", "product_image_ready", "product_image_missing", "product_image_failed"]),
        WebsiteStage(key: "build",    label: "CONSTRUCTION DU SITE",    matchSteps: ["agent_call", "deliverable_ready"]),
        WebsiteStage(key: "quality",  label: "VÉRIFICATION QUALITÉ",    matchSteps: ["quality_check"]),
        WebsiteStage(key: "deploy",   label: "DÉPLOIEMENT",             matchSteps: ["site_deployed"]),
    ] }

    private func startLogPolling(_ step: QuestStep) {
        guard let missionId = step.missionId else { return }
        logPollingTask?.cancel()
        logPollingTask = Task {
            while !Task.isCancelled {
                if let logs = try? await APIClient.shared.fetchMissionLogs(missionId: missionId) {
                    await MainActor.run { websiteLogs = logs }
                }
                try? await Task.sleep(nanoseconds: 3_000_000_000)
            }
        }
        // Also poll site_status so the UI refreshes automatically when the site goes live
        startSiteStatusPolling()
    }

    private func startSiteStatusPolling() {
        guard let slug = company?.slug else { return }
        siteStatusPollingTask?.cancel()
        siteStatusPollingTask = Task {
            while !Task.isCancelled {
                try? await Task.sleep(nanoseconds: 5_000_000_000)
                guard !Task.isCancelled else { break }
                if let status = try? await APIClient.shared.fetchSiteStatus(slug: slug) {
                    if status.live {
                        await appState.refreshCompany()
                        break
                    }
                }
            }
        }
    }

    // MARK: - URL section (shared gateway)

    private var urlSection: some View {
        let version = company?.siteVersion
        let sectionTitle = "SITE WEB" + (version != nil ? " — v\(version!)" : "")
        return retroSection(sectionTitle) {
            VStack(alignment: .leading, spacing: 10) {
                if siteUrl != nil {
                    HStack(spacing: 10) {
                        Text(displayUrl)
                            .font(mono(11)).foregroundStyle(.white.opacity(0.8))
                            .lineLimit(1)
                            .frame(maxWidth: .infinity, alignment: .leading)
                        if let url = URL(string: displayUrl.hasPrefix("http") ? displayUrl : "https://\(displayUrl)") {
                            Button(action: { UIApplication.shared.open(url) }) {
                                Text("OUVRIR")
                                    .font(mono(9)).foregroundStyle(.black)
                                    .padding(.horizontal, 10).padding(.vertical, 6)
                                    .background(Color.white)
                            }
                        }
                    }
                    Button(action: {
                        UIPasteboard.general.string = displayUrl
                    }) {
                        Text("COPIER L'URL")
                            .font(mono(10)).foregroundStyle(.white)
                            .frame(maxWidth: .infinity).padding(.vertical, 9)
                            .overlay(Rectangle().stroke(.white.opacity(0.4), lineWidth: 1))
                    }
                } else {
                    Text("Site pas encore créé.")
                        .font(mono(10)).foregroundStyle(.white.opacity(0.4))
                    Text("Lance la mission 'Créer le site' depuis l'onglet Quêtes.")
                        .font(mono(9)).foregroundStyle(.white.opacity(0.25))
                }
            }
            .padding(12)
        }
    }

    // MARK: - Product image section

    @State private var showProductImageFullscreen = false

    private var productImageSection: some View {
        let imageUrl = company?.productImageUrl
        let websiteIsRunning = websiteStep?.isRunning ?? false

        return retroSection("IMAGE PRODUIT") {
            VStack(spacing: 0) {
                if websiteIsRunning && imageUrl == nil {
                    // Generating state
                    HStack(spacing: 8) {
                        ProgressView().tint(.white).scaleEffect(0.65)
                        VStack(alignment: .leading, spacing: 2) {
                            Text("GÉNÉRATION EN COURS...")
                                .font(mono(10)).foregroundStyle(.white.opacity(0.6))
                            Text("L'image produit est en train d'être créée.")
                                .font(mono(8)).foregroundStyle(.white.opacity(0.3))
                        }
                        Spacer()
                    }
                    .padding(12)
                } else if let urlStr = imageUrl, let url = URL(string: urlStr) {
                    // Generated — show thumbnail
                    Button(action: { showProductImageFullscreen = true }) {
                        HStack(spacing: 12) {
                            AsyncImage(url: url) { phase in
                                switch phase {
                                case .success(let img):
                                    img.resizable().scaledToFill()
                                        .frame(width: 56, height: 56)
                                        .clipped()
                                        .overlay(Rectangle().stroke(.white.opacity(0.2), lineWidth: 1))
                                case .failure:
                                    Rectangle().foregroundStyle(.white.opacity(0.05))
                                        .frame(width: 56, height: 56)
                                        .overlay(Text("?").font(mono(16)).foregroundStyle(.white.opacity(0.3)))
                                default:
                                    Rectangle().foregroundStyle(.white.opacity(0.05))
                                        .frame(width: 56, height: 56)
                                        .overlay(ProgressView().tint(.white).scaleEffect(0.6))
                                }
                            }
                            VStack(alignment: .leading, spacing: 2) {
                                Text("IMAGE GÉNÉRÉE ◉")
                                    .font(mono(10)).foregroundStyle(.white)
                                Text("Tap pour voir en plein écran")
                                    .font(mono(8)).foregroundStyle(.white.opacity(0.35))
                            }
                            Spacer()
                            Text("▸").font(mono(12)).foregroundStyle(.white.opacity(0.4))
                        }
                        .padding(12)
                    }
                    .buttonStyle(.plain)
                    .sheet(isPresented: $showProductImageFullscreen) {
                        productImageFullscreen(url: url)
                    }
                } else {
                    // Not generated
                    HStack {
                        VStack(alignment: .leading, spacing: 2) {
                            Text("IMAGE NON GÉNÉRÉE ○")
                                .font(mono(10)).foregroundStyle(.white.opacity(0.4))
                            Text("Le site a quand même été créé. Génère l'image depuis le Sage.")
                                .font(mono(8)).foregroundStyle(.white.opacity(0.25))
                        }
                        Spacer()
                    }
                    .padding(12)
                }
            }
        }
    }

    private func productImageFullscreen(url: URL) -> some View {
        ZStack {
            Color.black.ignoresSafeArea()
            VStack(spacing: 0) {
                HStack {
                    Button(action: { showProductImageFullscreen = false }) {
                        Text("FERMER").font(mono(10)).foregroundStyle(.white)
                            .padding(.horizontal, 14).padding(.vertical, 8)
                            .overlay(Rectangle().stroke(.white.opacity(0.4), lineWidth: 1))
                    }
                    Spacer()
                    ShareLink(item: url) {
                        Text("PARTAGER").font(mono(10)).foregroundStyle(.white)
                            .padding(.horizontal, 14).padding(.vertical, 8)
                            .overlay(Rectangle().stroke(.white.opacity(0.4), lineWidth: 1))
                    }
                }
                .padding(14)
                Spacer()
                AsyncImage(url: url) { phase in
                    switch phase {
                    case .success(let img):
                        img.resizable().scaledToFit()
                            .padding(14)
                    default:
                        ProgressView().tint(.white)
                    }
                }
                Spacer()
                Text("IMAGE PRODUIT").font(mono(8)).foregroundStyle(.white.opacity(0.25)).padding(.bottom, 24)
            }
        }
    }

    // MARK: - Custom domains (Polsia-style, placeholder)

    private var customDomainsSection: some View {
        retroSection("DOMAINES PERSONNALISÉS") {
            VStack(spacing: 0) {
                HStack {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("AUCUN DOMAINE CONNECTÉ")
                            .font(mono(10)).foregroundStyle(.white.opacity(0.4))
                        Text("Connecte un domaine que tu possèdes.")
                            .font(mono(9)).foregroundStyle(.white.opacity(0.25))
                    }
                    Spacer()
                }
                .padding(12)

                Rectangle().frame(height: 1).foregroundStyle(.white.opacity(0.1))

                HStack {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("CONNECTER UN DOMAINE EXISTANT")
                            .font(mono(10)).foregroundStyle(.white)
                        Text("Utilise un domaine que tu as déjà acheté.")
                            .font(mono(9)).foregroundStyle(.white.opacity(0.35))
                    }
                    Spacer()
                    Button(action: {}) {
                        Text("CONNECTER")
                            .font(mono(9)).foregroundStyle(.white)
                            .padding(.horizontal, 10).padding(.vertical, 6)
                            .overlay(Rectangle().stroke(.white.opacity(0.5), lineWidth: 1))
                    }
                    .disabled(true)
                }
                .padding(12)
            }
        }
    }

    private func startWebsiteStep(_ step: QuestStep) {
        guard launchingStep == nil else { return }
        launchingStep = step.stepNumber
        Task {
            await appState.startQuestStep(stepNumber: step.stepNumber)
            launchingStep = nil
        }
    }
}

// MARK: ─────────────────────────────────────────────────────────
// MARK: - RetroDocsSheet
// MARK: ─────────────────────────────────────────────────────────

struct RetroDocsSheet: View {
    @EnvironmentObject private var appState: AppState
    @Environment(\.dismiss) private var dismiss

    let filterAgent: String?   // nil = show all; "researcher" = filter to research docs

    @State private var expandedDocId: String?
    @State private var showProductImage = false

    private var allDocs: [Mission] {
        // Landing page HTML is accessible via the Website sheet — don't pollute DOCS
        let base = appState.missions.filter {
            $0.isCompleted && $0.deliverable != nil && $0.missionType != "landing_page"
        }
        if let agent = filterAgent {
            let related = Set(VillageMap.polisiaAgentTypes(for: agent))
            return base.filter { related.contains($0.agentType) }
                       .sorted { ($0.createdAt ?? "") > ($1.createdAt ?? "") }
        }
        return base.sorted { ($0.createdAt ?? "") > ($1.createdAt ?? "") }
    }

    private var productImageUrl: URL? {
        guard filterAgent == nil, let str = appState.company?.productImageUrl, !str.isEmpty else { return nil }
        return URL(string: str)
    }

    private var title: String { filterAgent == nil ? "DOCS" : "RESEARCH" }
    private var subtitle: String { filterAgent == nil ? "TOUS LES DOCUMENTS GÉNÉRÉS" : "ÉTUDE DE MARCHÉ & STRATÉGIE" }

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()
            retroScanlines

            VStack(spacing: 0) {
                sheetHeader(icon: "◨", title: title, subtitle: subtitle, dismiss: dismiss)
                    .overlay(alignment: .bottom) { Rectangle().frame(height: 1).foregroundStyle(.white.opacity(0.2)) }

                if allDocs.isEmpty {
                    retroEmpty("AUCUN DOCUMENT GÉNÉRÉ\nLANCE TES PREMIÈRES MISSIONS")
                } else {
                    ScrollView(showsIndicators: false) {
                        VStack(spacing: 0) {
                            // Progress header
                            let progress = appState.questChainProgress
                            VStack(alignment: .leading, spacing: 8) {
                                HStack {
                                    Text("DOSSIER ENTREPRISE")
                                        .font(mono(11)).foregroundStyle(.white)
                                    Spacer()
                                    let totalCount = allDocs.count + (productImageUrl != nil ? 1 : 0)
                                    Text("\(totalCount) doc\(totalCount != 1 ? "s" : "")")
                                        .font(mono(9)).foregroundStyle(.white.opacity(0.4))
                                }
                                GeometryReader { geo in
                                    ZStack(alignment: .leading) {
                                        Rectangle().foregroundStyle(.white.opacity(0.1))
                                        Rectangle()
                                            .frame(width: progress.total > 0
                                                   ? geo.size.width * CGFloat(progress.completed) / CGFloat(progress.total) : 0)
                                            .foregroundStyle(.white.opacity(0.65))
                                    }
                                    .overlay(Rectangle().stroke(.white.opacity(0.3), lineWidth: 0.5))
                                }
                                .frame(height: 7)
                                Text("\(progress.completed)/\(progress.total) étapes complètes")
                                    .font(mono(8)).foregroundStyle(.white.opacity(0.35))
                            }
                            .padding(14)
                            .background(Color.black)
                            .overlay(Rectangle().stroke(.white.opacity(0.3), lineWidth: 1))
                            .padding(.horizontal, 14).padding(.top, 14).padding(.bottom, 10)

                            LazyVStack(spacing: 0) {
                                // Product image card (pinned at top when available)
                                if let url = productImageUrl {
                                    productImageDocRow(url: url)
                                    Rectangle().frame(height: 1).foregroundStyle(.white.opacity(0.1))
                                }
                                ForEach(allDocs) { mission in
                                    documentRow(mission)
                                    Rectangle().frame(height: 1).foregroundStyle(.white.opacity(0.1))
                                }
                            }
                            .padding(.horizontal, 14)
                            .background(Color.black)
                            .overlay(Rectangle().stroke(.white.opacity(0.25), lineWidth: 1).padding(.horizontal, 14))
                            .padding(.bottom, 24)
                        }
                    }
                }
            }
        }
    }

    private func productImageDocRow(url: URL) -> some View {
        Button(action: { showProductImage = true }) {
            HStack(spacing: 10) {
                AsyncImage(url: url) { phase in
                    switch phase {
                    case .success(let img):
                        img.resizable().scaledToFill()
                            .frame(width: 40, height: 40).clipped()
                            .overlay(Rectangle().stroke(.white.opacity(0.2), lineWidth: 1))
                    default:
                        Rectangle().foregroundStyle(.white.opacity(0.05))
                            .frame(width: 40, height: 40)
                            .overlay(ProgressView().tint(.white).scaleEffect(0.5))
                    }
                }
                VStack(alignment: .leading, spacing: 2) {
                    Text("IMAGE PRODUIT")
                        .font(mono(11)).foregroundStyle(.white)
                    HStack(spacing: 6) {
                        Text("BUILDER").font(mono(8)).foregroundStyle(.white.opacity(0.4))
                        Text("IMAGE").font(mono(8)).foregroundStyle(.white.opacity(0.4))
                    }
                }
                Spacer()
                Text("▸").font(mono(12)).foregroundStyle(.white.opacity(0.4))
            }
            .padding(.horizontal, 12).padding(.vertical, 10)
        }
        .buttonStyle(.plain)
        .sheet(isPresented: $showProductImage) {
            ZStack {
                Color.black.ignoresSafeArea()
                VStack(spacing: 0) {
                    HStack {
                        Button(action: { showProductImage = false }) {
                            Text("FERMER").font(mono(10)).foregroundStyle(.white)
                                .padding(.horizontal, 14).padding(.vertical, 8)
                                .overlay(Rectangle().stroke(.white.opacity(0.4), lineWidth: 1))
                        }
                        Spacer()
                        ShareLink(item: url) {
                            Text("PARTAGER").font(mono(10)).foregroundStyle(.white)
                                .padding(.horizontal, 14).padding(.vertical, 8)
                                .overlay(Rectangle().stroke(.white.opacity(0.4), lineWidth: 1))
                        }
                    }
                    .padding(14)
                    Spacer()
                    AsyncImage(url: url) { phase in
                        switch phase {
                        case .success(let img): img.resizable().scaledToFit().padding(14)
                        default: ProgressView().tint(.white)
                        }
                    }
                    Spacer()
                    Text("IMAGE PRODUIT GÉNÉRÉE PAR L'IA")
                        .font(mono(8)).foregroundStyle(.white.opacity(0.25)).padding(.bottom, 24)
                }
            }
        }
    }

    private func documentRow(_ mission: Mission) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            Button(action: {
                withAnimation(.easeOut(duration: 0.2)) {
                    expandedDocId = expandedDocId == mission.id ? nil : mission.id
                }
            }) {
                HStack(spacing: 10) {
                    Text(docIcon(mission.deliverableFormat))
                        .font(mono(14)).foregroundStyle(.white.opacity(0.6))
                    VStack(alignment: .leading, spacing: 2) {
                        Text(mission.missionType.replacingOccurrences(of: "_", with: " ").uppercased())
                            .font(mono(11)).foregroundStyle(.white)
                        HStack(spacing: 6) {
                            Text(agentCode(mission.agentType)).font(mono(8)).foregroundStyle(.white.opacity(0.4))
                            Text((mission.deliverableFormat ?? "TXT").uppercased())
                                .font(mono(8)).foregroundStyle(.white.opacity(0.4))
                        }
                    }
                    Spacer()
                    Text(expandedDocId == mission.id ? "▼" : "▸")
                        .font(mono(12)).foregroundStyle(.white.opacity(0.4))
                }
                .padding(.horizontal, 12).padding(.vertical, 10)
            }
            .buttonStyle(.plain)

            if expandedDocId == mission.id {
                Rectangle().frame(height: 1).foregroundStyle(.white.opacity(0.15))
                DeliverableContentBlock(mission: mission)
                    .padding(.horizontal, 12).padding(.vertical, 10)
                Rectangle().frame(height: 1).foregroundStyle(.white.opacity(0.1))
                HStack(spacing: 10) {
                    Button(action: {
                        if let content = mission.deliverable {
                            UIPasteboard.general.string = content
                            AnalyticsTracker.track("deliverable_copied", properties: [
                                "mission_type": mission.missionType, "source": "docs_sheet"
                            ])
                        }
                    }) {
                        Text("COPIER")
                            .font(mono(10)).foregroundStyle(.white)
                            .frame(maxWidth: .infinity).padding(.vertical, 9)
                            .overlay(Rectangle().stroke(.white.opacity(0.4), lineWidth: 1))
                    }
                    ShareLink(item: mission.deliverable ?? "") {
                        Text("PARTAGER")
                            .font(mono(10)).foregroundStyle(.black)
                            .frame(maxWidth: .infinity).padding(.vertical, 9)
                            .background(Color.white)
                    }
                }
                .padding(.horizontal, 12).padding(.vertical, 10)
            }
        }
    }

    private func docIcon(_ format: String?) -> String {
        switch format {
        case "html", "url": return "◻"
        case "json": return "◧"
        case "pdf": return "◫"
        default: return "◨"
        }
    }

    private func agentCode(_ type: String) -> String {
        switch type {
        case "builder": return "BUILD"
        case "marketer": return "ADS"
        case "researcher": return "RSCH"
        case "orchestrator": return "QG"
        case "outreach": return "OUT"
        case "support": return "SUP"
        case "finance": return "FIN"
        case "content": return "CNT"
        default: return type.prefix(5).uppercased()
        }
    }
}

// MARK: ─────────────────────────────────────────────────────────
// MARK: - RetroBusinessSheet
// MARK: ─────────────────────────────────────────────────────────

struct RetroBusinessSheet: View {
    @EnvironmentObject private var appState: AppState
    @Environment(\.dismiss) private var dismiss

    @State private var isStripeLoading = false
    @State private var stripeError: String?
    @State private var launchingStep: Int?

    @State private var orders: OrdersResponse?
    @State private var invoices: [Invoice] = []
    @State private var isLoadingRevenue = false

    private var company: Company? { appState.company }
    private var stripeStatus: String { company?.stripeConnectStatus ?? "not_started" }
    private var stripeOk: Bool { stripeStatus == "ready" }

    private var businessStep: QuestStep? {
        appState.questChain.first { $0.agentType == "finance" && !$0.isCompleted }
    }

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()
            retroScanlines

            VStack(spacing: 0) {
                sheetHeader(icon: "◈", title: "BUSINESS", subtitle: "REVENUS — STRIPE — STATISTIQUES", dismiss: dismiss)
                    .overlay(alignment: .bottom) { Rectangle().frame(height: 1).foregroundStyle(.white.opacity(0.2)) }

                ScrollView(showsIndicators: false) {
                    VStack(spacing: 12) {

                        if let step = businessStep, step.isAvailable {
                            businessQuestBanner(step)
                        } else if let step = businessStep, step.isRunning {
                            businessRunningBanner(step)
                        }

                        businessOverviewSection
                        stripeSection

                        if stripeOk {
                            ordersSection
                            invoicesSection
                        }
                    }
                    .padding(.horizontal, 14).padding(.top, 14).padding(.bottom, 24)
                }
            }
        }
        .task { if stripeOk { await loadRevenue() } }
    }

    private func loadRevenue() async {
        guard let id = company?.id else { return }
        isLoadingRevenue = true
        defer { isLoadingRevenue = false }
        async let ordersTask = try? APIClient.shared.fetchOrders(companyId: id)
        async let invoicesTask = try? APIClient.shared.fetchInvoices(companyId: id)
        orders = await ordersTask
        let inv = await invoicesTask
        invoices = inv?.invoices ?? []
    }

    // MARK: - Quest banners

    private func businessQuestBanner(_ step: QuestStep) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("ÉTAPE \(step.stepNumber)  ·  DISPONIBLE")
                .font(mono(9)).foregroundStyle(.white.opacity(0.5))
            Text(step.title.uppercased()).font(mono(12)).foregroundStyle(.white)
            Text(step.description).font(mono(10)).foregroundStyle(.white.opacity(0.6)).lineLimit(3)
            Button(action: { startBusinessStep(step) }) {
                HStack(spacing: 6) {
                    if launchingStep == step.stepNumber { ProgressView().tint(.black).scaleEffect(0.7) }
                    Text(launchingStep == step.stepNumber ? "LANCEMENT..." : "▶  LANCER LA MISSION")
                }
                .font(mono(11)).foregroundStyle(.black)
                .frame(maxWidth: .infinity).padding(.vertical, 11)
                .background(Color.white)
            }
            .disabled(launchingStep != nil)
        }
        .padding(12)
        .background(Color.black)
        .overlay(Rectangle().stroke(.white.opacity(0.7), lineWidth: 1))
    }

    private func businessRunningBanner(_ step: QuestStep) -> some View {
        HStack(spacing: 10) {
            ProgressView().tint(.white).scaleEffect(0.8)
            VStack(alignment: .leading, spacing: 2) {
                Text("EN COURS — ÉTAPE \(step.stepNumber)").font(mono(9)).foregroundStyle(.white.opacity(0.5))
                Text(step.title.uppercased()).font(mono(11)).foregroundStyle(.white)
            }
            Spacer()
        }
        .padding(12)
        .background(Color.black)
        .overlay(Rectangle().stroke(.white.opacity(0.5), lineWidth: 1))
    }

    // MARK: - Business overview

    private var businessOverviewSection: some View {
        retroSection("VUE D'ENSEMBLE") {
            HStack(spacing: 0) {
                infoCell(label: "TYPE", value: company?.businessType.displayName.uppercased() ?? "—")
                divider
                infoCell(label: "VISITEURS", value: "—")
                divider
                infoCell(label: "REVENUS", value: orders?.totalRevenueDisplay ?? "$0")
            }
        }
    }

    private var stripeSection: some View {
        retroSection("STRIPE — PAIEMENTS") {
            VStack(spacing: 0) {
                HStack {
                    VStack(alignment: .leading, spacing: 3) {
                        Text("STRIPE CONNECT").font(mono(11)).foregroundStyle(.white)
                        Text(stripeStatusLabel.uppercased())
                            .font(mono(9))
                            .foregroundStyle(stripeOk ? .white : .white.opacity(0.4))
                            .padding(.horizontal, 5).padding(.vertical, 2)
                            .overlay(Rectangle().stroke(stripeOk ? Color.white.opacity(0.7) : Color.white.opacity(0.2), lineWidth: 1))
                    }
                    Spacer()
                    if stripeOk {
                        Text("✓  CONNECTÉ").font(mono(10)).foregroundStyle(.white)
                    }
                }
                .padding(12)

                if !stripeOk {
                    Rectangle().frame(height: 1).foregroundStyle(.white.opacity(0.15))
                    if let error = stripeError {
                        Text(error).font(mono(9)).foregroundStyle(.white.opacity(0.5))
                            .padding(.horizontal, 12).padding(.vertical, 6)
                        Rectangle().frame(height: 1).foregroundStyle(.white.opacity(0.1))
                    }
                    Button(action: { Task { await setupStripe() } }) {
                        HStack(spacing: 6) {
                            if isStripeLoading { ProgressView().tint(.black).scaleEffect(0.7) }
                            Text(isStripeLoading ? "CONNEXION..." : "▶  SETUP PAYMENTS")
                        }
                        .font(mono(11)).foregroundStyle(.black)
                        .frame(maxWidth: .infinity).padding(.vertical, 11)
                        .background(isStripeLoading ? Color.white.opacity(0.7) : Color.white)
                        .padding(12)
                    }
                    .disabled(isStripeLoading)
                }
            }
        }
    }


    private func infoCell(label: String, value: String) -> some View {
        VStack(spacing: 3) {
            Text(value).font(mono(14)).foregroundStyle(.white)
            Text(label).font(mono(7)).foregroundStyle(.white.opacity(0.35))
        }
        .frame(maxWidth: .infinity).padding(.vertical, 12)
    }

    private var divider: some View {
        Rectangle().frame(width: 1).foregroundStyle(.white.opacity(0.1)).padding(.vertical, 10)
    }

    private var stripeStatusLabel: String {
        switch stripeStatus {
        case "ready": return "Connecté"
        case "pending": return "En attente"
        case "not_started": return "Non configuré"
        default: return stripeStatus
        }
    }

    private func setupStripe() async {
        guard let companyId = company?.id else { return }
        isStripeLoading = true
        stripeError = nil
        defer { isStripeLoading = false }
        do {
            let urlString = try await APIClient.shared.startStripeOnboarding(companyId: companyId)
            guard let url = URL(string: urlString), !urlString.isEmpty else {
                stripeError = "Lien onboarding indisponible"
                return
            }
            await UIApplication.shared.open(url)
            await appState.refreshCompany()
        } catch let err as APIError {
            switch err {
            case .http(let code, _) where code == 500:
                stripeError = "Stripe non configuré sur ce serveur. Contactez l'admin."
            case .http(let code, let body):
                stripeError = "Erreur \(code): \(body)"
            default:
                stripeError = err.localizedDescription
            }
        } catch {
            stripeError = error.localizedDescription
        }
    }

    // MARK: - Orders section

    private var ordersSection: some View {
        retroSection("COMMANDES  (\(orders?.total ?? 0))") {
            VStack(spacing: 0) {
                if isLoadingRevenue {
                    HStack { ProgressView().tint(.white).scaleEffect(0.7); Spacer() }.padding(12)
                } else if let resp = orders, !resp.orders.isEmpty {
                    // Revenue total
                    HStack {
                        Text("TOTAL REVENUS")
                            .font(mono(9)).foregroundStyle(.white.opacity(0.4))
                        Spacer()
                        Text(resp.totalRevenueDisplay)
                            .font(mono(12)).foregroundStyle(.white)
                    }
                    .padding(.horizontal, 12).padding(.vertical, 8)
                    Rectangle().frame(height: 1).foregroundStyle(.white.opacity(0.1))
                    // Order rows (last 5)
                    ForEach(Array(resp.orders.prefix(5).enumerated()), id: \.element.id) { idx, order in
                        if idx > 0 { Rectangle().frame(height: 1).foregroundStyle(.white.opacity(0.08)) }
                        HStack(spacing: 8) {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(order.productName?.uppercased() ?? "COMMANDE")
                                    .font(mono(10)).foregroundStyle(.white).lineLimit(1)
                                if let email = order.customerEmail {
                                    Text(email).font(mono(8)).foregroundStyle(.white.opacity(0.3)).lineLimit(1)
                                }
                            }
                            Spacer()
                            Text(order.amountDisplay)
                                .font(mono(11)).foregroundStyle(.white)
                        }
                        .padding(.horizontal, 12).padding(.vertical, 8)
                    }
                    if resp.orders.count > 5 {
                        Text("+ \(resp.orders.count - 5) autres commandes")
                            .font(mono(9)).foregroundStyle(.white.opacity(0.3))
                            .padding(12)
                    }
                } else {
                    Text("AUCUNE COMMANDE REÇUE")
                        .font(mono(10)).foregroundStyle(.white.opacity(0.3))
                        .padding(12)
                }
            }
        }
    }

    // MARK: - Invoices section

    private var invoicesSection: some View {
        retroSection("FACTURES STRIPE  (\(invoices.count))") {
            VStack(spacing: 0) {
                if invoices.isEmpty && !isLoadingRevenue {
                    Text("AUCUNE FACTURE")
                        .font(mono(10)).foregroundStyle(.white.opacity(0.3))
                        .padding(12)
                } else {
                    ForEach(Array(invoices.prefix(5).enumerated()), id: \.element.id) { idx, inv in
                        if idx > 0 { Rectangle().frame(height: 1).foregroundStyle(.white.opacity(0.08)) }
                        HStack {
                            VStack(alignment: .leading, spacing: 2) {
                                Text((inv.number ?? "INV").uppercased())
                                    .font(mono(10)).foregroundStyle(.white)
                                Text(inv.status.uppercased())
                                    .font(mono(8))
                                    .foregroundStyle(inv.status == "paid" ? .white : .white.opacity(0.35))
                                    .padding(.horizontal, 4).padding(.vertical, 1)
                                    .overlay(Rectangle().stroke(.white.opacity(0.2), lineWidth: 1))
                            }
                            Spacer()
                            VStack(alignment: .trailing, spacing: 2) {
                                Text(inv.amountDisplay).font(mono(11)).foregroundStyle(.white)
                                if let urlStr = inv.hostedInvoiceUrl, let url = URL(string: urlStr) {
                                    Link("VOIR ▸", destination: url)
                                        .font(mono(8)).foregroundStyle(.white.opacity(0.4))
                                }
                            }
                        }
                        .padding(.horizontal, 12).padding(.vertical, 9)
                    }
                }
            }
        }
    }

    private func startBusinessStep(_ step: QuestStep) {
        guard launchingStep == nil else { return }
        launchingStep = step.stepNumber
        Task {
            await appState.startQuestStep(stepNumber: step.stepNumber)
            launchingStep = nil
        }
    }
}

// MARK: - Debug Menu

struct DebugMenuSheet: View {
    @EnvironmentObject private var appState: AppState
    @Environment(\.dismiss) private var dismiss
    @State private var isLocal = APIClient.shared.isUsingLocal
    @State private var resetDone = false
    @State private var creditsAdded = false
    @State private var addingCredits = false
    @State private var deleteResetting = false
    @State private var deleteResetDone = false
    @State private var showDeleteConfirm = false

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()
            retroScanlines
            ScrollView {
                VStack(spacing: 0) {
                    sheetHeader(icon: "⚙", title: "DEBUG", subtitle: "ENV · BACKEND · RESET", dismiss: dismiss)

                    // URL switcher
                    retroSection("BACKEND URL") {
                        VStack(spacing: 8) {
                            Text(APIClient.shared.baseURL)
                                .font(.system(size: 10, weight: .bold, design: .monospaced))
                                .foregroundStyle(.white.opacity(0.5))
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .padding(.bottom, 4)

                            HStack(spacing: 10) {
                                debugToggleBtn("🌐 PROD", active: !isLocal) {
                                    APIClient.shared.useProductionBackend()
                                    isLocal = false
                                }
                                debugToggleBtn("💻 LOCAL", active: isLocal) {
                                    APIClient.shared.useLocalBackend()
                                    isLocal = true
                                }
                            }

                            if isLocal {
                                Text("⚠ Lance d'abord ./backend/start.sh sur ton Mac")
                                    .font(.system(size: 10, weight: .bold, design: .monospaced))
                                    .foregroundStyle(.yellow.opacity(0.7))
                                    .frame(maxWidth: .infinity, alignment: .leading)
                                    .padding(.top, 4)
                            }
                        }
                    }

                    retroSection("ACTIONS") {
                        VStack(spacing: 8) {
                            // Add trial credits
                            Button(action: {
                                guard let id = appState.company?.id else { return }
                                addingCredits = true
                                Task {
                                    try? await APIClient.shared.addTrialCredits(companyId: id)
                                    await appState.fetchSubscription()
                                    addingCredits = false
                                    creditsAdded = true
                                }
                            }) {
                                HStack {
                                    if addingCredits { ProgressView().tint(.white).scaleEffect(0.7) }
                                    Text(creditsAdded ? "✓ +10 CRÉDITS AJOUTÉS" : "⚡ AJOUTER 10 CRÉDITS (TRIAL)")
                                        .font(.system(size: 12, weight: .bold, design: .monospaced))
                                    Spacer()
                                }
                                .foregroundStyle(creditsAdded ? .green : .white.opacity(0.9))
                                .padding(10)
                                .overlay(Rectangle().stroke(.white.opacity(0.2), lineWidth: 1))
                            }
                            .disabled(addingCredits)

                            Button(action: {
                                UserDefaults.standard.removeObject(forKey: "rpg_user_id")
                                UserDefaults.standard.removeObject(forKey: "rpg_company_id")
                                UserDefaults.standard.removeObject(forKey: "hasCompletedOnboarding")
                                resetDone = true
                            }) {
                                HStack {
                                    Text("🗑 RESET ONBOARDING")
                                        .font(.system(size: 12, weight: .bold, design: .monospaced))
                                    Spacer()
                                    if resetDone { Text("✓").font(.system(size: 12, weight: .bold, design: .monospaced)) }
                                }
                                .foregroundStyle(resetDone ? .green : .red.opacity(0.8))
                                .padding(10)
                                .overlay(Rectangle().stroke(.white.opacity(0.2), lineWidth: 1))
                            }

                            // DELETE & RESET — supprime la company en DB + infra + reset local
                            Button(action: { showDeleteConfirm = true }) {
                                HStack {
                                    if deleteResetting { ProgressView().tint(.white).scaleEffect(0.7) }
                                    Text(deleteResetDone ? "✓ COMPANY SUPPRIMÉE" : "💣 DELETE COMPANY & RESET")
                                        .font(.system(size: 12, weight: .bold, design: .monospaced))
                                    Spacer()
                                }
                                .foregroundStyle(deleteResetDone ? .green : .orange)
                                .padding(10)
                                .overlay(Rectangle().stroke(.orange.opacity(0.4), lineWidth: 1))
                            }
                            .disabled(deleteResetting || appState.company == nil)
                            .confirmationDialog(
                                "Supprimer la company ?",
                                isPresented: $showDeleteConfirm,
                                titleVisibility: .visible
                            ) {
                                Button("Supprimer + Reset", role: .destructive) {
                                    guard let companyId = appState.company?.id else { return }
                                    deleteResetting = true
                                    Task {
                                        try? await APIClient.shared.deleteCompany(companyId: companyId)
                                        await MainActor.run {
                                            // Clear local state
                                            UserDefaults.standard.removeObject(forKey: "rpg_user_id")
                                            UserDefaults.standard.removeObject(forKey: "rpg_company_id")
                                            UserDefaults.standard.removeObject(forKey: "hasCompletedOnboarding")
                                            // Reset AppState
                                            appState.company = nil
                                            appState.hasCompletedOnboarding = false
                                            appState.missions = []
                                            appState.questChain = []
                                            deleteResetting = false
                                            deleteResetDone = true
                                            dismiss()
                                        }
                                    }
                                }
                                Button("Annuler", role: .cancel) {}
                            } message: {
                                Text("La company, ses missions, son site et son infra seront définitivement supprimés. Cette action est irréversible.")
                            }
                        }
                    }

                    retroSection("BUILD INFO") {
                        VStack(alignment: .leading, spacing: 4) {
                            infoRow("MODE", isLocal ? "LOCAL 127.0.0.1:8080" : "PRODUCTION")
                            infoRow("API KEY", "rpg-prod-key-2026")
                            infoRow("BUILD", "\(Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "?") (\(Bundle.main.infoDictionary?["CFBundleVersion"] as? String ?? "?"))")
                        }
                    }

                    Spacer(minLength: 40)
                }
                .padding(.horizontal, 16)
            }
        }
        .preferredColorScheme(.dark)
    }

    private func debugToggleBtn(_ label: String, active: Bool, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(label)
                .font(.system(size: 12, weight: .bold, design: .monospaced))
                .foregroundStyle(active ? .black : .white.opacity(0.6))
                .frame(maxWidth: .infinity)
                .padding(.vertical, 10)
                .background(active ? Color.white : Color.clear)
                .overlay(Rectangle().stroke(.white.opacity(0.4), lineWidth: 1))
        }
    }

    private func infoRow(_ key: String, _ value: String) -> some View {
        HStack(spacing: 0) {
            Text(key)
                .font(.system(size: 10, weight: .bold, design: .monospaced))
                .foregroundStyle(.white.opacity(0.4))
                .frame(width: 80, alignment: .leading)
            Text(value)
                .font(.system(size: 10, weight: .bold, design: .monospaced))
                .foregroundStyle(.white.opacity(0.7))
        }
    }
}

// MARK: - RetroNotificationsSheet

struct RetroNotificationsSheet: View {
    @EnvironmentObject private var appState: AppState
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()
            retroScanlines

            VStack(spacing: 0) {
                // Header with "tout lire" action
                ZStack {
                    sheetHeader(icon: "◫", title: "NOTIFS", subtitle: "ALERTES & ACTIVITÉ SYSTÈME", dismiss: dismiss)
                    if appState.unreadNotificationCount > 0 {
                        HStack {
                            Spacer()
                            Button(action: { Task { await appState.markNotificationsRead() } }) {
                                Text("TOUT LU")
                                    .font(mono(9)).foregroundStyle(.white.opacity(0.6))
                                    .padding(.horizontal, 8).padding(.vertical, 4)
                                    .overlay(Rectangle().stroke(.white.opacity(0.3), lineWidth: 1))
                            }
                            .padding(.trailing, 14)
                            .padding(.top, 12)
                        }
                    }
                }
                .overlay(alignment: .bottom) { Rectangle().frame(height: 1).foregroundStyle(.white.opacity(0.2)) }

                if appState.notifications.isEmpty {
                    retroEmpty("AUCUNE NOTIFICATION")
                } else {
                    ScrollView(showsIndicators: false) {
                        VStack(spacing: 0) {
                            ForEach(Array(appState.notifications.enumerated()), id: \.element.id) { idx, notif in
                                if idx > 0 { Rectangle().frame(height: 1).foregroundStyle(.white.opacity(0.08)) }
                                retroNotifRow(notif)
                            }
                        }
                        .padding(.bottom, 24)
                    }
                }
            }
        }
        .preferredColorScheme(.dark)
        .task { await appState.fetchNotifications() }
    }

    private func retroNotifRow(_ notif: CompanyNotification) -> some View {
        HStack(spacing: 10) {
            // Unread indicator
            Rectangle()
                .frame(width: 2)
                .foregroundStyle(notif.read ? Color.clear : Color.white)
                .padding(.vertical, 8)

            VStack(alignment: .leading, spacing: 3) {
                Text(notif.title.uppercased())
                    .font(mono(10))
                    .foregroundStyle(notif.read ? .white.opacity(0.4) : .white)
                    .lineLimit(1)
                Text(notif.message)
                    .font(mono(9))
                    .foregroundStyle(.white.opacity(notif.read ? 0.25 : 0.55))
                    .lineLimit(2)
            }
            Spacer()
            Text(shortDate(notif.createdAt))
                .font(mono(8)).foregroundStyle(.white.opacity(0.2))
        }
        .padding(.horizontal, 14).padding(.vertical, 10)
        .background(notif.read ? Color.clear : Color.white.opacity(0.03))
    }

    private func shortDate(_ iso: String?) -> String {
        guard let s = iso else { return "" }
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        guard let d = f.date(from: s) else { return "" }
        let rel = RelativeDateTimeFormatter()
        rel.unitsStyle = .abbreviated
        return rel.localizedString(for: d, relativeTo: Date())
    }

    private func mono(_ size: CGFloat) -> Font {
        .system(size: size, weight: .bold, design: .monospaced)
    }
}
