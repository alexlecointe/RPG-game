import Foundation

enum AgentOnboardingStatus {
    case pending, running, done
}

@MainActor
final class AppState: ObservableObject {
    @Published var userId: String?
    @Published var company: Company?
    @Published var missions: [Mission] = []
    @Published var catalog: [MissionCatalogItem] = []
    @Published var isLoading = false
    @Published var errorMessage: String?
    @Published var hasCompletedOnboarding = false
    @Published var dailyChestAvailable = false
    @Published var dailyStreak: Int = 0
    @Published var questProgress: [String: Bool] = [:]
    @Published var questChain: [QuestStep] = []
    @Published var onboardingAgentStatus: [String: AgentOnboardingStatus] = [:]
    @Published var onboardingReady = false
    @Published var activityLog: [ActivityLogEntry] = []
    @Published var agentActivityFeed: [ActivityFeedEntry] = []
    @Published var justCompletedAgentTypes: Set<String> = []
    @Published var pendingMissionCompletions: [(agentType: String, missionType: String)] = []
    @Published var lootToPresent: Mission?
    @Published var showQuestChainOnLaunch = false
    @Published var sageMessages: [SageMessage] = []
    @Published var isSageLoading = false
    @Published var sageDailyBrief: String? = nil
    @Published var subscription: SubscriptionInfo?
    @Published var taskQueue: [Mission] = []
    @Published var recurringMissions: [RecurringMission] = []
    @Published var notifications: [CompanyNotification] = []

    private let api = APIClient.shared
    private let deviceIdKey = "rpg_device_id"
    private let companyIdKey = "rpg_company_id"
    private let lastDailyKey = "rpg_last_daily"
    private let streakKey = "rpg_streak"
    private let questKey = "rpg_quests"
    private let sageBriefKey = "rpg_sage_brief"
    private let sageBriefDateKey = "rpg_sage_brief_date"

    var deviceId: String {
        if let existing = UserDefaults.standard.string(forKey: deviceIdKey) {
            return existing
        }
        let id = UUID().uuidString
        UserDefaults.standard.set(id, forKey: deviceIdKey)
        return id
    }

    func fetchSubscription() async {
        guard let companyId = company?.id else { return }
        do {
            subscription = try await api.fetchSubscription(companyId: companyId)
        } catch {
            APIClient.debugLog("fetchSubscription FAIL", data: ["error": "\(error)"], hypothesis: "H-credits", location: "AppState.fetchSubscription")
        }
    }

    func fetchTaskQueue() async {
        guard let companyId = company?.id else { return }
        if let queue = try? await api.fetchTaskQueue(companyId: companyId) {
            taskQueue = queue.sorted { ($0.queueOrder ?? 999) < ($1.queueOrder ?? 999) }
        }
    }

    func fetchRecurringMissions() async {
        guard let companyId = company?.id else { return }
        if let list = try? await api.fetchRecurringMissions(companyId: companyId) {
            recurringMissions = list
        }
    }

    func createRecurringMission(missionType: String, frequency: String, dayOfWeek: Int? = nil, dayOfMonth: Int? = nil, hourUtc: Int = 9) async {
        guard let companyId = company?.id else { return }
        let body = RecurringMissionCreate(missionType: missionType, frequency: frequency, dayOfWeek: dayOfWeek, dayOfMonth: dayOfMonth, hourUtc: hourUtc)
        if let rm = try? await api.createRecurringMission(companyId: companyId, body: body) {
            recurringMissions.insert(rm, at: 0)
        }
    }

    func deleteRecurringMission(id: String) async {
        try? await api.deleteRecurringMission(recurringId: id)
        recurringMissions.removeAll { $0.id == id }
    }

    var unreadNotificationCount: Int {
        notifications.filter { !$0.read }.count
    }

    func fetchNotifications() async {
        guard let companyId = company?.id else { return }
        if let list = try? await api.fetchNotifications(companyId: companyId) {
            notifications = list
        }
    }

