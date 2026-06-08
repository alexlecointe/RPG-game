import Foundation

enum APIError: LocalizedError {
    case invalidURL
    case http(Int, String)

    var errorDescription: String? {
        switch self {
        case .invalidURL: return "URL invalide"
        case .http(let code, let body): return "HTTP \(code): \(body)"
        }
    }
}

struct DailyRewardResponse: Codable {
    let creditsAwarded: Int
    let streak: Int
    let bonusActive: Bool

    enum CodingKeys: String, CodingKey {
        case creditsAwarded = "credits_awarded"
        case streak
        case bonusActive = "bonus_active"
    }
}

struct StripeStatusResponse: Codable {
    let status: String
    let chargesEnabled: Bool?
    let payoutsEnabled: Bool?

    enum CodingKeys: String, CodingKey {
        case status
        case chargesEnabled = "charges_enabled"
        case payoutsEnabled = "payouts_enabled"
    }
}

struct StripeOnboardingResponse: Codable {
    let url: String
}

struct BetaFeedbackResponse: Codable {
    let id: String
    let missionType: String
    let usedDeliverable: Bool
    let rating: Int

    enum CodingKeys: String, CodingKey {
        case id, rating
        case missionType = "mission_type"
        case usedDeliverable = "used_deliverable"
    }
}

final class APIClient {
    static let shared = APIClient()

    private static let baseURLKey = "rpg_api_base_url"

    private static let productionURL = "https://rpg-agent-api.onrender.com/api/v1"

    #if targetEnvironment(simulator)
    private static let localURL = "http://127.0.0.1:8080/api/v1"
    #else
    private static let localURL = "http://192.168.1.15:8080/api/v1"
    #endif

    var baseURL: String {
        if let custom = UserDefaults.standard.string(forKey: Self.baseURLKey), !custom.isEmpty {
            return custom
        }
        return Self.productionURL
    }

    var apiKey = "rpg-prod-key-2026"

    private lazy var session: URLSession = {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 15
        config.timeoutIntervalForResource = 30
        return URLSession(configuration: config)
    }()

    /// Session longue durée pour les appels LLM (quêtes, missions, Sage)
    private lazy var longSession: URLSession = {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 120
        config.timeoutIntervalForResource = 180
        return URLSession(configuration: config)
    }()

    private let decoder = JSONDecoder()
    private let encoder = JSONEncoder()

    // #region agent log
    private static let debugLogPath = "/tmp/debug-44d3d4.log"
    static func debugLog(_ message: String, data: [String: Any] = [:], hypothesis: String = "", location: String = "") {
        let ts = Int(Date().timeIntervalSince1970 * 1000)
        var payload: [String: Any] = ["sessionId": "44d3d4", "timestamp": ts, "location": location, "message": message, "hypothesisId": hypothesis]
        if !data.isEmpty { payload["data"] = data }
        if let json = try? JSONSerialization.data(withJSONObject: payload), var line = String(data: json, encoding: .utf8) {
            line += "\n"
            if let fh = FileHandle(forWritingAtPath: debugLogPath) {
                fh.seekToEndOfFile(); fh.write(line.data(using: .utf8)!); fh.closeFile()
            } else {
                FileManager.default.createFile(atPath: debugLogPath, contents: line.data(using: .utf8))
            }
        }
    }
    // #endregion

    func registerUser(deviceId: String) async throws -> User {
        try await post("/users", body: ["device_id": deviceId])
    }

    func createCompany(
        userId: String,
        name: String,
        missionStatement: String,
        productDescription: String = "",
        targetAudience: String = "",
        businessType: BusinessType = .ecommerce
    ) async throws -> Company {
        try await post(
            "/companies/\(userId)",
            body: [
                "name": name,
                "mission_statement": missionStatement,
                "product_description": productDescription,
                "target_audience": targetAudience,
                "business_type": businessType.rawValue,
            ]
        )
    }

    func fetchCompany(id: String) async throws -> Company {
        try await get("/companies/\(id)")
    }

