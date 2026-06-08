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
        // 5 steps for all types: QG → Site Web → Paiements → Ads (prep) → Ads (launch)
        // Steps 3 and 4 both unlock from step 2 (parallel)
        // Step 5 requires both 3 and 4
        return [1: [], 2: [1], 3: [2], 4: [2], 5: [3, 4]]
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
    let autoPilot: Bool

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
        case autoPilot = "auto_pilot"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(String.self, forKey: .id)
        name = try c.decode(String.self, forKey: .name)
        slug = try c.decodeIfPresent(String.self, forKey: .slug)
        missionStatement = try c.decode(String.self, forKey: .missionStatement)
        productDescription = try c.decodeIfPresent(String.self, forKey: .productDescription) ?? ""
        targetAudience = try c.decodeIfPresent(String.self, forKey: .targetAudience) ?? ""
        businessType = try c.decodeIfPresent(BusinessType.self, forKey: .businessType) ?? .ecommerce
        level = try c.decode(Int.self, forKey: .level)
        xp = try c.decode(Int.self, forKey: .xp)
        buildings = try c.decodeIfPresent([Building].self, forKey: .buildings) ?? []
        renderUrl = try c.decodeIfPresent(String.self, forKey: .renderUrl)
        siteUrl = try c.decodeIfPresent(String.self, forKey: .siteUrl)
        stripeConnectStatus = try c.decodeIfPresent(String.self, forKey: .stripeConnectStatus)
        dailyAdsBudgetCents = try c.decodeIfPresent(Int.self, forKey: .dailyAdsBudgetCents)
        adsWalletBalanceCents = try c.decodeIfPresent(Int.self, forKey: .adsWalletBalanceCents)
        wallet = try c.decode(Wallet.self, forKey: .wallet)
        autoPilot = try c.decodeIfPresent(Bool.self, forKey: .autoPilot) ?? false
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
    let createdTaskId: String?
    let createdTaskTitle: String?

    enum CodingKeys: String, CodingKey {
        case reply
        case createdTaskId = "created_task_id"
        case createdTaskTitle = "created_task_title"
    }
}

struct Mission: Codable, Identifiable {
    let id: String
    let companyId: String
    let agentType: String
    let missionType: String
    let status: String
    let source: String?
    let title: String?
    let description: String?
    let queueOrder: Int?
    let rejectedReason: String?
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
        case id, status, deliverable, source, title, description
        case companyId = "company_id"
        case agentType = "agent_type"
        case missionType = "mission_type"
        case queueOrder = "queue_order"
        case rejectedReason = "rejected_reason"
        case creditsCost = "credits_cost"
        case xpReward = "xp_reward"
        case deliverableFormat = "deliverable_format"
        case qualityScore = "quality_score"
        case errorMessage = "error_message"
        case startedAt = "started_at"
        case completedAt = "completed_at"
        case createdAt = "created_at"
    }

    var displayTitle: String {
        title ?? missionType.replacingOccurrences(of: "_", with: " ").capitalized
    }

    var isPending: Bool { status == "pending" }
    var isRunning: Bool { status == "running" }
    var isCompleted: Bool { status == "completed" }
    var isFailed: Bool { status == "failed" }
    var isRejected: Bool { status == "rejected" }

    var taskSourceDisplay: String {
        switch source {
        case "ceo_proposal": return "CEO"
        case "agent_generated": return "AGENT"
        case "recurring_task": return "AUTO"
        default: return "USER"
        }
    }

    var taskSourceIcon: String {
        switch source {
        case "ceo_proposal": return "brain.head.profile"
        case "agent_generated": return "gearshape.fill"
        case "recurring_task": return "arrow.clockwise"
        default: return "person.fill"
        }
    }
}

// MARK: - Sage response with task creation

struct SageResponse: Codable {
    let reply: String
    let createdTaskId: String?
    let createdTaskTitle: String?

