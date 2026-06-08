import SwiftUI
import SpriteKit

struct GameContainerView: View {
    @EnvironmentObject private var appState: AppState
    @State private var gameScene: GameScene?
    @State private var selectedBuilding: Building?
    @State private var dialogueNPC: VillageMap.NPCDef?
    @State private var dialoguePages: [VillageMap.DialoguePage] = []
    @State private var dialoguePageIndex = 0
    @State private var showDialogue = false
    @State private var showMissionBoard = false
    @State private var showJournal = false
    @State private var showQuestChain = false
    @State private var showSageChat = false
    @State private var showNotifications = false
    @State private var lootMission: Mission?
    @State private var isNearSage = false
    @State private var previousXP: Int = 0
    @State private var previousLevel: Int = 1
    @State private var previousCredits: Int = 0

    private var hudCreditTotal: Int {
        appState.subscription?.totalCredits ?? (appState.company?.wallet.creditsBalance ?? 0)
    }

    private var hudCreditColor: Color {
        if hudCreditTotal == 0 { return PixelTheme.accentRed }
        if hudCreditTotal < 3  { return PixelTheme.accentRed }
        return PixelTheme.accent
    }

    private var hudCreditText: String {
        "\(hudCreditTotal) CR"
    }

    var body: some View {
        ZStack {
            if let scene = gameScene {
                SpriteView(scene: scene)
                    .ignoresSafeArea()
            } else {
                Color.black.ignoresSafeArea()
                ProgressView().tint(.yellow)
            }

            VStack {
                hudBar
                Spacer()
            }

            if isNearSage && !showDialogue {
                sageProximityPopup
            }

            if showDialogue, dialoguePageIndex < dialoguePages.count {
                dialogueOverlay
            }
        }
        .onAppear { setupScene() }
        .onChange(of: appState.missions) { syncMissionStates() }
        .onChange(of: appState.lootToPresent?.id) { _, newId in
            if let id = newId, let mission = appState.lootToPresent, mission.id == id {
                // #region agent log
                let dLen = mission.deliverable?.count ?? -1
                let dPreview = mission.deliverable.map { String($0.prefix(80)) } ?? "NIL"
                print("[DEBUG-H2] GameContainerView.onChange(lootToPresent): capturing mission \(id). deliverable len=\(dLen) preview='\(dPreview)'")
                // #endregion
                lootMission = mission
                appState.lootToPresent = nil
            }
        }
        .onChange(of: appState.showQuestChainOnLaunch) { _, show in
            if show {
                showQuestChain = true
                appState.showQuestChainOnLaunch = false
            }
        }
        .onChange(of: appState.company?.xp) { handleXPChange(newXP: appState.company?.xp ?? 0) }
        .onChange(of: appState.company?.wallet.creditsBalance) { handleCreditChange(newBal: appState.company?.wallet.creditsBalance ?? 0) }
        .onChange(of: appState.company?.level) {
            let lvl = appState.company?.level ?? 1
            if lvl > previousLevel {
                gameScene?.showLevelUp(level: lvl)
                previousLevel = lvl
            }
        }
        .sheet(item: $selectedBuilding) { building in
            BuildingDetailView(building: building)
                .environmentObject(appState)
        }
        .sheet(isPresented: $showJournal) {
            MissionJournalView()
                .environmentObject(appState)
        }
        .sheet(isPresented: $showQuestChain) {
            QuestChainView()
                .environmentObject(appState)
        }
        .sheet(isPresented: $showSageChat) {
            SageChatView()
                .environmentObject(appState)
        }
        .sheet(item: $lootMission) { mission in
            LootRevealView(mission: mission) {
                syncMissionStates()
            }
            .environmentObject(appState)
        }
        .sheet(isPresented: $showNotifications) {
            NotificationsView()
                .environmentObject(appState)
        }
        .task { await appState.fetchNotifications() }
    }

    // MARK: - HUD (landscape layout with XP bar)

