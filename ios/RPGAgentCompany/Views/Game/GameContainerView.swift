import SwiftUI
import SpriteKit

// MARK: - Main retro dashboard

struct GameContainerView: View {
    @EnvironmentObject private var appState: AppState

    @State private var showJournal = false      // MISSIONS bottom bar
    @State private var showQuestChain = false
    @State private var showSageChat = false
    @State private var showDebugMenu = false
    @State private var showNotifications = false

    // Card-specific detail sheets
    @State private var showAdsSheet = false
    @State private var showWebsiteSheet = false
    @State private var showDocsSheet = false
    @State private var showBusinessSheet = false
    @State private var showResearchSheet = false   // for RESEARCH (QG) card

    @State private var dialogueNPC: VillageMap.NPCDef?
    @State private var dialoguePages: [VillageMap.DialoguePage] = []
    @State private var dialoguePageIndex = 0
    @State private var showDialogue = false

    @State private var blink = false

    // MARK: - Computed

    private var company: Company? { appState.company }
    private var questChain: [QuestStep] { appState.visibleQuestChain }
    private var missions: [Mission] { appState.missions }

    private func related(_ agentId: String) -> Set<String> { Set(VillageMap.polisiaAgentTypes(for: agentId)) }
    private func step(_ agentId: String) -> QuestStep? { questChain.first { related(agentId).contains($0.agentType) && !$0.isCompleted } }
    private func running(_ agentId: String) -> [Mission] { missions.filter { related(agentId).contains($0.agentType) && ($0.isRunning || $0.isPending) } }
    private func doneCount(_ agentId: String) -> Int { questChain.filter { related(agentId).contains($0.agentType) && $0.isCompleted }.count }

    private var recentDocs: [Mission] {
        missions.filter(\.hasVisibleDeliverable)
               .sorted { ($0.createdAt ?? "") > ($1.createdAt ?? "") }
    }

    // MARK: - Body

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()
            scanlines

            VStack(spacing: 0) {
                topBar
                ScrollView(showsIndicators: false) {
                    VStack(spacing: 10) {
                        // Daily chest banner
                        if appState.dailyChestAvailable {
                            dailyChestBanner
                        }
                        // Daily brief from Sage (if any)
                        if let brief = appState.sageDailyBrief {
                            sageDailyBriefBanner(brief)
                        }
                        // Row 1 — BUSINESS + WEBSITE
                        HStack(spacing: 10) {
                            businessCard.frame(maxWidth: .infinity)
                            websiteCard.frame(maxWidth: .infinity)
                        }
                        // Row 2 — ADS + RESEARCH
                        HStack(spacing: 10) {
                            adsCard.frame(maxWidth: .infinity)
                            researchCard.frame(maxWidth: .infinity)
                        }
                        // Row 3 — DOCS (full width)
                        docsCard
                    }
                    .padding(.horizontal, 14)
                    .padding(.top, 14)
                    .refreshable { await appState.refreshMissionsAndChain() }
                    .padding(.bottom, 20)
                }
                bottomNav
            }