    func markNotificationsRead() async {
        guard let companyId = company?.id else { return }
        try? await api.markNotificationsRead(companyId: companyId)
        notifications = notifications.map { n in
            CompanyNotification(id: n.id, type: n.type, title: n.title, message: n.message, read: true, createdAt: n.createdAt)
        }
    }

    func startNotificationPolling() {
        Task {
            while company != nil {
                try? await Task.sleep(nanoseconds: 15_000_000_000) // 15s
                let prevNotifCount = notifications.count
                let prevUnread = unreadNotificationCount
                await fetchNotifications()

                // If new notifications arrived that signal a mission/step change → refresh
                let hasNewActionNotif = notifications.prefix(5).contains {
                    ["step_completed", "step_unlocked", "chain_completed", "mission_started",
                     "site_deployed", "payment_received"].contains($0.type)
                }
                let gotNewNotif = notifications.count > prevNotifCount || unreadNotificationCount > prevUnread
                if gotNewNotif && hasNewActionNotif {
                    await refreshMissionsAndChain()
                }
            }
        }

        // Separate mission polling every 20s while any mission is running
        Task {
            while company != nil {
                try? await Task.sleep(nanoseconds: 20_000_000_000) // 20s
                let hasActive = missions.contains { $0.isRunning || $0.isPending }
                if hasActive {
                    await refreshMissionsAndChain()
                }
            }
        }
    }

    func refreshMissionsAndChain() async {
        guard let companyId = company?.id else { return }
        let updated = (try? await api.fetchMissions(companyId: companyId)) ?? missions
        let updatedChain = (try? await api.fetchQuestChain(companyId: companyId)) ?? questChain

        // Detect newly completed missions → show loot
        for m in updated where m.isCompleted && m.deliverable != nil {
            if let prev = missions.first(where: { $0.id == m.id }), prev.isRunning {
                lootToPresent = m
                justCompletedAgentTypes.insert(m.agentType)
            }
        }

        missions = updated
        questChain = updatedChain
    }

    func toggleAutoPilot() async {
        guard let company else { return }
        let newValue = !company.autoPilot
        do {
            _ = try await api.toggleAutoPilot(companyId: company.id, enabled: newValue)
            self.company = try await api.fetchCompany(id: company.id)
            await fetchNotifications()
        } catch {
            APIClient.debugLog("toggleAutoPilot FAIL", data: ["error": "\(error)"], hypothesis: "H-autopilot", location: "AppState.toggleAutoPilot")
        }
    }

    func rejectTask(id: String, reason: String = "user_cancelled") async {
        do {
            try await api.rejectTask(missionId: id, reason: reason)
            taskQueue.removeAll { $0.id == id }
            await fetchSubscription()
        } catch {
            errorMessage = "Impossible de rejeter la tâche"
        }
    }

    func moveToTop(id: String) async {
        do {
            let updated = try await api.moveTaskToTop(missionId: id)
            if let idx = taskQueue.firstIndex(where: { $0.id == id }) {
                taskQueue.remove(at: idx)
                taskQueue.insert(updated, at: 0)
            }
        } catch {
            errorMessage = "Impossible de déplacer la tâche"
        }
    }