    private var hudBar: some View {
        HStack(spacing: 10) {
            Text(appState.company?.name.uppercased() ?? "BASE")
                .font(PixelTheme.captionFont)
                .foregroundStyle(PixelTheme.textPrimary)
                .lineLimit(1)
                .truncationMode(.tail)
                .frame(maxWidth: 80)

            xpBarCompact
                .frame(width: 100)

            Spacer()

            Button(action: { showQuestChain = true }) {
                HStack(spacing: 3) {
                    Text("⚔")
                        .font(.system(size: 11))
                    Text("QUÊTES")
                        .font(PixelTheme.microFont)
                        .foregroundStyle(PixelTheme.accent)
                        .lineLimit(1)
                        .fixedSize()
                }
            }

            Button(action: { showJournal = true }) {
                HStack(spacing: 3) {
                    Text("📜")
                        .font(.system(size: 11))
                    Text("JOURNAL")
                        .font(PixelTheme.microFont)
                        .foregroundStyle(PixelTheme.textSecondary)
                        .lineLimit(1)
                        .fixedSize()
                }
            }

            // Notification bell
            Button { showNotifications = true } label: {
                ZStack(alignment: .topTrailing) {
                    Image(systemName: "bell.fill")
                        .font(.system(size: 12))
                        .foregroundStyle(appState.unreadNotificationCount > 0 ? PixelTheme.accent : PixelTheme.textSecondary)
                    if appState.unreadNotificationCount > 0 {
                        Text("\(min(appState.unreadNotificationCount, 9))")
                            .font(.system(size: 8, weight: .bold))
                            .foregroundStyle(PixelTheme.bgDark)
                            .padding(2)
                            .background(PixelTheme.accentRed, in: Circle())
                            .offset(x: 4, y: -4)
                    }
                }
            }

            // Polsia credit HUD — rouge si < 3
            HStack(spacing: 3) {
                Image(systemName: "bolt.fill")
                    .font(.system(size: 9, weight: .bold))
                    .foregroundStyle(hudCreditColor)
                Text(hudCreditText)
                    .font(PixelTheme.microFont)
                    .foregroundStyle(hudCreditColor)
                    .lineLimit(1)
                    .fixedSize()
            }

            if appState.dailyStreak > 0 {
                HStack(spacing: 2) {
                    Text("🔥")
                        .font(.system(size: 10))
                    Text("\(appState.dailyStreak)j")
                        .font(PixelTheme.microFont)
                        .foregroundStyle(PixelTheme.accentPurple)
                }
            }
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 6)
        .background(PixelTheme.bgDark.opacity(0.8).background(.ultraThinMaterial))
    }