    enum CodingKeys: String, CodingKey {
        case reply
        case createdTaskId = "created_task_id"
        case createdTaskTitle = "created_task_title"
    }
}

// MARK: - Company Notification

struct CompanyNotification: Codable, Identifiable {
    let id: String
    let type: String
    let title: String
    let message: String
    let read: Bool
    let createdAt: String

    enum CodingKeys: String, CodingKey {
        case id, type, title, message, read
        case createdAt = "created_at"
    }

    var icon: String {
        switch type {
        case "step_completed": return "checkmark.circle.fill"
        case "step_unlocked": return "lock.open.fill"
        case "chain_completed": return "star.fill"
        case "mission_failed": return "xmark.circle.fill"
        case "low_credits": return "bolt.slash.fill"
        default: return "bell.fill"
        }
    }

    var iconColor: String {
        switch type {
        case "step_completed": return "green"
        case "step_unlocked": return "accent"
        case "chain_completed": return "accent"
        case "mission_failed": return "red"
        case "low_credits": return "red"
        default: return "secondary"
        }
    }
}

// MARK: - Recurring Mission

struct RecurringMission: Codable, Identifiable {
    let id: String
    let companyId: String
    let missionType: String
    let frequency: String
    let dayOfWeek: Int?
    let dayOfMonth: Int?
    let hourUtc: Int
    let isActive: Bool
    let lastRunAt: Date?
    let nextRunAt: Date?
    let createdAt: Date

    enum CodingKeys: String, CodingKey {
        case id, frequency
        case companyId = "company_id"
        case missionType = "mission_type"
        case dayOfWeek = "day_of_week"
        case dayOfMonth = "day_of_month"
        case hourUtc = "hour_utc"
        case isActive = "is_active"
        case lastRunAt = "last_run_at"
        case nextRunAt = "next_run_at"
        case createdAt = "created_at"
    }

    var displayTitle: String {
        missionType.replacingOccurrences(of: "_", with: " ").capitalized
    }

    var frequencyLabel: String {
        switch frequency {
        case "daily": return "Quotidien · \(hourUtc)h UTC"
        case "weekly": return "Hebdo · \(dayOfWeek.map { "J\($0)" } ?? "")  \(hourUtc)h UTC"
        case "monthly": return "Mensuel · J\(dayOfMonth ?? 1) · \(hourUtc)h UTC"
        default: return frequency
        }
    }
}

struct RecurringMissionCreate: Codable {
    let missionType: String
    let frequency: String
    let dayOfWeek: Int?
    let dayOfMonth: Int?
    let hourUtc: Int

    enum CodingKeys: String, CodingKey {
        case frequency
        case missionType = "mission_type"
        case dayOfWeek = "day_of_week"
        case dayOfMonth = "day_of_month"
        case hourUtc = "hour_utc"
    }
}

// MARK: - Freeform task creation

struct CreateTaskRequest: Codable {
    let title: String
    let description: String
    let agentType: String?

    enum CodingKeys: String, CodingKey {
        case title, description
        case agentType = "agent_type"
    }
}

// MARK: - Ads Models

struct AdCampaign: Codable, Identifiable {
    let id: String
    let companyId: String
    let name: String
    let status: String
    let dailyBudgetCents: Int
    let spendCents: Int
    let impressions: Int
    let clicks: Int
    let ctr: Double
    let cpcCents: Int
    let metaCampaignId: String?
    let targetingJson: String?
    let objective: String?
    let callToAction: String?
    let purchaseRoas: Double?
    let hoursSinceActivation: Int?
    let reach: Int?
    let frequency: Double?
    let videoViews: Int?
    let videoThruplaysWatched: Int?