    func fetchCatalog(agentType: String? = nil) async throws -> [MissionCatalogItem] {
        var path = "/catalog/missions"
        if let agentType { path += "?agent_type=\(agentType)" }
        return try await get(path)
    }

    func fetchMissions(companyId: String) async throws -> [Mission] {
        try await get("/companies/\(companyId)/missions")
    }

    func startMission(companyId: String, missionType: String) async throws -> Mission {
        try await post("/companies/\(companyId)/missions", body: ["mission_type": missionType])
    }

    func fetchMission(id: String) async throws -> Mission {
        try await get("/missions/\(id)")
    }

    // MARK: - Task Queue (Polsia)

    func fetchTaskQueue(companyId: String) async throws -> [Mission] {
        try await get("/companies/\(companyId)/tasks/queue")
    }

    func createFreeformTask(companyId: String, title: String, description: String = "", agentType: String? = nil) async throws -> Mission {
        var body: [String: Any] = ["title": title, "description": description]
        if let at = agentType { body["agent_type"] = at }
        return try await postJSON("/companies/\(companyId)/tasks", body: body)
    }

    func rejectTask(missionId: String, reason: String = "user_cancelled") async throws {
        let _: Mission = try await postJSON("/missions/\(missionId)/reject", body: ["reason": reason])
    }

    func moveTaskToTop(missionId: String) async throws -> Mission {
        try await postEmpty("/missions/\(missionId)/move-to-top")
    }

    func reorderTask(missionId: String, position: Int) async throws -> Mission {
        try await patchJSON("/missions/\(missionId)/order", body: ["position": position])
    }

    func editTask(missionId: String, title: String? = nil, description: String? = nil) async throws -> Mission {
        var body: [String: Any] = [:]
        if let t = title { body["title"] = t }
        if let d = description { body["description"] = d }
        return try await patchJSON("/missions/\(missionId)", body: body)
    }

    func routeTask(companyId: String, title: String, description: String = "") async throws -> String {
        let encoded = title.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? title
        let descEncoded = description.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? ""
        let resp: [String: String] = try await get("/companies/\(companyId)/tasks/route?title=\(encoded)&description=\(descEncoded)")
        return resp["recommended_agent"] ?? "orchestrator"
    }

    /// Manually trigger execution of a PENDING task (Polsia run_link).
    func executeTask(missionId: String) async throws -> Mission {
        try await postEmpty("/missions/\(missionId)/execute")
    }

    func fetchMissionLogs(missionId: String) async throws -> [MissionLogEntry] {
        try await get("/missions/\(missionId)/logs")
    }

    func upgradeBuilding(companyId: String, buildingId: String) async throws {
        let _: Building = try await post("/companies/\(companyId)/buildings/\(buildingId)/upgrade", body: [:])
    }

    func claimDailyReward(companyId: String) async throws -> DailyRewardResponse {
        try await post("/companies/\(companyId)/daily-reward", body: [:])
    }

    func fetchQuestChain(companyId: String) async throws -> [QuestStep] {
        try await get("/companies/\(companyId)/quest-chain")
    }

    func fetchActivityFeed(companyId: String, limit: Int = 50) async throws -> [ActivityFeedEntry] {
        try await get("/companies/\(companyId)/activity-feed?limit=\(limit)")
    }

    func sendSageMessage(companyId: String, message: String, history: [[String: String]]) async throws -> SageReply {
        let body: [String: Any] = [
            "message": message,
            "history": history,
        ]
        return try await postJSON("/companies/\(companyId)/sage", body: body)
    }

    func startQuestStep(companyId: String, stepNumber: Int) async throws -> Mission {
        try await postEmpty("/companies/\(companyId)/quest-chain/\(stepNumber)/start")
    }

    func fetchStripeStatus(companyId: String) async throws -> StripeStatusResponse {
        try await get("/companies/\(companyId)/stripe/status")
    }

    func startStripeOnboarding(companyId: String) async throws -> String {
        let resp: StripeOnboardingResponse = try await postEmpty("/companies/\(companyId)/stripe/onboarding")
        return resp.url
    }