    private var xpBarCompact: some View {
        let xp = appState.company?.xp ?? 0
        let level = appState.company?.level ?? 1
        let nextLvl = appState.xpForNextLevel
        let progress = nextLvl > 0 ? min(Double(xp) / Double(nextLvl), 1.0) : 0

        return HStack(spacing: 4) {
            Text("LV.\(level)")
                .font(PixelTheme.microFont)
                .foregroundStyle(PixelTheme.accent)

            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 2)
                        .fill(PixelTheme.bgDark)
                    RoundedRectangle(cornerRadius: 2)
                        .fill(PixelTheme.accentGreen)
                        .frame(width: max(geo.size.width * progress, 2))
                        .animation(.easeOut(duration: 0.6), value: xp)
                }
            }
            .frame(height: 6)

            Text("\(xp)/\(nextLvl)")
                .font(PixelTheme.microFont)
                .foregroundStyle(PixelTheme.textSecondary)
        }
    }

    // MARK: - Multi-page Dialogue

    private var dialogueOverlay: some View {
        VStack {
            Spacer()

            let page = dialoguePages[dialoguePageIndex]

            VStack(alignment: .leading, spacing: 6) {
                if let npc = dialogueNPC {
                    Text(npc.name.uppercased())
                        .font(PixelTheme.bodyFont)
                        .foregroundStyle(PixelTheme.accent)
                }

                Text(page.text)
                    .font(PixelTheme.captionFont)
                    .foregroundStyle(PixelTheme.textPrimary)
                    .transition(.opacity)
                    .id("dialogue_\(dialoguePageIndex)")

                HStack {
                    Spacer()

                    if let choices = page.choices {
                        ForEach(Array(choices.enumerated()), id: \.offset) { _, choice in
                            Button(choice.label) {
                                handleDialogueChoice(choice.action)
                            }
                            .buttonStyle(PixelButtonStyle(
                                color: choice.action == .close ? PixelTheme.bgLight
                                    : choice.action == .openSageChat ? PixelTheme.accentPurple
                                    : PixelTheme.accent
                            ))
                        }
                    } else {
                        Button("▶") {
                            withAnimation(.easeOut(duration: 0.15)) {
                                dialoguePageIndex += 1
                            }
                        }
                        .buttonStyle(PixelButtonStyle())
                    }
                }
            }
            .padding(14)
            .background(
                RoundedRectangle(cornerRadius: PixelTheme.cardRadius)
                    .fill(PixelTheme.bgDark.opacity(0.95))
                    .overlay(RoundedRectangle(cornerRadius: PixelTheme.cardRadius)
                        .stroke(PixelTheme.accent, lineWidth: 2))
            )
            .padding(.horizontal, 40)
            .padding(.bottom, 20)
        }
        .transition(.move(edge: .bottom))
    }

    private var sageProximityPopup: some View {
        GeometryReader { geo in
            Button {
                showSageChat = true
            } label: {
                HStack(spacing: 8) {
                    Text("🔮")
                        .font(.system(size: 16))
                    Text("PARLER AU SAGE")
                        .font(PixelTheme.captionFont)
                        .foregroundStyle(PixelTheme.textPrimary)
                        .lineLimit(1)
                        .fixedSize()
                }
                .padding(.horizontal, 20)
                .padding(.vertical, 10)
                .background(
                    RoundedRectangle(cornerRadius: PixelTheme.cardRadius)
                        .fill(PixelTheme.accentPurple.opacity(0.85))
                        .overlay(
                            RoundedRectangle(cornerRadius: PixelTheme.cardRadius)
                                .stroke(PixelTheme.accent, lineWidth: 2)
                        )
                )
            }
            .position(x: geo.size.width / 2, y: geo.size.height * 0.77)
        }
        .transition(.move(edge: .bottom).combined(with: .opacity))
        .animation(.easeOut(duration: 0.25), value: isNearSage)
    }

    private func handleDialogueChoice(_ action: VillageMap.DialogueAction) {
        switch action {
        case .nextPage:
            withAnimation(.easeOut(duration: 0.15)) {
                dialoguePageIndex += 1
            }
        case .close:
            withAnimation(.easeOut(duration: 0.2)) {
                showDialogue = false
            }
        case .openQuests:
            showDialogue = false
            if let npc = dialogueNPC, let agentType = npc.agentType,
               let building = appState.company?.buildings.first(where: { $0.agentType == agentType }) {
                selectedBuilding = building
            }
        case .openSageChat:
            showDialogue = false
            showSageChat = true
        }
    }

    // MARK: - Mission state sync

    private func syncMissionStates() {
        guard let scene = gameScene else { return }
        guard let buildings = appState.company?.buildings else { return }

        for building in buildings {
            let agentTypes = Set(VillageMap.polisiaAgentTypes(for: building.agentType))
            let agentMissions = appState.missions.filter { agentTypes.contains($0.agentType) }
            let buildingId = buildingIdForAgent(building.agentType)
            if agentMissions.contains(where: { $0.status == "running" || $0.status == "pending" }) {
                scene.updateBuildingMissionState(buildingId: buildingId, state: .running)
            } else if let completed = agentMissions.first(where: { $0.status == "completed" && $0.deliverable != nil }) {
                scene.updateBuildingMissionState(
                    buildingId: buildingId,
                    state: .completed(missionId: completed.id)
                )
            } else {
                scene.updateBuildingMissionState(buildingId: buildingId, state: .idle)
            }
        }
    }

    private func buildingIdForAgent(_ agentType: String) -> String {
        switch agentType {
        case "orchestrator": return "hq"
        case "builder": return "forge"
        case "marketer": return "market"
        case "finance": return "bank"
        default: return ""
        }
    }

    // MARK: - Floating text triggers

    private func handleXPChange(newXP: Int) {
        let diff = newXP - previousXP
        if diff > 0 && previousXP > 0 {
            gameScene?.showFloatingText(
                "+\(diff) XP",
                color: UIColor(red: 0.2, green: 0.85, blue: 0.4, alpha: 1)
            )
        }
        previousXP = newXP
    }

    private func handleCreditChange(newBal: Int) {
        let diff = newBal - previousCredits
        if diff != 0 && previousCredits > 0 {
            let text = diff > 0 ? "+\(diff)" : "\(diff)"
            gameScene?.showFloatingText(
                "\(text) ◆",
                color: UIColor(red: 1, green: 0.78, blue: 0.2, alpha: 1)
            )
        }
        previousCredits = newBal
    }

    // MARK: - Scene setup (landscape 64x40 tiles)

    private func setupScene() {
        let ts = TilesetManager.tileSize
        let scene = GameScene(size: CGSize(
            width: CGFloat(VillageMap.width) * ts,
            height: CGFloat(VillageMap.height) * ts
        ))
        scene.scaleMode = .aspectFill
        scene.playerLevel = appState.company?.level ?? 1
        if let buildings = appState.company?.buildings {
            scene.activeAgentTypes = Set(
                buildings.map { $0.agentType }.filter { VillageMap.polisiaBuildingAgents.contains($0) }
            )
        }

        previousXP = appState.company?.xp ?? 0
        previousLevel = appState.company?.level ?? 1
        previousCredits = appState.company?.wallet.creditsBalance ?? 0

        scene.callbacks.onBuildingEnter = { bldDef in
            if let building = appState.company?.buildings.first(where: { $0.agentType == bldDef.agentType }) {
                selectedBuilding = building
            }
        }

        scene.callbacks.onNPCInteract = { npc in
            let relatedTypes: Set<String> = {
                guard let at = npc.agentType else { return [] }
                return Set(VillageMap.polisiaAgentTypes(for: at))
            }()
            let hasRunning = appState.missions.contains {
                relatedTypes.contains($0.agentType) && ($0.status == "running" || $0.status == "pending")
            }
            let hasCompleted = appState.missions.contains {
                relatedTypes.contains($0.agentType) && $0.status == "completed" && $0.deliverable != nil
            }
            let visitedKey = "visited_\(npc.id)"
            let isFirstVisit = !UserDefaults.standard.bool(forKey: visitedKey)
            UserDefaults.standard.set(true, forKey: visitedKey)

            dialogueNPC = npc
            dialoguePages = VillageMap.dialoguePages(
                for: npc,
                hasRunningMission: hasRunning,
                hasCompletedMission: hasCompleted,
                isFirstVisit: isFirstVisit,
                missionCount: appState.missions.count,
                questChain: appState.questChain,
                businessType: appState.company?.businessType ?? .ecommerce
            )
            dialoguePageIndex = 0
            withAnimation(.easeOut(duration: 0.2)) { showDialogue = true }
        }

        scene.callbacks.onNearSage = { near in
            withAnimation(.easeOut(duration: 0.25)) {
                isNearSage = near
            }
        }

        scene.callbacks.onCollectLoot = { missionId in
            if let mission = appState.missions.first(where: { $0.id == missionId }) {
                lootMission = mission
                AnalyticsTracker.track("deliverable_viewed", properties: [
                    "mission_type": mission.missionType,
                    "source": "village_loot",
                ])
            }
        }

        scene.callbacks.onDailyChest = {
            Task { await appState.claimDailyReward() }
        }

        if appState.dailyChestAvailable {
            scene.showDailyChest(at: 30, tileY: 20)
        }

        gameScene = scene
        syncMissionStates()
    }
}