    enum CodingKeys: String, CodingKey {
        case id, name, status, impressions, clicks, ctr, reach, frequency
        case companyId = "company_id"
        case dailyBudgetCents = "daily_budget_cents"
        case spendCents = "spend_cents"
        case cpcCents = "cpc_cents"
        case metaCampaignId = "meta_campaign_id"
        case targetingJson = "targeting_json"
        case objective
        case callToAction = "call_to_action"
        case purchaseRoas = "purchase_roas"
        case hoursSinceActivation = "hours_since_activation"
        case videoViews = "video_views"
        case videoThruplaysWatched = "video_thruplay_watched"
    }

    var statusDisplay: String {
        switch status {
        case "active": return "Active"
        case "paused": return "Paused"
        case "blocked": return "Blocked"
        case "draft": return "Draft"
        default: return status.capitalized
        }
    }

    var spendFormatted: String {
        String(format: "$%.2f", Double(spendCents) / 100)
    }

    var cpcFormatted: String {
        String(format: "$%.2f", Double(cpcCents) / 100)
    }

    var ctrFormatted: String {
        String(format: "%.2f%%", ctr)
    }
}

struct AdCreative: Codable, Identifiable {
    let id: String
    let campaignId: String
    let title: String
    let body: String
    let videoUrl: String?
    let thumbnailUrl: String?
    let status: String
    let spendCents: Int
    let impressions: Int
    let clicks: Int
    let ctr: Double

    enum CodingKeys: String, CodingKey {
        case id, title, body, status, impressions, clicks, ctr
        case campaignId = "campaign_id"
        case videoUrl = "video_url"
        case thumbnailUrl = "thumbnail_url"
        case spendCents = "spend_cents"
    }

    var spendFormatted: String {
        String(format: "%.2f€", Double(spendCents) / 100)
    }

    var ctrFormatted: String {
        String(format: "%.1f%%", ctr)
    }
}

struct WalletTransaction: Codable, Identifiable {
    let id: String
    let companyId: String
    let amountCents: Int
    let type: String  // "credit" | "debit" | "fee"
    let note: String
    let createdAt: String

    enum CodingKeys: String, CodingKey {
        case id, note, type
        case companyId = "company_id"
        case amountCents = "amount_cents"
        case createdAt = "created_at"
    }

    var amountFormatted: String {
        let usd = Double(abs(amountCents)) / 100
        let sign = amountCents >= 0 ? "+" : "-"
        return "\(sign)$\(String(format: "%.2f", usd))"
    }

    var isCredit: Bool { amountCents > 0 }

    var dateFormatted: String {
        let iso = ISO8601DateFormatter()
        iso.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        let iso2 = ISO8601DateFormatter()
        if let date = iso.date(from: createdAt) ?? iso2.date(from: createdAt) {
            let df = DateFormatter()
            df.dateStyle = .medium
            df.timeStyle = .short
            return df.string(from: date)
        }
        return createdAt
    }
}

struct AdsSummary: Codable {
    let state: String
    let stateMessage: String?
    let walletBalanceCents: Int
    let dailyBudgetCents: Int
    let totalSpendCents: Int
    let totalImpressions: Int
    let totalClicks: Int
    let ctr: Double
    let cpcCents: Int
    let spendRollup7d: [Int]
    let campaigns: [AdCampaign]
    let creatives: [AdCreative]
    let ownerActionable: Bool
    let actionableMessage: String?

    enum CodingKeys: String, CodingKey {
        case state, campaigns, creatives, ctr
        case stateMessage = "state_message"
        case walletBalanceCents = "wallet_balance_cents"
        case dailyBudgetCents = "daily_budget_cents"
        case totalSpendCents = "total_spend_cents"
        case spendRollup7d = "spend_rollup_7d"
        case totalImpressions = "total_impressions"
        case totalClicks = "total_clicks"
        case cpcCents = "cpc_cents"
        case ownerActionable = "owner_actionable"
        case actionableMessage = "actionable_message"
    }