            if showDialogue, dialoguePageIndex < dialoguePages.count {
                dialogueOverlay
            }
        }
        .onAppear { startBlink() }
        .onChange(of: appState.showQuestChainOnLaunch) { _, show in
            if show { showQuestChain = true; appState.showQuestChainOnLaunch = false }
        }
        .sheet(isPresented: $showJournal) {
            MissionJournalView().environmentObject(appState)
        }
        .sheet(isPresented: $showQuestChain) { QuestChainView().environmentObject(appState) }
        .sheet(isPresented: $showSageChat) { SageChatView().environmentObject(appState) }
        .sheet(isPresented: $showAdsSheet) {
            RetroAdsSheet().environmentObject(appState)
        }
        .sheet(isPresented: $showWebsiteSheet) {
            RetroWebsiteSheet().environmentObject(appState)
        }
        .sheet(isPresented: $showDocsSheet) {
            RetroDocsSheet(filterAgent: nil).environmentObject(appState)
        }
        .sheet(isPresented: $showBusinessSheet) {
            RetroBusinessSheet().environmentObject(appState)
        }
        .sheet(isPresented: $showResearchSheet) {
            RetroDocsSheet(filterAgent: "researcher").environmentObject(appState)
        }
    }

    // MARK: - Scanlines

    private var scanlines: some View {
        GeometryReader { _ in
            Canvas { ctx, size in
                var y: CGFloat = 0
                while y < size.height {
                    ctx.stroke(Path { p in p.move(to: .init(x: 0, y: y)); p.addLine(to: .init(x: size.width, y: y)) },
                               with: .color(.white.opacity(0.04)), lineWidth: 1)
                    y += 4
                }
            }
        }
        .ignoresSafeArea().allowsHitTesting(false)
    }

    // MARK: - Sage daily brief banner

    @State private var sageBriefDismissed = false

    private func sageDailyBriefBanner(_ brief: String) -> some View {
        Button(action: { showSageChat = true }) {
            HStack(spacing: 10) {
                Text("◉").font(mono(16)).foregroundStyle(.white.opacity(0.7))
                VStack(alignment: .leading, spacing: 2) {
                    Text("BRIEF QUOTIDIEN — AI PUNK")
                        .font(mono(9)).foregroundStyle(.white.opacity(0.5))
                    Text(brief)
                        .font(mono(10)).foregroundStyle(.white)
                        .lineLimit(2)
                }
                Spacer()
                Button(action: { appState.dismissSageDailyBrief() }) {
                    Text("✕").font(mono(10)).foregroundStyle(.white.opacity(0.3))
                }
            }
            .padding(.horizontal, 12).padding(.vertical, 10)
            .background(Color.white.opacity(0.04))
            .overlay(Rectangle().stroke(.white.opacity(0.3), lineWidth: 1))
        }
        .buttonStyle(.plain)
        .padding(.horizontal, 14).padding(.top, 4)
    }

    // MARK: - Daily chest banner

    private var dailyChestBanner: some View {
        Button(action: { Task { await appState.claimDailyReward() } }) {
            HStack(spacing: 10) {
                Text("◈").font(mono(20)).foregroundStyle(.white)
                VStack(alignment: .leading, spacing: 2) {
                    Text("COFFRE QUOTIDIEN DISPONIBLE")
                        .font(mono(11)).foregroundStyle(.white)
                    Text("OUVRIR POUR RECEVOIR TES CRÉDITS GRATUITS")
                        .font(mono(8)).foregroundStyle(.white.opacity(0.45))
                }
                Spacer()
                Text("▶").font(mono(14)).foregroundStyle(.white.opacity(0.6))
            }
            .padding(.horizontal, 14).padding(.vertical, 12)
            .background(Color.white.opacity(0.05))
            .overlay(Rectangle().stroke(.white.opacity(0.5), lineWidth: 1))
        }
        .padding(.horizontal, 14).padding(.top, 6)
    }

    // MARK: - Top bar

    private var topBar: some View {
        HStack(spacing: 8) {
            VStack(alignment: .leading, spacing: 1) {
                Text("▌\(company?.name.uppercased() ?? "---")")
                    .font(mono(12)).foregroundStyle(.white).lineLimit(1)
                Text(company?.missionStatement ?? "")
                    .font(mono(8)).foregroundStyle(.white.opacity(0.35)).lineLimit(1)
            }
            Spacer()
            pixelTag("LV.\(company?.level ?? 1)")
            let cr = appState.subscription?.totalCredits ?? 0
            let low = appState.subscription?.isLowCredits ?? false
            pixelTag("\(cr) Credits")
                .foregroundStyle(low ? Color(red: 1, green: 0.3, blue: 0.3) : .white)
            if let co = company {
                Button(action: { Task { await appState.toggleAutoPilot() } }) {
                    Text(co.autoPilot ? "AUTO◉" : "AUTO○")
                        .font(mono(10))
                        .foregroundStyle(co.autoPilot ? .black : .white.opacity(0.4))
                        .padding(.horizontal, 5).padding(.vertical, 3)
                        .background(co.autoPilot ? Color.white : Color.clear)
                        .overlay(Rectangle().stroke(.white.opacity(0.35), lineWidth: 1))
                }
            }
            // Notification bell with badge
            Button(action: {
                showNotifications = true
                Task { await appState.markNotificationsRead() }
            }) {
                ZStack(alignment: .topTrailing) {
                    Text("◫")
                        .font(mono(12)).foregroundStyle(.white.opacity(0.5))
                    if appState.unreadNotificationCount > 0 {
                        Text("\(min(appState.unreadNotificationCount, 9))")
                            .font(.system(size: 8, weight: .black, design: .monospaced))
                            .foregroundStyle(.black)
                            .frame(width: 13, height: 13)
                            .background(Color.white)
                            .clipShape(Circle())
                            .offset(x: 5, y: -4)
                    }
                }
            }
            Button(action: { showDebugMenu = true }) {
                Text("⚙")
                    .font(mono(12)).foregroundStyle(.white.opacity(0.25))
            }
        }
        .padding(.horizontal, 14).padding(.top, 8).padding(.bottom, 10)
        .overlay(alignment: .bottom) { Rectangle().frame(height: 1).foregroundStyle(.white.opacity(0.2)) }
        .sheet(isPresented: $showDebugMenu) { DebugMenuSheet().environmentObject(appState) }
        .sheet(isPresented: $showNotifications) { RetroNotificationsSheet() }
    }

    private func pixelTag(_ t: String) -> some View {
        Text(t).font(mono(10)).foregroundStyle(.white)
            .padding(.horizontal, 6).padding(.vertical, 3)
            .overlay(Rectangle().stroke(.white.opacity(0.3), lineWidth: 1))
    }

    // MARK: - BUSINESS card

    private var businessCard: some View {
        let bld = VillageMap.buildings.first { $0.agentType == "finance" }
        let stripeStatus = company?.stripeConnectStatus ?? "not_started"
        let stripeOk = stripeStatus == "ready"
        let adsBudget = company?.adsWalletBalanceCents ?? 0

        return RetroPanel(
            icon: "◈", title: "BUSINESS",
            isActive: stripeStatus == "ready" || stripeStatus == "pending",
            blink: blink
        ) {
            VStack(alignment: .leading, spacing: 7) {
                // Business type badge
                if let co = company {
                    Text(co.businessType.displayName.uppercased())
                        .font(mono(8)).foregroundStyle(.white.opacity(0.4))
                        .padding(.horizontal, 5).padding(.vertical, 2)
                        .overlay(Rectangle().stroke(.white.opacity(0.2), lineWidth: 1))
                }
                // Stripe status
                HStack(spacing: 4) {
                    Text(stripeOk ? "STRIPE ✓" : "STRIPE ○")
                        .font(mono(9))
                        .foregroundStyle(stripeOk ? .white : .white.opacity(0.35))
                    if adsBudget > 0 {
                        Text("ADS $\(adsBudget / 100)")
                            .font(mono(8)).foregroundStyle(.white.opacity(0.4))
                    }
                }
                // Quest step
                if stripeOk {
                    panelDone
                } else if stripeStatus == "pending" {
                    panelRunning("Stripe Connect")
                } else {
                    panelLocked("Setup payments")
                }
            }
        }
        .onTapGesture { if let b = bld { openBuilding(b) } }
    }

    // MARK: - WEBSITE card

    private var websiteCard: some View {
        let bld = VillageMap.buildings.first { $0.agentType == "builder" }
        let s = step("builder")
        let r = running("builder")
        let done = doneCount("builder")
        let siteStatus = company?.siteStatus ?? "not_created"
        let siteUrl = siteStatus == "live" ? company?.siteUrl : nil
        let runningWebsite = r.filter { $0.missionType == "landing_page" || $0.missionType == "landing_page_revision" }
        let websiteRunning = siteStatus == "publishing"
            || runningWebsite.contains(where: { $0.isRunning || ($0.isPending && $0.source != "ceo_proposal") })
            || (s?.isRunning ?? false)
        let websitePendingRetry = runningWebsite.contains(where: { $0.isPending && $0.source == "ceo_proposal" })
        let websiteFailed = siteStatus == "failed"
        let hasLiveSite = siteStatus == "live" && !(siteUrl ?? "").isEmpty

        return RetroPanel(
            icon: "◈", title: "WEBSITE",
            isActive: websiteRunning || hasLiveSite || websiteFailed || websitePendingRetry || s != nil || done > 0,
            blink: blink
        ) {
            VStack(alignment: .leading, spacing: 7) {
                // URL
                if let url = siteUrl, !url.isEmpty {
                    Text(url.replacingOccurrences(of: "https://", with: ""))
                        .font(mono(8)).foregroundStyle(.white.opacity(0.7))
                        .lineLimit(1)
                        .onTapGesture { if let u = URL(string: url) { UIApplication.shared.open(u) } }
                } else {
                    Text(websiteRunning ? "PUBLICATION..." : "NON DÉPLOYÉ")
                        .font(mono(8)).foregroundStyle(.white.opacity(0.25))
                }
                // Quest step
                if websiteRunning {
                    panelRunning(r.first?.displayTitle ?? s?.title ?? "Génération site")
                } else if hasLiveSite {
                    panelDone
                } else if websiteFailed {
                    panelLocked("Erreur publication")
                } else if websitePendingRetry {
                    panelLocked("Retry à lancer")
                } else if let s, s.isAvailable {
                    panelAvailable(s)
                } else if s?.isLocked == true || (s == nil && done == 0) {
                    panelLocked(s?.title)
                } else {
                    panelLocked("Créer le site")
                }
            }
        }
        .onTapGesture { if let b = bld { openBuilding(b) } }
    }

    // MARK: - ADS card

    private var adsCard: some View {
        let bld = VillageMap.buildings.first { $0.agentType == "marketer" }
        let s = step("marketer")
        let r = running("marketer")
        let done = doneCount("marketer")
        let adsBudget = company?.adsWalletBalanceCents ?? 0

        return RetroPanel(
            icon: "◈", title: "ADS",
            isActive: s != nil || done > 0,
            blink: blink
        ) {
            VStack(alignment: .leading, spacing: 7) {
                if adsBudget > 0 {
                    HStack(spacing: 4) {
                        Text("META")
                            .font(mono(8)).foregroundStyle(.white.opacity(0.4))
                            .padding(.horizontal, 4).padding(.vertical, 2)
                            .overlay(Rectangle().stroke(.white.opacity(0.2), lineWidth: 1))
                        Text("$\(adsBudget / 100) budget")
                            .font(mono(8)).foregroundStyle(.white.opacity(0.45))
                    }
                } else {
                    Text("META ADS")
                        .font(mono(8)).foregroundStyle(.white.opacity(0.3))
                }
                if !r.isEmpty {
                    panelRunning(r.first?.displayTitle ?? "")
                } else if let s, s.isRunning {
                    panelRunning(s.title)
                } else if let s, s.isAvailable {
                    panelAvailable(s)
                } else if s?.isLocked == true || (s == nil && done == 0) {
                    panelLocked(s?.title)
                } else {
                    panelDone
                }
            }
        }
        .onTapGesture { if let b = bld { openBuilding(b) } }
    }

    // MARK: - RESEARCH card (ex QG)

    private var researchCard: some View {
        let bld = VillageMap.buildings.first { $0.agentType == "orchestrator" }
        let s = step("orchestrator")
        let r = running("orchestrator")
        let done = doneCount("orchestrator")
        let hasDocs = missions.contains { related("orchestrator").contains($0.agentType) && $0.hasVisibleDeliverable }

        return RetroPanel(
            icon: "◈", title: "RESEARCH",
            isActive: s != nil || done > 0,
            blink: blink
        ) {
            VStack(alignment: .leading, spacing: 7) {
                Text("ÉTUDE DE MARCHÉ · STRATÉGIE")
                    .font(mono(8)).foregroundStyle(.white.opacity(0.4))
                if !r.isEmpty {
                    panelRunning(r.first?.displayTitle ?? "")
                } else if let s, s.isRunning {
                    panelRunning(s.title)
                } else if let s, s.isAvailable {
                    panelAvailable(s)
                } else if s?.isLocked == true || (s == nil && done == 0) {
                    panelLocked(s?.title)
                } else if hasDocs {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("TERMINÉ  ✓").font(mono(10)).foregroundStyle(.white.opacity(0.6))
                        pixelBar(fraction: 1)
                        Text("▸  VOIR LA RECHERCHE").font(mono(9)).foregroundStyle(.white.opacity(0.5))
                    }
                } else {
                    panelDone
                }
            }
        }
        .onTapGesture { if let b = bld { openBuilding(b) } }
    }

    // MARK: - DOCS card (full width)

    private var docsCard: some View {
        VStack(alignment: .leading, spacing: 0) {
            // Header
            HStack {
                Text("◈"); Text("DOCS").lineLimit(1); Spacer()
                Text("\(recentDocs.count) doc\(recentDocs.count != 1 ? "s" : "")")
                    .foregroundStyle(.white.opacity(0.4))
            }
            .font(mono(10)).foregroundStyle(recentDocs.isEmpty ? .white.opacity(0.25) : .white)
            .padding(.horizontal, 10).padding(.top, 9).padding(.bottom, 7)

            Rectangle().frame(height: 1).foregroundStyle(.white.opacity(0.25))

            if recentDocs.isEmpty {
                Text("AUCUN DOCUMENT GÉNÉRÉ — LANCE TES PREMIÈRES MISSIONS")
                    .font(mono(9)).foregroundStyle(.white.opacity(0.22))
                    .padding(12)
            } else {
                VStack(spacing: 0) {
                    ForEach(recentDocs.prefix(4)) { doc in
                        HStack(spacing: 8) {
                            Text(docIcon(doc))
                                .font(mono(11)).foregroundStyle(.white.opacity(0.6))
                            Text(doc.missionType.replacingOccurrences(of: "_", with: " ").uppercased())
                                .font(mono(10)).foregroundStyle(.white).lineLimit(1)
                            Spacer()
                            Text(doc.agentType.prefix(3).uppercased())
                                .font(mono(8)).foregroundStyle(.white.opacity(0.35))
                        }
                        .padding(.horizontal, 10).padding(.vertical, 7)
                        if doc.id != recentDocs.prefix(4).last?.id {
                            Rectangle().frame(height: 1).foregroundStyle(.white.opacity(0.1))
                                .padding(.horizontal, 10)
                        }
                    }
                    if recentDocs.count > 4 {
                        Text("+ \(recentDocs.count - 4) autres docs →")
                            .font(mono(9)).foregroundStyle(.white.opacity(0.4))
                            .padding(.horizontal, 10).padding(.vertical, 8)
                            .frame(maxWidth: .infinity, alignment: .trailing)
                    }
                }
            }
        }
        .background(Color.black)
        .overlay(
            ZStack {
                Rectangle().stroke(recentDocs.isEmpty ? Color.white.opacity(0.45) : Color.white.opacity(0.85), lineWidth: 1)
                GeometryReader { g in
                    Group {
                        cornerDot(x: 3.5, y: 3.5); cornerDot(x: g.size.width - 3.5, y: 3.5)
                        cornerDot(x: 3.5, y: g.size.height - 3.5); cornerDot(x: g.size.width - 3.5, y: g.size.height - 3.5)
                    }.foregroundStyle(.white.opacity(recentDocs.isEmpty ? 0.35 : 0.6))
                }
            }
        )
        .onTapGesture { showDocsSheet = true }
    }

    private func docIcon(_ m: Mission) -> String {
        switch m.deliverableFormat {
        case "pdf": return "◫"
        case "html", "url": return "◻"
        case "json": return "◧"
        default: return "◨"
        }
    }

    // MARK: - Shared panel content helpers

    private func panelRunning(_ title: String) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            Text("EN COURS").font(mono(8)).foregroundStyle(.white.opacity(0.5))
            Text(title).font(mono(10)).foregroundStyle(.white).lineLimit(2)
            pixelBar(fraction: blink ? 0.55 : 0.45)
        }
    }

    private func panelAvailable(_ s: QuestStep) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            Text("ÉTAPE \(s.stepNumber)").font(mono(8)).foregroundStyle(.white.opacity(0.4))
            Text(s.title).font(mono(10)).foregroundStyle(.white).lineLimit(2)
            pixelBar(fraction: 0)
            Text("▶  LANCER").font(mono(10)).foregroundStyle(.black)
                .padding(.horizontal, 8).padding(.vertical, 4).background(Color.white)
        }
    }

    private func panelLocked(_ title: String?) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            Text("[ VERROUILLÉ ]").font(mono(9)).foregroundStyle(.white.opacity(0.22))
            if let t = title { Text(t).font(mono(9)).foregroundStyle(.white.opacity(0.18)).lineLimit(2) }
            pixelBar(fraction: 0, dimmed: true)
        }
    }

    private var panelDone: some View {
        VStack(alignment: .leading, spacing: 5) {
            Text("TERMINÉ  ✓").font(mono(10)).foregroundStyle(.white.opacity(0.6))
            pixelBar(fraction: 1)
        }
    }

    private func pixelBar(fraction: Double, dimmed: Bool = false) -> some View {
        GeometryReader { geo in
            ZStack(alignment: .leading) {
                Rectangle().foregroundStyle(.white.opacity(dimmed ? 0.05 : 0.12))
                Rectangle()
                    .frame(width: max(0, geo.size.width * CGFloat(fraction)))
                    .foregroundStyle(.white.opacity(dimmed ? 0.1 : (fraction >= 1 ? 0.8 : 0.6)))
            }
            .overlay(Rectangle().stroke(.white.opacity(dimmed ? 0.1 : 0.4), lineWidth: 0.5))
        }
        .frame(height: 6)
    }

    private func cornerDot(x: CGFloat, y: CGFloat) -> some View {
        Circle().frame(width: 3, height: 3).position(x: x, y: y)
    }

    // MARK: - Bottom nav   [AI PUNK | MISSIONS | TASKS]

    private var activeMissionCount: Int {
        missions.filter { $0.isPending || $0.isRunning }.count
    }

    private var bottomNav: some View {
        HStack(spacing: 0) {
            navBtn("◉", "AI PUNK") { showSageChat = true }
            navSep
            navBtn("◆", "MISSIONS", badgeCount: activeMissionCount) { showJournal = true }
            navSep
            navBtn("◇", "TASKS") { showQuestChain = true }
        }
        .frame(height: 54)
        .background(Color.black)
        .overlay(alignment: .top) { Rectangle().frame(height: 1).foregroundStyle(.white.opacity(0.2)) }
    }

    private func navBtn(_ icon: String, _ label: String, badgeCount: Int = 0, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            ZStack(alignment: .topTrailing) {
                VStack(spacing: 3) {
                    Text(icon).font(mono(13))
                    Text(label).font(mono(7))
                }
                .frame(maxWidth: .infinity)

                if badgeCount > 0 {
                    Text("\(badgeCount)")
                        .font(mono(7))
                        .foregroundStyle(.black)
                        .padding(.horizontal, 4)
                        .padding(.vertical, 1)
                        .background(PixelTheme.accentGreen)
                        .clipShape(Capsule())
                        .padding(.trailing, 18)
                        .padding(.top, 3)
                }
            }
            .foregroundStyle(.white.opacity(0.55)).frame(maxWidth: .infinity)
        }
    }

    private var navSep: some View {
        Rectangle().frame(width: 1).foregroundStyle(.white.opacity(0.15)).padding(.vertical, 14)
    }

    // MARK: - Dialogue overlay

    private var dialogueOverlay: some View {
        VStack {
            Spacer()
            let page = dialoguePages[dialoguePageIndex]
            VStack(alignment: .leading, spacing: 10) {
                if let npc = dialogueNPC {
                    HStack(spacing: 6) { Text("▌"); Text(npc.name.uppercased()) }
                        .font(mono(11)).foregroundStyle(.white)
                    Rectangle().frame(height: 1).foregroundStyle(.white.opacity(0.3))
                }
                Text(page.text).font(mono(11)).foregroundStyle(.white.opacity(0.9))
                    .fixedSize(horizontal: false, vertical: true).id("p_\(dialoguePageIndex)")
                HStack {
                    Spacer()
                    if let choices = page.choices {
                        ForEach(Array(choices.enumerated()), id: \.offset) { _, c in
                            Button(c.label) { handleChoice(c.action) }
                                .font(mono(11))
                                .foregroundStyle(c.action == .close ? .white.opacity(0.5) : .black)
                                .padding(.horizontal, 10).padding(.vertical, 7)
                                .background(c.action == .close ? Color.clear : Color.white)
                                .overlay(Rectangle().stroke(c.action == .close ? Color.white.opacity(0.4) : Color.white, lineWidth: 1))
                        }
                    } else {
                        Button("▶") { withAnimation(.easeOut(duration: 0.15)) { dialoguePageIndex += 1 } }
                            .font(mono(14)).foregroundStyle(.black)
                            .padding(.horizontal, 14).padding(.vertical, 7).background(Color.white)
                    }
                }
            }
            .padding(16).background(Color.black)
            .overlay(ZStack {
                Rectangle().stroke(Color.white.opacity(0.8), lineWidth: 1)
                GeometryReader { g in
                    Group {
                        cornerDot(x: 4, y: 4); cornerDot(x: g.size.width-4, y: 4)
                        cornerDot(x: 4, y: g.size.height-4); cornerDot(x: g.size.width-4, y: g.size.height-4)
                    }.foregroundStyle(.white.opacity(0.5))
                }
            })
            .padding(.horizontal, 20).padding(.bottom, 74)
        }
        .transition(.move(edge: .bottom).combined(with: .opacity))
        .animation(.easeOut(duration: 0.2), value: showDialogue)
    }

    private func handleChoice(_ action: VillageMap.DialogueAction) {
        switch action {
        case .nextPage:
            withAnimation(.easeOut(duration: 0.15)) { dialoguePageIndex += 1 }
        case .close:
            withAnimation(.easeOut(duration: 0.2)) { showDialogue = false }
        case .openQuests:
            showDialogue = false; showQuestChain = true
        case .openSageChat:
            showDialogue = false; showSageChat = true
        case .openAdsDetail:
            showDialogue = false; showAdsSheet = true
        case .openWebsiteDetail:
            showDialogue = false; showWebsiteSheet = true
        case .openDocsDetail:
            showDialogue = false; showDocsSheet = true
        case .openBusinessDetail:
            showDialogue = false; showBusinessSheet = true
        case .openResearchDetail:
            showDialogue = false; showResearchSheet = true
        }
    }

    // MARK: - Open building (triggers NPC dialogue)

    private func openBuilding(_ bld: VillageMap.BuildingDef) {
        let npc = VillageMap.npcs.first { $0.agentType == bld.agentType }
            ?? VillageMap.NPCDef(id: "npc_\(bld.agentType)", name: bld.name,
                                 tileX: 0, tileY: 0, dialogue: "", agentType: bld.agentType)
        let rel = related(bld.agentType)
        let hasRunning = missions.contains { rel.contains($0.agentType) && ($0.isRunning || $0.isPending) }
        let hasDone = missions.contains { rel.contains($0.agentType) && $0.hasVisibleDeliverable }
        let visitedKey = "visited_\(npc.id)"
        let isFirst = !UserDefaults.standard.bool(forKey: visitedKey)
        UserDefaults.standard.set(true, forKey: visitedKey)

        dialogueNPC = npc
        dialoguePages = VillageMap.dialoguePages(
            for: npc, hasRunningMission: hasRunning, hasCompletedMission: hasDone,
            isFirstVisit: isFirst, missionCount: missions.count,
            questChain: questChain, businessType: company?.businessType ?? .ecommerce
        )
        dialoguePageIndex = 0
        withAnimation(.easeOut(duration: 0.2)) { showDialogue = true }
    }

    // MARK: - Blink + font

    private func startBlink() {
        func tick() { DispatchQueue.main.asyncAfter(deadline: .now() + 0.6) { blink.toggle(); tick() } }
        tick()
    }
    private func mono(_ size: CGFloat) -> Font { .system(size: size, weight: .bold, design: .monospaced) }
}