    func bootstrap() async {
        loadLocalState()
        NotificationManager.shared.requestPermission()
        NotificationManager.shared.cancelReengagementReminder()

        // #region agent log
        let savedId = UserDefaults.standard.string(forKey: companyIdKey)
        APIClient.debugLog("bootstrap START", data: ["savedCompanyId": savedId ?? "nil"], hypothesis: "H1", location: "AppState.bootstrap")
        // #endregion

        if let savedCompanyId = UserDefaults.standard.string(forKey: companyIdKey) {
            isLoading = true
            defer { isLoading = false }

            for attempt in 0..<4 {
                if attempt > 0 {
                    try? await Task.sleep(for: .seconds(Double(attempt) * 1.5))
                }
                do {
                    let user = try await api.registerUser(deviceId: deviceId)
                    userId = user.id
                    company = try await api.fetchCompany(id: savedCompanyId)
                    catalog = try await api.fetchCatalog()
                    missions = try await api.fetchMissions(companyId: savedCompanyId)
                    questChain = (try? await api.fetchQuestChain(companyId: savedCompanyId)) ?? []
                    subscription = try? await api.initSubscription(companyId: savedCompanyId)
                    hasCompletedOnboarding = true
                    // #region agent log
                    APIClient.debugLog("bootstrap SUCCESS", data: ["attempt": attempt], hypothesis: "H1", location: "AppState.bootstrap")
                    // #endregion
                    checkDailyChest()
                    loadSageHistory()
                    startNotificationPolling()
                    return
                } catch {
                    // #region agent log
                    APIClient.debugLog("bootstrap FAIL", data: ["attempt": attempt, "error": "\(error)"], hypothesis: "H1", location: "AppState.bootstrap")
                    // #endregion
                    if attempt == 3 {
                        UserDefaults.standard.removeObject(forKey: companyIdKey)
                    }
                }
            }
            // #region agent log
            APIClient.debugLog("bootstrap EXHAUSTED — removed stale ID", hypothesis: "H1", location: "AppState.bootstrap")
            // #endregion
        } else {
            // #region agent log
            APIClient.debugLog("bootstrap NO saved ID — show onboarding", hypothesis: "H1", location: "AppState.bootstrap")
            // #endregion
        }
    }

    func skipToGame(
        name: String = "Ma Base",
        businessType: BusinessType = .ecommerce
    ) {
        company = Company.demo(name: name, businessType: businessType)
        hasCompletedOnboarding = true
        onboardingReady = true
    }

    func createNewCompany(
        name: String,
        missionStatement: String,
        productDescription: String = "",
        targetAudience: String = "",
        businessType: BusinessType = .ecommerce
    ) async {
        isLoading = true
        // #region agent log
        APIClient.debugLog("createNewCompany START", data: ["name": name, "businessType": businessType.rawValue], hypothesis: "H2", location: "AppState.createNewCompany")
        // #endregion

        for attempt in 0..<4 {
            if attempt > 0 {
                // Exponential back-off — gives Render time to wake up from cold start
                let delay: Double = [5, 15, 30][min(attempt - 1, 2)]
                try? await Task.sleep(for: .seconds(delay))
            }
            do {
                // #region agent log
                APIClient.debugLog("createNewCompany attempt \(attempt) — registerUser", hypothesis: "H3", location: "AppState.createNewCompany")
                // #endregion
                let user = try await api.registerUser(deviceId: deviceId)
                userId = user.id
                // #region agent log
                APIClient.debugLog("createNewCompany attempt \(attempt) — registerUser OK, calling createCompany", data: ["userId": user.id], hypothesis: "H3", location: "AppState.createNewCompany")
                // #endregion
                let newCompany = try await api.createCompany(
                    userId: user.id,
                    name: name,
                    missionStatement: missionStatement,
                    productDescription: productDescription,
                    targetAudience: targetAudience,
                    businessType: businessType
                )
                // #region agent log
                APIClient.debugLog("createNewCompany attempt \(attempt) — createCompany OK", data: ["companyId": newCompany.id], hypothesis: "H2", location: "AppState.createNewCompany")
                // #endregion
                UserDefaults.standard.set(newCompany.id, forKey: companyIdKey)
                company = try await api.fetchCompany(id: newCompany.id)
                catalog = (try? await api.fetchCatalog()) ?? []
                missions = (try? await api.fetchMissions(companyId: newCompany.id)) ?? []
                questChain = (try? await api.fetchQuestChain(companyId: newCompany.id)) ?? []
                subscription = try? await api.initSubscription(companyId: newCompany.id)
                checkDailyChest()
                hasCompletedOnboarding = true
                onboardingReady = true
                showQuestChainOnLaunch = true
                isLoading = false
                startNotificationPolling()
                // #region agent log
                APIClient.debugLog("createNewCompany SUCCESS", data: ["companyId": newCompany.id], hypothesis: "H2", location: "AppState.createNewCompany")
                // #endregion
                return
            } catch {
                // #region agent log
                APIClient.debugLog("createNewCompany FAIL", data: ["attempt": attempt, "error": "\(error)"], hypothesis: "H2", location: "AppState.createNewCompany")
                // #endregion
                if attempt == 3 {
                    isLoading = false
                    errorMessage = Self.serverUnreachableMessage(for: error)
                }
            }
        }
    }

