import Foundation

enum BusinessType: String, Codable, CaseIterable {
    case ecommerce
    case app
    case saas

    var displayName: String {
        switch self {
        case .ecommerce: return "E-COMMERCE"
        case .app: return "APP"
        case .saas: return "SAAS"
        }
    }

    var subtitle: String {
        switch self {
        case .ecommerce: return "Vends des produits en ligne"
        case .app: return "Lance ton application"
        case .saas: return "Cree ton logiciel"
        }
    }

    var questChainTitle: String {
        switch self {
        case .ecommerce: return "LANCEMENT E-COMMERCE"
        case .app: return "LANCEMENT APP"
        case .saas: return "LANCEMENT SAAS"
        }
    }

    var questChainSubtitle: String {
        switch self {
        case .ecommerce: return "Complete chaque etape pour lancer ta marque"
        case .app: return "Complete chaque etape pour lancer ton app"
        case .saas: return "Complete chaque etape pour lancer ton SaaS"
        }
    }

    var icon: String {
        switch self {
        case .ecommerce: return "cart.fill"
        case .app: return "iphone"
        case .saas: return "cloud.fill"
        }
    }

    var dependencyGraph: [Int: [Int]] {
        switch self {
        case .ecommerce:
            return [
                1: [], 2: [1], 3: [1], 4: [3], 5: [3, 4],
                6: [5], 7: [5], 8: [6, 7]
            ]
        case .app:
            return [
                1: [], 2: [1], 3: [2], 4: [2, 3], 5: [4],
                6: [4], 7: [5, 6]
            ]
        case .saas:
            return [
                1: [], 2: [1], 3: [1], 4: [3], 5: [3, 4],
                6: [5], 7: [5], 8: [6, 7]
            ]
        }
    }
}

struct User: Codable, Identifiable {
    let id: String
    let deviceId: String
    let createdAt: String

    enum CodingKeys: String, CodingKey {
        case id
        case deviceId = "device_id"
        case createdAt = "created_at"
    }
}

struct Building: Codable, Identifiable {
    let id: String
    let agentType: String
    let level: Int

    enum CodingKeys: String, CodingKey {
        case id
        case agentType = "agent_type"
        case level
    }

    var displayName: String {
        switch agentType {
        case "orchestrator": return "QG"
        case "builder": return "Site Web"
        case "marketer": return "Ads"
        case "finance": return "Paiements"
        case "researcher", "content", "support", "outreach": return "QG"
        default: return agentType
        }
    }

    var symbol: String {
        switch agentType {
        case "builder": return "hammer.fill"
        case "marketer": return "megaphone.fill"
        case "researcher": return "book.fill"
        case "orchestrator": return "crown.fill"
        case "outreach": return "envelope.fill"
        case "support": return "bubble.left.fill"
        case "finance": return "banknote.fill"
        case "content": return "paintbrush.fill"
        default: return "building.2.fill"
        }
    }
}

struct Wallet: Codable {
    let creditsBalance: Int
    let creditsCap: Int
    let dailyFreeCredits: Int

    enum CodingKeys: String, CodingKey {
        case creditsBalance = "credits_balance"
        case creditsCap = "credits_cap"
        case dailyFreeCredits = "daily_free_credits"
    }
}

struct Company: Codable, Identifiable {
    let id: String
    let name: String
    let slug: String?
    let missionStatement: String
    let productDescription: String
    let targetAudience: String
    let businessType: BusinessType
    let level: Int
    let xp: Int
    let buildings: [Building]
    let renderUrl: String?
    let siteUrl: String?
    let stripeConnectStatus: String?
    let dailyAdsBudgetCents: Int?
    let adsWalletBalanceCents: Int?
    let wallet: Wallet

    enum CodingKeys: String, CodingKey {
        case id, name, slug, level, xp, buildings, wallet
        case missionStatement = "mission_statement"
        case productDescription = "product_description"
        case targetAudience = "target_audience"
        case businessType = "business_type"
        case renderUrl = "render_url"
        case siteUrl = "site_url"
        case stripeConnectStatus = "stripe_connect_status"
        case dailyAdsBudgetCents = "daily_ads_budget_cents"
        case adsWalletBalanceCents = "ads_wallet_balance_cents"
    }
}

struct MissionLogEntry: Codable, Identifiable {
    var id: String { "\(step)_\(createdAt)" }
    let step: String
    let message: String
    let createdAt: String

    enum CodingKeys: String, CodingKey {
        case step, message
        case createdAt = "created_at"
    }
}

struct ActivityFeedEntry: Codable, Identifiable {
    var id: String { "\(missionId)_\(step)_\(createdAt)" }
    let missionId: String
    let agentType: String
    let missionType: String
    let missionStatus: String
    let step: String
    let message: String
    let createdAt: String

    enum CodingKeys: String, CodingKey {
        case step, message
        case missionId = "mission_id"
        case agentType = "agent_type"
        case missionType = "mission_type"
        case missionStatus = "mission_status"
        case createdAt = "created_at"
    }
}

struct MissionCatalogItem: Codable, Identifiable {
    var id: String { missionType }
    let missionType: String
    let agentType: String
    let title: String
    let description: String
    let creditsCost: Int
    let estimatedMinutes: Int
    let outputFormat: String

    enum CodingKeys: String, CodingKey {
        case missionType = "mission_type"
        case agentType = "agent_type"
        case title, description
        case creditsCost = "credits_cost"
        case estimatedMinutes = "estimated_minutes"
        case outputFormat = "output_format"
    }
}

struct QuestStep: Codable, Identifiable {
    let id: String
    let stepNumber: Int
    let missionType: String
    let title: String
    let description: String
    let agentType: String
    let status: String
    let missionId: String?
    let buildingName: String
    let unlockedAt: String?
    let completedAt: String?

    enum CodingKeys: String, CodingKey {
        case id, title, description, status
        case stepNumber = "step_number"
        case missionType = "mission_type"
        case agentType = "agent_type"
        case missionId = "mission_id"
        case buildingName = "building_name"
        case unlockedAt = "unlocked_at"
        case completedAt = "completed_at"
    }

    var isLocked: Bool { status == "locked" }
    var isAvailable: Bool { status == "available" }
    var isRunning: Bool { status == "running" }
    var isCompleted: Bool { status == "completed" }
}

struct SageMessage: Identifiable {
    let id = UUID()
    let role: String  // "user" or "assistant"
    let content: String
    let timestamp: Date

    var isUser: Bool { role == "user" }
}

struct SageReply: Codable {
    let reply: String
}

struct Mission: Codable, Identifiable {
    let id: String
    let companyId: String
    let agentType: String
    let missionType: String
    let status: String
    let creditsCost: Int
    let xpReward: Int
    let deliverableFormat: String?
    let deliverable: String?
    let qualityScore: Double?
    let errorMessage: String?
    let startedAt: String?
    let completedAt: String?
    let createdAt: String?

    enum CodingKeys: String, CodingKey {
        case id, status, deliverable
        case companyId = "company_id"
        case agentType = "agent_type"
        case missionType = "mission_type"
        case creditsCost = "credits_cost"
        case xpReward = "xp_reward"
        case deliverableFormat = "deliverable_format"
        case qualityScore = "quality_score"
        case errorMessage = "error_message"
        case startedAt = "started_at"
        case completedAt = "completed_at"
        case createdAt = "created_at"
    }
}