    var stateDisplay: String {
        switch state {
        case "running": return "Running"
        case "paused": return "Paused"
        case "winding_down": return "Winding Down"
        case "warming_up": return "Learning"
        case "delivery_blocked": return "Blocked"
        case "stale_no_delivery": return "No Delivery"
        case "card_expired": return "Card Expired"
        case "payment_method_missing": return "Payment Missing"
        case "no_campaigns": return "No Campaigns"
        case "draft": return "Draft"
        default: return state.capitalized
        }
    }

    var stateColor: String {
        switch state {
        case "running": return "green"
        case "warming_up": return "orange"
        case "winding_down": return "orange"
        case "delivery_blocked", "stale_no_delivery",
             "card_expired", "payment_method_missing": return "red"
        case "paused": return "gray"
        default: return "gray"
        }
    }

    var walletFormatted: String {
        String(format: "$%.2f", Double(walletBalanceCents) / 100)
    }

    var dailyBudgetFormatted: String {
        String(format: "$%.2f", Double(dailyBudgetCents) / 100)
    }

    var totalSpendFormatted: String {
        String(format: "$%.2f", Double(totalSpendCents) / 100)
    }

    var ctrFormatted: String {
        String(format: "%.1f%%", ctr)
    }

    var cpcFormatted: String {
        String(format: "$%.2f", Double(cpcCents) / 100)
    }

    var pausedCount: Int { campaigns.filter { $0.status == "paused" }.count }
    var activeCount: Int { campaigns.filter { $0.status == "active" }.count }
    var allPaused: Bool { !campaigns.isEmpty && campaigns.allSatisfy { $0.status == "paused" } }
    var allActive: Bool { !campaigns.isEmpty && campaigns.allSatisfy { $0.status == "active" } }
}

// MARK: - Billing Models (Polsia-like)

struct SubscriptionInfo: Codable {
    let status: String
    let planId: String?
    let planLabel: String?
    let creditsRemaining: Int
    let packCredits: Int
    let totalCredits: Int
    let creditsUsedPeriod: Int
    let creditsMonthly: Int
    let trialEnd: String?
    let currentPeriodEnd: String?
    let ownerActionable: Bool
    let actionableMessage: String?

    enum CodingKeys: String, CodingKey {
        case status
        case planId = "plan_id"
        case planLabel = "plan_label"
        case creditsRemaining = "credits_remaining"
        case packCredits = "pack_credits"
        case totalCredits = "total_credits"
        case creditsUsedPeriod = "credits_used_period"
        case creditsMonthly = "credits_monthly"
        case trialEnd = "trial_end"
        case currentPeriodEnd = "current_period_end"
        case ownerActionable = "owner_actionable"
        case actionableMessage = "actionable_message"
    }

    var statusDisplay: String {
        switch status {
        case "trial": return "Essai gratuit"
        case "active": return "Actif"
        case "cancelled": return "Annulé"
        case "past_due": return "Paiement échoué"
        case "expired": return "Expiré"
        default: return "Non abonné"
        }
    }

    var isActive: Bool { status == "active" || status == "trial" }
    var hasCredits: Bool { totalCredits > 0 }
    var isLowCredits: Bool { totalCredits > 0 && totalCredits < 3 }
}

struct BillingPlan: Codable, Identifiable {
    let id: String
    let label: String
    let cents: Int
    let credits: Int
    let priceDisplay: String
    let isCurrent: Bool

    enum CodingKeys: String, CodingKey {
        case id, label, cents, credits
        case priceDisplay = "price_display"
        case isCurrent = "is_current"
    }

    var creditsDisplay: String { "\(credits) crédits/mois" }
}

struct CreditPack: Codable, Identifiable {
    let id: String
    let label: String
    let cents: Int
    let credits: Int
    let priceDisplay: String

    enum CodingKeys: String, CodingKey {
        case id, label, cents, credits
        case priceDisplay = "price_display"
    }
}

struct BillingPlansResponse: Codable {
    let plans: [BillingPlan]
    let packs: [CreditPack]
    let currentSubscription: SubscriptionInfo?

