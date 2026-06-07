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

    #if targetEnvironment(simulator)
    private static let defaultHost = "127.0.0.1"
    #else
    private static let defaultHost = "192.168.1.15"
    #endif

    var baseURL: String {
        if let custom = UserDefaults.standard.string(forKey: Self.baseURLKey), !custom.isEmpty {
            return custom
        }
        return "http://\(Self.defaultHost):8080/api/v1"
    }

    var apiKey = "dev-local-key-change-in-production"

    private lazy var session: URLSession = {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 15
        config.timeoutIntervalForResource = 30
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
        let (data, response) = try await session.data(for: request)
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
        let (data, response) = try await session.data(for: request)
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