    func setAdsBudget(companyId: String, dailyBudgetCents: Int) async throws {
        let _: [String: Int] = try await postJSON(
            "/companies/\(companyId)/ads/budget",
            body: ["daily_budget_cents": dailyBudgetCents]
        )
    }

    func chargeAdsWallet(companyId: String) async throws -> [String: Int] {
        try await postEmpty("/companies/\(companyId)/ads/wallet/charge")
    }

    func fetchAdsSummary(companyId: String) async throws -> AdsSummary {
        try await get("/companies/\(companyId)/ads/summary")
    }

    func fetchAdsCampaigns(companyId: String) async throws -> [AdCampaign] {
        try await get("/companies/\(companyId)/ads/campaigns")
    }

    func fetchAdsCreatives(companyId: String) async throws -> [AdCreative] {
        try await get("/companies/\(companyId)/ads/creatives")
    }

    func pauseAdsCampaign(companyId: String, campaignId: String) async throws {
        let _: [String: String] = try await postEmpty("/companies/\(companyId)/ads/campaigns/\(campaignId)/pause")
    }

    func resumeAdsCampaign(companyId: String, campaignId: String) async throws {
        let _: [String: String] = try await postEmpty("/companies/\(companyId)/ads/campaigns/\(campaignId)/resume")
    }

    func applyScaleCampaign(companyId: String, campaignId: String) async throws {
        let _: [String: String] = try await postEmpty("/companies/\(companyId)/ads/campaigns/\(campaignId)/apply-scale")
    }

    func applySplitWinner(companyId: String, campaignId: String) async throws {
        let _: [String: String] = try await postEmpty("/companies/\(companyId)/ads/campaigns/\(campaignId)/apply-split-winner")
    }

    func fetchWalletTransactions(companyId: String, limit: Int = 20) async throws -> [WalletTransaction] {
        try await get("/companies/\(companyId)/ads/transactions?limit=\(limit)")
    }


    func pauseAllAdsCampaigns(companyId: String, campaigns: [AdCampaign]) async throws {
        for campaign in campaigns where campaign.status == "active" {
            try await pauseAdsCampaign(companyId: companyId, campaignId: campaign.id)
        }
    }

    func resumeAllAdsCampaigns(companyId: String, campaigns: [AdCampaign]) async throws {
        for campaign in campaigns where campaign.status != "active" {
            try await resumeAdsCampaign(companyId: companyId, campaignId: campaign.id)
        }
    }

    // MARK: - Auto-pilot

    func toggleAutoPilot(companyId: String, enabled: Bool) async throws -> Company {
        return try await postJSON("/companies/\(companyId)/auto-pilot", body: ["enabled": enabled])
    }

    // MARK: - Edit Task

    func editTask(missionId: String, title: String, description: String) async throws -> Mission {
        return try await patchJSON(
            "/missions/\(missionId)",
            body: ["title": title, "description": description]
        )
    }

    // MARK: - Notifications

    func fetchNotifications(companyId: String, unreadOnly: Bool = false) async throws -> [CompanyNotification] {
        let path = "/companies/\(companyId)/notifications?limit=30" + (unreadOnly ? "&unread_only=true" : "")
        return try await get(path)
    }

    func markNotificationsRead(companyId: String) async throws {
        let _: [String: String] = try await postEmpty("/companies/\(companyId)/notifications/read-all")
    }

    // MARK: - Recurring Missions

    func fetchRecurringMissions(companyId: String) async throws -> [RecurringMission] {
        try await get("/companies/\(companyId)/recurring-missions")
    }

    func createRecurringMission(companyId: String, body: RecurringMissionCreate) async throws -> RecurringMission {
        let payload: [String: Any?] = [
            "mission_type": body.missionType,
            "frequency": body.frequency,
            "day_of_week": body.dayOfWeek,
            "day_of_month": body.dayOfMonth,
            "hour_utc": body.hourUtc,
        ]
        let clean = payload.compactMapValues { $0 }
        return try await postJSON("/companies/\(companyId)/recurring-missions", body: clean)
    }