    private func pollOnboardingMissions(companyId: String) async {
        let agentOrder = ["researcher", "builder", "marketer"]
        var completedAgents: Set<String> = []

        for _ in 0..<120 {
            try? await Task.sleep(nanoseconds: 500_000_000)
            missions = (try? await api.fetchMissions(companyId: companyId)) ?? missions

            for agent in agentOrder {
                let agentMissions = missions.filter { $0.agentType == agent }
                if agentMissions.contains(where: { $0.status == "completed" || $0.status == "failed" }) {
                    if !completedAgents.contains(agent) {
                        completedAgents.insert(agent)
                        onboardingAgentStatus[agent] = .done
                        addActivityLog("Agent \(agent) a termine sa tache")
                        if let m = agentMissions.first(where: { $0.status == "completed" }) {
                            justCompletedAgentTypes.insert(agent)
                            NotificationManager.shared.scheduleMissionComplete(agentType: agent, missionType: m.missionType)
                        }

                        if let next = agentOrder.first(where: { !completedAgents.contains($0) && onboardingAgentStatus[$0] == .pending }) {
                            onboardingAgentStatus[next] = .running
                        }
                    }
                } else if agentMissions.contains(where: { $0.status == "running" || $0.status == "pending" }) {
                    if onboardingAgentStatus[agent] == .pending {
                        onboardingAgentStatus[agent] = .running
                    }
                }
            }

            if completedAgents.count >= 1 && !onboardingReady {
                onboardingReady = true
            }

            if completedAgents.count == agentOrder.count {
                company = try? await api.fetchCompany(id: companyId)
                await fetchQuestChain()
                return
            }
        }

        onboardingReady = true
    }