// MARK: - Reusable retro panel wrapper

private struct RetroPanel<Content: View>: View {
    let icon: String
    let title: String
    let isActive: Bool
    let blink: Bool
    @ViewBuilder let content: Content

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 5) {
                Text(icon).foregroundStyle(.white.opacity(isActive ? 1.0 : 0.55))
                Text(title.uppercased()).lineLimit(1)
                Spacer()
            }
            .font(.system(size: 10, weight: .bold, design: .monospaced))
            .foregroundStyle(.white.opacity(isActive ? 1.0 : 0.55))
            .padding(.horizontal, 10).padding(.top, 9).padding(.bottom, 7)

            Rectangle().frame(height: 1).foregroundStyle(.white.opacity(isActive ? 0.4 : 0.25))

            content
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(10)
        }
        .background(Color.black)
        .overlay(ZStack {
            Rectangle().stroke(isActive ? Color.white.opacity(0.85) : Color.white.opacity(0.45), lineWidth: 1)
            GeometryReader { g in
                Group {
                    dot(x: 3.5, y: 3.5); dot(x: g.size.width-3.5, y: 3.5)
                    dot(x: 3.5, y: g.size.height-3.5); dot(x: g.size.width-3.5, y: g.size.height-3.5)
                }.foregroundStyle(.white.opacity(isActive ? 0.6 : 0.35))
            }
        })
    }
    private func dot(x: CGFloat, y: CGFloat) -> some View {
        Circle().frame(width: 3, height: 3).position(x: x, y: y)
    }
}