    func deleteRecurringMission(recurringId: String) async throws {
        guard let url = URL(string: baseURL + "/recurring-missions/\(recurringId)") else { throw APIError.invalidURL }
        var request = URLRequest(url: url)
        request.httpMethod = "DELETE"
        request.setValue(apiKey, forHTTPHeaderField: "X-API-Key")
        let (data, response) = try await session.data(for: request)
        try validate(response: response, data: data)
    }

    // MARK: - Billing (Polsia-like)

    func fetchSubscription(companyId: String) async throws -> SubscriptionInfo {
        try await get("/companies/\(companyId)/billing/subscription")
    }

    func fetchBillingPlans(companyId: String) async throws -> BillingPlansResponse {
        try await get("/companies/\(companyId)/billing/plans")
    }

    func createCheckoutSession(
        companyId: String,
        type: String,
        planOrPackId: String,
        successUrl: String = "rpgagent://billing/success",
        cancelUrl: String = "rpgagent://billing/cancel"
    ) async throws -> String {
        let resp: CheckoutSessionResponse = try await postJSON(
            "/companies/\(companyId)/billing/checkout",
            body: [
                "type": type,
                "plan_or_pack_id": planOrPackId,
                "success_url": successUrl,
                "cancel_url": cancelUrl,
            ]
        )
        return resp.checkoutUrl
    }

    func initSubscription(companyId: String) async throws -> SubscriptionInfo {
        try await postEmpty("/companies/\(companyId)/billing/init")
    }

    // MARK: - Orders (Système B)

    func fetchOrders(companyId: String, limit: Int = 50) async throws -> OrdersResponse {
        try await get("/companies/\(companyId)/orders?limit=\(limit)")
    }

    // MARK: - God Mode

    func fetchGodModePlans() async throws -> GodModePlansResponse {
        // company_id not strictly needed but endpoint exists per company
        try await get("/companies/_/billing/god-mode/plans")
    }

    func fetchGodModePlansFor(companyId: String) async throws -> GodModePlansResponse {
        try await get("/companies/\(companyId)/billing/god-mode/plans")
    }

    func createGodModeCheckout(
        companyId: String,
        godPlanId: String,
        successUrl: String = "rpgagent://billing/god-mode/success",
        cancelUrl: String = "rpgagent://billing/god-mode/cancel"
    ) async throws -> String {
        let resp: CheckoutSessionResponse = try await postJSON(
            "/companies/\(companyId)/billing/god-mode/checkout",
            body: [
                "god_plan_id": godPlanId,
                "success_url": successUrl,
                "cancel_url": cancelUrl,
            ]
        )
        return resp.checkoutUrl
    }

    func fetchActiveGodMode(companyId: String) async throws -> GodModeActiveResponse {
        try await get("/companies/\(companyId)/billing/god-mode/active")
    }

    func fetchBillingPortalURL(companyId: String) async throws -> String {
        let resp: PortalSessionResponse = try await get("/companies/\(companyId)/billing/portal")
        return resp.portalUrl
    }

    func fetchInvoices(companyId: String) async throws -> InvoicesResponse {
        try await get("/companies/\(companyId)/billing/invoices")
    }

    // MARK: - Products & Payment Links (Système B)

    func fetchProducts(companyId: String) async throws -> StripeProductsResponse {
        try await get("/companies/\(companyId)/products")
    }

    func createPaymentLink(
        companyId: String,
        productName: String,
        amountCents: Int,
        currency: String = "eur"
    ) async throws -> String {
        struct Resp: Codable { let url: String? }
        let resp: Resp = try await postJSON(
            "/companies/\(companyId)/products/payment-link",
            body: ["product_name": productName, "amount_cents": amountCents, "currency": currency] as [String: Any]
        )
        return resp.url ?? ""
    }

    func submitBetaFeedback(
        companyId: String,
        missionId: String,
        missionType: String,
        used: Bool,
        rating: Int,
        comment: String
    ) async throws {
        let _: BetaFeedbackResponse = try await postJSON(
            "/companies/\(companyId)/feedback",
            body: [
                "mission_id": missionId,
                "mission_type": missionType,
                "used_deliverable": used,
                "rating": rating,
                "comment": comment,
            ]
        )
    }