    enum CodingKeys: String, CodingKey {
        case plans, packs
        case currentSubscription = "current_subscription"
    }
}

struct CheckoutSessionResponse: Codable {
    let checkoutUrl: String

    enum CodingKeys: String, CodingKey {
        case checkoutUrl = "checkout_url"
    }
}

// MARK: - Orders (Système B — ventes founder → clients)

struct Order: Codable, Identifiable {
    let id: String
    let stripePaymentIntentId: String
    let stripeSessionId: String?
    let customerEmail: String?
    let amountCents: Int
    let currency: String
    let productName: String?
    let metaEventSent: Bool
    let createdAt: String

    enum CodingKeys: String, CodingKey {
        case id
        case stripePaymentIntentId = "stripe_payment_intent_id"
        case stripeSessionId = "stripe_session_id"
        case customerEmail = "customer_email"
        case amountCents = "amount_cents"
        case currency
        case productName = "product_name"
        case metaEventSent = "meta_event_sent"
        case createdAt = "created_at"
    }

    var amountDisplay: String {
        let major = Double(amountCents) / 100.0
        return String(format: "%.2f %@", major, currency.uppercased())
    }
}

struct OrdersResponse: Codable {
    let orders: [Order]
    let total: Int
    let totalRevenueCents: Int

    enum CodingKeys: String, CodingKey {
        case orders, total
        case totalRevenueCents = "total_revenue_cents"
    }

    var totalRevenueDisplay: String {
        let major = Double(totalRevenueCents) / 100.0
        return String(format: "%.2f EUR", major)
    }
}

// MARK: - God Mode

struct GodModePlan: Codable, Identifiable {
    let id: String
    let label: String
    let cents: Int
    let hours: Int
    let priceDisplay: String

    enum CodingKeys: String, CodingKey {
        case id, label, cents, hours
        case priceDisplay = "price_display"
    }
}

struct GodModePlansResponse: Codable {
    let plans: [GodModePlan]
}

struct GodModeActiveResponse: Codable {
    let active: Bool
    let session: GodModeActiveSession?
}

struct GodModeActiveSession: Codable {
    let id: String
    let godPlanId: String
    let hours: Int
    let startedAt: String?
    let expiresAt: String?

    enum CodingKeys: String, CodingKey {
        case id, hours
        case godPlanId = "god_plan_id"
        case startedAt = "started_at"
        case expiresAt = "expires_at"
    }
}

struct PortalSessionResponse: Codable {
    let portalUrl: String
    enum CodingKeys: String, CodingKey {
        case portalUrl = "portal_url"
    }
}

struct Invoice: Codable, Identifiable {
    let id: String
    let number: String?
    let amountPaid: Int
    let currency: String
    let status: String
    let created: Int
    let hostedInvoiceUrl: String?
    let invoicePdf: String?

    enum CodingKeys: String, CodingKey {
        case id, number, currency, status, created
        case amountPaid = "amount_paid"
        case hostedInvoiceUrl = "hosted_invoice_url"
        case invoicePdf = "invoice_pdf"
    }

    var amountDisplay: String {
        String(format: "%.2f %@", Double(amountPaid) / 100.0, currency.uppercased())
    }
}

struct InvoicesResponse: Codable {
    let invoices: [Invoice]
}

// MARK: - Stripe Products (Payment Links listing)

struct StripePrice: Codable {
    let priceId: String?
    let amount: Int?
    let currency: String
    let recurring: String?

    enum CodingKeys: String, CodingKey {
        case priceId = "price_id"
        case amount, currency, recurring
    }
}

struct StripeProduct: Codable, Identifiable {
    let id: String
    let name: String
    let description: String
    let prices: [StripePrice]
    let paymentLinkUrl: String?

    enum CodingKeys: String, CodingKey {
        case id, name, description, prices
        case paymentLinkUrl = "payment_link_url"
    }
}

struct StripeProductsResponse: Codable {
    let products: [StripeProduct]
    let count: Int
}