    func refreshCompany() async {
        guard let id = company?.id else { return }
        do {
            company = try await api.fetchCompany(id: id)
            missions = try await api.fetchMissions(companyId: id)
            await fetchQuestChain()
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    // MARK: - Quest Chain

    func fetchQuestChain() async {
        guard let companyId = company?.id else { return }
        do {
            let chain = try await api.fetchQuestChain(companyId: companyId)
            if !chain.isEmpty {
                questChain = chain
            }
        } catch {
            print("[QuestChain] fetch error: \(error.localizedDescription)")
        }
    }

    func startQuestStep(stepNumber: Int) async {
        guard let companyId = company?.id else { return }
        isLoading = true
        defer { isLoading = false }
        do {
            let mission = try await api.startQuestStep(companyId: companyId, stepNumber: stepNumber)
            taskQueue.append(mission)
            taskQueue.sort { ($0.queueOrder ?? 999) < ($1.queueOrder ?? 999) }
            AnalyticsTracker.track("mission_queued", properties: [
                "mission_type": mission.missionType,
                "source": "quest_chain",
                "step": "\(stepNumber)",
            ])
            addActivityLog("Quest step \(stepNumber) ajoutée à la file")
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    var currentQuestStep: QuestStep? {
        questChain.first { $0.isAvailable }
    }

    func questStepForBuilding(agentType: String) -> QuestStep? {
        let types = Set(VillageMap.polisiaAgentTypes(for: agentType))
        return questChain.first { types.contains($0.agentType) && ($0.isAvailable || $0.isRunning) }
    }

    func lockedQuestSteps(agentType: String) -> [QuestStep] {
        let types = Set(VillageMap.polisiaAgentTypes(for: agentType))
        return questChain.filter { types.contains($0.agentType) && $0.isLocked }
    }

    func completedQuestSteps(agentType: String) -> [QuestStep] {
        let types = Set(VillageMap.polisiaAgentTypes(for: agentType))
        return questChain.filter { types.contains($0.agentType) && $0.isCompleted }
    }

    func allQuestStepsForBuilding(agentType: String) -> [QuestStep] {
        let types = Set(VillageMap.polisiaAgentTypes(for: agentType))
        return questChain.filter { types.contains($0.agentType) }
    }

    func prerequisiteNames(for step: QuestStep) -> [String] {
        let bt = company?.businessType ?? .ecommerce
        let prereqNumbers = BusinessType.dependencyGraph(from: questChain)[step.stepNumber] ?? []
        return questChain
            .filter { prereqNumbers.contains($0.stepNumber) && !$0.isCompleted }
            .map { "Etape \($0.stepNumber): \($0.title)" }
    }

    func startMission(type: String) async -> Mission? {
        guard let companyId = company?.id else { return nil }
        isLoading = true
        defer { isLoading = false }
        do {
            let mission = try await api.startMission(companyId: companyId, missionType: type)
            taskQueue.append(mission)
            taskQueue.sort { ($0.queueOrder ?? 999) < ($1.queueOrder ?? 999) }
            AnalyticsTracker.track("mission_queued", properties: [
                "mission_type": type,
                "source": "catalog",
            ])
            completeQuest("first_mission")
            addActivityLog("Mission \(type) ajoutée à la file")
            return mission
        } catch {
            errorMessage = error.localizedDescription
            return nil
        }
    }

    private func pollUntilComplete(missionId: String) async {
        // If mission stays pending for 30s, the runner likely died — call startQuestStep again
        // to trigger the stuck-mission re-fire logic on the backend.
        var pendingTickCount = 0
        // Poll up to 120s (240 × 0.5s) — LLM missions can take 30-90s
        for _ in 0..<240 {
            try? await Task.sleep(nanoseconds: 500_000_000)
            if let updated = try? await api.fetchMission(id: missionId) {
                if let idx = missions.firstIndex(where: { $0.id == missionId }) {
                    missions[idx] = updated
                }
                if updated.status == "pending" {
                    pendingTickCount += 1
                }
                if updated.status == "completed" {
                    // #region agent log
                    let delivLen = updated.deliverable?.count ?? -1
                    let delivPreview = updated.deliverable?.prefix(80) ?? "NIL"
                    print("[DEBUG-H1] pollUntilComplete: mission completed. deliverable len=\(delivLen) preview='\(delivPreview)'")
                    // #endregion
                    justCompletedAgentTypes.insert(updated.agentType)
                    pendingMissionCompletions.append((updated.agentType, updated.missionType))
                    lootToPresent = updated
                    NotificationManager.shared.scheduleMissionComplete(
                        agentType: updated.agentType,
                        missionType: updated.missionType
                    )
                    NotificationManager.shared.scheduleReengagementReminder()
                    AnalyticsTracker.track("mission_completed", properties: [
                        "mission_type": updated.missionType,
                        "quality": updated.qualityScore.map { String(format: "%.0f", $0) } ?? "n/a",
                    ])
                    return
                }
                if updated.status == "failed" {
                    return
                }
            }
        }
        // Polling timed out — do a final refresh so NPC dialogue reflects reality
        // #region agent log
        print("[DEBUG-H3] pollUntilComplete: TIMEOUT after 120s — doing final refresh")
        // #endregion
        if let companyId = company?.id {
            missions = (try? await api.fetchMissions(companyId: companyId)) ?? missions
            questChain = (try? await api.fetchQuestChain(companyId: companyId)) ?? questChain
            // Present loot if the mission completed during the timeout gap
            if let finalMission = missions.first(where: { $0.id == missionId }),
               finalMission.status == "completed",
               finalMission.deliverable != nil {
                // #region agent log
                let fLen = finalMission.deliverable?.count ?? -1
                print("[DEBUG-H3] pollUntilComplete: timeout fallback found completed mission. deliverable len=\(fLen)")
                // #endregion
                justCompletedAgentTypes.insert(finalMission.agentType)
                lootToPresent = finalMission
            } else if let finalMission = missions.first(where: { $0.id == missionId }) {
                // #region agent log
                let fbStatus = finalMission.status
                let fbDeliverable = finalMission.deliverable.map { String($0.prefix(40)) } ?? "NIL"
                print("[DEBUG-H3] pollUntilComplete: timeout fallback — status=\(fbStatus) deliverable=\(fbDeliverable)")
                // #endregion
            }
        }
    }

    func clearJustCompleted(agentType: String) {
        justCompletedAgentTypes.remove(agentType)
        pendingMissionCompletions.removeAll { $0.agentType == agentType }
    }

    func missionForLoot(agentType: String) -> Mission? {
        missions.first {
            $0.agentType == agentType && $0.status == "completed" && $0.deliverable != nil
        }
    }

    var questChainProgress: (completed: Int, total: Int) {
        let total = questChain.count
        let completed = questChain.filter(\.isCompleted).count
        return (completed, total)
    }

    var xpForNextLevel: Int {
        let lvl = company?.level ?? 1
        return lvl * lvl * 100
    }

    // MARK: - Sage Chat

    func loadSageHistory() {
        guard let companyId = company?.id else { return }
        let key = "rpg_sage_history_\(companyId)"
        guard let data = UserDefaults.standard.data(forKey: key),
              let decoded = try? JSONDecoder().decode([SageMessage].self, from: data),
              !decoded.isEmpty else { return }
        sageMessages = decoded
    }

    private func saveSageHistory() {
        guard let companyId = company?.id else { return }
        let key = "rpg_sage_history_\(companyId)"
        let trimmed = Array(sageMessages.suffix(40))
        if let data = try? JSONEncoder().encode(trimmed) {
            UserDefaults.standard.set(data, forKey: key)
        }
    }

    func dismissSageDailyBrief() {
        sageDailyBrief = nil
        UserDefaults.standard.removeObject(forKey: sageBriefKey)
    }

    func sendSageMessage(_ text: String) async {
        guard let companyId = company?.id else { return }

        let userMsg = SageMessage(role: "user", content: text, timestamp: Date())
        sageMessages.append(userMsg)
        isSageLoading = true

        let history = sageMessages.dropLast().map { msg -> [String: String] in
            ["role": msg.role, "content": msg.content]
        }

        do {
            let reply = try await api.sendSageMessage(
                companyId: companyId,
                message: text,
                history: Array(history)
            )
            let assistantMsg = SageMessage(role: "assistant", content: reply.reply, timestamp: Date())
            sageMessages.append(assistantMsg)
            // If Sage queued a task, refresh the task queue
            if reply.createdTaskId != nil {
                await fetchTaskQueue()
            }
        } catch {
            let errorMsg = SageMessage(
                role: "assistant",
                content: "Le Sage reflechit... Reessaie dans un instant.",
                timestamp: Date()
            )
            sageMessages.append(errorMsg)
        }

        saveSageHistory()
        isSageLoading = false
    }

    // MARK: - Activity Feed (from backend)

    func fetchActivityFeed() async {
        guard let companyId = company?.id else { return }
        do {
            agentActivityFeed = try await api.fetchActivityFeed(companyId: companyId)
        } catch {
            print("[ActivityFeed] fetch error: \(error.localizedDescription)")
        }
    }

    // MARK: - Activity Log (local)

    func addActivityLog(_ message: String) {
        let entry = ActivityLogEntry(
            timestamp: Date(),
            message: message
        )
        activityLog.insert(entry, at: 0)
        if activityLog.count > 100 { activityLog.removeLast() }
    }

    // MARK: - Daily Chest

    func claimDailyReward() async {
        guard dailyChestAvailable, let companyId = company?.id else { return }
        do {
            let reward = try await api.claimDailyReward(companyId: companyId)
            dailyChestAvailable = false
            dailyStreak = reward.streak
            UserDefaults.standard.set(Date().timeIntervalSince1970, forKey: lastDailyKey)
            UserDefaults.standard.set(dailyStreak, forKey: streakKey)
            addActivityLog("Coffre quotidien : +\(reward.creditsAwarded) credits (streak \(reward.streak)j)")
            await refreshCompany()
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    private func checkDailyChest() {
        let lastClaim = UserDefaults.standard.double(forKey: lastDailyKey)
        if lastClaim == 0 {
            dailyChestAvailable = true
            return
        }
        let lastDate = Date(timeIntervalSince1970: lastClaim)
        dailyChestAvailable = !Calendar.current.isDateInToday(lastDate)
    }

    // MARK: - Quest Progress

    static let guidedQuests: [(id: String, title: String, description: String, reward: Int)] = [
        ("talk_guide", "Parle au Guide", "Trouve le Guide au centre du village et parle-lui.", 5),
        ("first_mission", "Lance ta premiere quete", "Va a un batiment et lance une quete.", 10),
        ("first_deliverable", "Recupere ton livrable", "Complete une quete et recupere le resultat.", 15),
        ("upgrade_building", "Ameliore un batiment", "Ameliore la Forge ou le Marche au niveau 2.", 20),
        ("research_mission", "Lance une recherche", "Confie une mission de recherche au Labo.", 10),
    ]

    func completeQuest(_ questId: String) {
        guard questProgress[questId] != true else { return }
        questProgress[questId] = true
        saveQuestProgress()
        addActivityLog("Quete terminee : \(questId)")
    }

    func isQuestCompleted(_ questId: String) -> Bool {
        questProgress[questId] == true
    }

    var currentQuestIndex: Int {
        if !questChain.isEmpty {
            return questChain.firstIndex(where: { $0.isAvailable || $0.isRunning }) ?? questChain.count
        }
        for (i, quest) in Self.guidedQuests.enumerated() {
            if questProgress[quest.id] != true { return i }
        }
        return Self.guidedQuests.count
    }

    private func loadLocalState() {
        dailyStreak = UserDefaults.standard.integer(forKey: streakKey)
        if let data = UserDefaults.standard.dictionary(forKey: questKey) as? [String: Bool] {
            questProgress = data
        }
    }

    private func saveQuestProgress() {
        UserDefaults.standard.set(questProgress, forKey: questKey)
    }

    // MARK: - Building Upgrade

    func upgradeBuilding(buildingId: String) async -> Bool {
        guard let companyId = company?.id else { return false }
        isLoading = true
        defer { isLoading = false }
        do {
            try await api.upgradeBuilding(companyId: companyId, buildingId: buildingId)
            await refreshCompany()
            completeQuest("upgrade_building")
            addActivityLog("Batiment ameliore !")
            return true
        } catch {
            errorMessage = error.localizedDescription
            return false
        }
    }

    private static func serverUnreachableMessage(for error: Error) -> String {
        let host = APIClient.shared.baseURL
        if let urlErr = error as? URLError {
            switch urlErr.code {
            case .timedOut:
                return "Timeout — le serveur met trop longtemps à répondre (Render cold start ?). Réessaie dans 30s.\n\nURL : \(host)"
            case .notConnectedToInternet, .networkConnectionLost:
                return "Pas de connexion internet."
            default:
                return "Serveur injoignable (\(urlErr.code.rawValue)).\nURL : \(host)"
            }
        }
        if let apiErr = error as? APIError, case .http(let code, let body) = apiErr {
            return "Erreur HTTP \(code)\n\(body.prefix(200))"
        }
        return "Erreur : \(error.localizedDescription)"
    }
}

struct ActivityLogEntry: Identifiable {
    let id = UUID()
    let timestamp: Date
    let message: String
}