    private func get<T: Decodable>(_ path: String) async throws -> T {
        guard let url = URL(string: baseURL + path) else { throw APIError.invalidURL }
        var request = URLRequest(url: url)
        request.setValue(apiKey, forHTTPHeaderField: "X-API-Key")
        // #region agent log
        APIClient.debugLog("GET request", data: ["url": url.absoluteString], hypothesis: "H2", location: "APIClient.get")
        // #endregion
        let (data, response) = try await session.data(for: request)
        // #region agent log
        let httpCode = (response as? HTTPURLResponse)?.statusCode ?? -1
        APIClient.debugLog("GET response", data: ["url": path, "status": httpCode, "bodyLen": data.count], hypothesis: "H2", location: "APIClient.get")
        // #endregion
        try validate(response: response, data: data)
        do {
            return try decoder.decode(T.self, from: data)
        } catch {
            // #region agent log
            let bodyPreview = String(data: data.prefix(500), encoding: .utf8) ?? "n/a"
            APIClient.debugLog("DECODE FAILED", data: ["path": path, "error": "\(error)", "body": bodyPreview], hypothesis: "H2", location: "APIClient.get.decode")
            // #endregion
            throw error
        }
    }

    private func postEmpty<T: Decodable>(_ path: String) async throws -> T {
        guard let url = URL(string: baseURL + path) else { throw APIError.invalidURL }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(apiKey, forHTTPHeaderField: "X-API-Key")
        let (data, response) = try await longSession.data(for: request)
        try validate(response: response, data: data)
        return try decoder.decode(T.self, from: data)
    }

    private func post<T: Decodable>(_ path: String, body: [String: String]) async throws -> T {
        guard let url = URL(string: baseURL + path) else { throw APIError.invalidURL }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(apiKey, forHTTPHeaderField: "X-API-Key")
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        // #region agent log
        APIClient.debugLog("POST request", data: ["url": url.absoluteString, "bodyKeys": Array(body.keys)], hypothesis: "H2", location: "APIClient.post")
        // #endregion
        let (data, response) = try await session.data(for: request)
        // #region agent log
        let httpCode = (response as? HTTPURLResponse)?.statusCode ?? -1
        APIClient.debugLog("POST response", data: ["path": path, "status": httpCode, "bodyLen": data.count], hypothesis: "H2", location: "APIClient.post")
        // #endregion
        try validate(response: response, data: data)
        do {
            return try decoder.decode(T.self, from: data)
        } catch {
            // #region agent log
            let bodyPreview = String(data: data.prefix(500), encoding: .utf8) ?? "n/a"
            APIClient.debugLog("DECODE FAILED post", data: ["path": path, "error": "\(error)", "body": bodyPreview], hypothesis: "H2", location: "APIClient.post.decode")
            // #endregion
            throw error
        }
    }

    private func postJSON<T: Decodable>(_ path: String, body: [String: Any]) async throws -> T {
        guard let url = URL(string: baseURL + path) else { throw APIError.invalidURL }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(apiKey, forHTTPHeaderField: "X-API-Key")
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        let (data, response) = try await longSession.data(for: request)
        try validate(response: response, data: data)
        return try decoder.decode(T.self, from: data)
    }

    private func patchJSON<T: Decodable>(_ path: String, body: [String: Any]) async throws -> T {
        guard let url = URL(string: baseURL + path) else { throw APIError.invalidURL }
        var request = URLRequest(url: url)
        request.httpMethod = "PATCH"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(apiKey, forHTTPHeaderField: "X-API-Key")
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        let (data, response) = try await longSession.data(for: request)
        try validate(response: response, data: data)
        return try decoder.decode(T.self, from: data)
    }

    private func validate(response: URLResponse, data: Data) throws {
        guard let http = response as? HTTPURLResponse else { return }
        guard (200...299).contains(http.statusCode) else {
            let body = String(data: data, encoding: .utf8) ?? ""
            throw APIError.http(http.statusCode, body)
        }
    }
}