// MARK: - Map modal (accessible from… nowhere for now — kept as hidden utility)

struct MapSheetView: View {
    @EnvironmentObject private var appState: AppState
    @Environment(\.dismiss) private var dismiss
    @State private var gameScene: GameScene?

    var body: some View {
        ZStack {
            if let scene = gameScene {
                SpriteView(scene: scene).ignoresSafeArea().grayscale(1.0)
            } else {
                Color.black.ignoresSafeArea()
                ProgressView().tint(.white)
            }
            VStack {
                HStack {
                    Spacer()
                    Button(action: { dismiss() }) {
                        Text("✕  FERMER")
                            .font(.system(size: 11, weight: .bold, design: .monospaced))
                            .foregroundStyle(.white).padding(.horizontal, 12).padding(.vertical, 8)
                            .background(Color.black.opacity(0.85))
                            .overlay(Rectangle().stroke(.white.opacity(0.5), lineWidth: 1))
                    }.padding(16)
                }
                Spacer()
            }
        }
        .onAppear { setupScene() }
    }

    private func setupScene() {
        guard gameScene == nil else { return }
        let ts = TilesetManager.tileSize
        let scene = GameScene(size: CGSize(width: CGFloat(VillageMap.width)*ts, height: CGFloat(VillageMap.height)*ts))
        scene.scaleMode = .aspectFill
        scene.playerLevel = appState.company?.level ?? 1
        if let b = appState.company?.buildings {
            scene.activeAgentTypes = Set(b.map { $0.agentType }.filter { VillageMap.polisiaBuildingAgents.contains($0) })
        }
        scene.callbacks.onNPCInteract = { _ in }
        scene.callbacks.onNearSage = { _ in }
        scene.callbacks.onBuildingEnter = { _ in }
        scene.callbacks.onCollectLoot = { _ in }
        scene.callbacks.onDailyChest = { Task { await appState.claimDailyReward() } }
        gameScene = scene
    }
}
