import SwiftUI

// MARK: - PaywallView

struct PaywallView: View {
    let companyId: String
    @Environment(\.dismiss) private var dismiss
    @EnvironmentObject private var appState: AppState

    @State private var plans: [BillingPlan] = []
    @State private var packs: [CreditPack] = []
    @State private var subscription: SubscriptionInfo?
    @State private var isLoading = true
    @State private var loadingItemId: String?
    @State private var errorMessage: String?
    @State private var checkoutURL: URL?
    @State private var showSafari = false
    @State private var selectedTab = 0  // 0=Plans, 1=Packs
    @State private var showOrders = false
    @State private var showGodMode = false
    @State private var showProducts = false
    @State private var showInvoices = false
    @State private var portalURL: URL?
    @State private var showPortalSafari = false
    @State private var activeGodMode: GodModeActiveSession?

    var body: some View {
        ZStack {
            PixelTheme.bgDark.ignoresSafeArea()

            VStack(spacing: 0) {
                headerBar
                subscriptionBanner
                tabPicker
                    .padding(.horizontal)
                    .padding(.top, 8)

                if isLoading {
                    Spacer()
                    ProgressView()
                        .tint(PixelTheme.accent)
                    Spacer()
                } else if let error = errorMessage {
                    Spacer()
                    Text(error).foregroundStyle(PixelTheme.accentRed).font(PixelTheme.bodyFont).padding()
                    Spacer()
                } else {
                    TabView(selection: $selectedTab) {
                        plansTab.tag(0)
                        packsTab.tag(1)
                    }
                    .tabViewStyle(.page(indexDisplayMode: .never))
                }

                if let msg = subscription?.actionableMessage, subscription?.ownerActionable == true {
                    Text(msg)
                        .font(PixelTheme.captionFont)
                        .foregroundStyle(PixelTheme.accent)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal)
                        .padding(.bottom, 8)
                }
            }
        }
        .sheet(isPresented: $showSafari) {
            if let url = checkoutURL {
                SafariView(url: url)
                    .ignoresSafeArea()
                    .onDisappear { refreshSubscription() }
            }
        }
        .sheet(isPresented: $showGodMode, onDismiss: { Task { await loadActiveGodMode() } }) {
            GodModeView(companyId: companyId)
        }
        .sheet(isPresented: $showOrders) {
            OrdersView(companyId: companyId)
        }
        .sheet(isPresented: $showProducts) {
            ProductsView(companyId: companyId)
        }
        .sheet(isPresented: $showInvoices) {
            InvoicesView(companyId: companyId)
        }
        .sheet(isPresented: $showPortalSafari) {
            if let url = portalURL { SafariView(url: url).ignoresSafeArea() }
        }
        .task {
            await loadBillingData()
            await loadActiveGodMode()
        }
    }

    // MARK: - Header

    private var headerBar: some View {
        HStack {
            Button { dismiss() } label: {
                Image(systemName: "xmark")
                    .font(.system(size: 16, weight: .bold))
                    .foregroundStyle(PixelTheme.textSecondary)
            }
            Spacer()
            Text("CRÉDITS & PLANS")
                .font(PixelTheme.headlineFont)
                .foregroundStyle(PixelTheme.accent)
            Spacer()
            // placeholder for alignment
            Image(systemName: "xmark").opacity(0)
        }
        .padding(.horizontal)
        .padding(.vertical, 12)
        .background(PixelTheme.bgMedium)
    }

    // MARK: - Subscription Banner

    private var subscriptionBanner: some View {
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 4) {
                if let sub = subscription {
                    Text(sub.statusDisplay.uppercased())
                        .font(PixelTheme.captionFont)
                        .foregroundStyle(statusColor(sub.status))
                    Text("\(sub.totalCredits) CR restants")
                        .font(PixelTheme.headlineFont)
                        .foregroundStyle(sub.isLowCredits ? PixelTheme.accentRed : PixelTheme.textPrimary)
                    if let plan = sub.planLabel {
                        Text("Plan \(plan) — \(sub.creditsMonthly) CR/mois")
                            .font(PixelTheme.captionFont)
                            .foregroundStyle(PixelTheme.textSecondary)
                    }
                } else {
                    Text("NON ABONNÉ")
                        .font(PixelTheme.captionFont)
                        .foregroundStyle(PixelTheme.textSecondary)
                    Text("0 CR")
                        .font(PixelTheme.headlineFont)
                        .foregroundStyle(PixelTheme.accentRed)
                }
            }
            Spacer()
            Image(systemName: "bolt.circle.fill")
                .font(.system(size: 36))
                .foregroundStyle(PixelTheme.accent)
        }
        .padding()
        .background(PixelTheme.bgMedium)
        .overlay(Rectangle().frame(height: 1).foregroundStyle(PixelTheme.cardBorder), alignment: .bottom)
    }

    // MARK: - Tab picker

    private var tabPicker: some View {
        VStack(spacing: 8) {
            HStack(spacing: 0) {
                tabButton(title: "ABONNEMENTS", index: 0)
                tabButton(title: "PACKS ONE-SHOT", index: 1)
            }
            .background(PixelTheme.bgMedium)
            .clipShape(RoundedRectangle(cornerRadius: 8))

            // God Mode active banner
            if let gm = activeGodMode {
                godModeBanner(gm)
            }

            HStack(spacing: 8) {
                shortcutButton(
                    icon: "bolt.fill",
                    label: activeGodMode != nil ? "GOD ON" : "GOD MODE",
                    color: PixelTheme.accent,
                    action: { showGodMode = true }
                )
                shortcutButton(
                    icon: "cart.fill",
                    label: "VENTES",
                    color: PixelTheme.accentGreen,
                    action: { showOrders = true }
                )
            }
            HStack(spacing: 8) {
                shortcutButton(
                    icon: "link.badge.plus",
                    label: "PRODUITS",
                    color: PixelTheme.accent,
                    action: { showProducts = true }
                )
                shortcutButton(
                    icon: "doc.text",
                    label: "FACTURES",
                    color: PixelTheme.textSecondary,
                    action: { showInvoices = true }
                )
            }
            HStack(spacing: 8) {
                Button { Task { await openPortal() } } label: {
                    HStack(spacing: 6) {
                        Image(systemName: "gearshape").font(.system(size: 12))
                        Text("GÉRER ABONNEMENT")
                            .font(PixelTheme.captionFont)
                    }
                    .foregroundStyle(PixelTheme.textSecondary)
                    .padding(.vertical, 7)
                    .frame(maxWidth: .infinity)
                    .background(PixelTheme.bgMedium)
                    .clipShape(RoundedRectangle(cornerRadius: 6))
                    .overlay(RoundedRectangle(cornerRadius: 6).stroke(PixelTheme.cardBorder, lineWidth: 1))
                }
            }
        }
    }

    private func shortcutButton(icon: String, label: String, color: Color, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack(spacing: 6) {
                Image(systemName: icon).font(.system(size: 12))
                Text(label).font(PixelTheme.captionFont)
            }
            .foregroundStyle(color)
            .padding(.vertical, 7)
            .frame(maxWidth: .infinity)
            .background(color.opacity(0.12))
            .clipShape(RoundedRectangle(cornerRadius: 6))
            .overlay(RoundedRectangle(cornerRadius: 6).stroke(color.opacity(0.3), lineWidth: 1))
        }
    }

    private func godModeBanner(_ session: GodModeActiveSession) -> some View {
        HStack(spacing: 8) {
            Image(systemName: "bolt.fill").foregroundStyle(PixelTheme.accent)
            VStack(alignment: .leading, spacing: 2) {
                Text("GOD MODE ACTIF").font(PixelTheme.captionFont).foregroundStyle(PixelTheme.accent)
                if let exp = session.expiresAt {
                    Text("Expire \(formattedDate(exp))")
                        .font(PixelTheme.microFont)
                        .foregroundStyle(PixelTheme.textSecondary)
                }
            }
            Spacer()
            Image(systemName: "circle.fill")
                .font(.system(size: 8))
                .foregroundStyle(PixelTheme.accentGreen)
        }
        .padding(.horizontal, 12).padding(.vertical, 8)
        .background(PixelTheme.accent.opacity(0.1))
        .clipShape(RoundedRectangle(cornerRadius: 6))
        .overlay(RoundedRectangle(cornerRadius: 6).stroke(PixelTheme.accent.opacity(0.3), lineWidth: 1))
    }

    private func formattedDate(_ iso: String) -> String {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let d = f.date(from: iso) {
            let df = DateFormatter()
            df.dateStyle = .short; df.timeStyle = .short; df.locale = Locale(identifier: "fr_FR")
            return df.string(from: d)
        }
        return iso
    }

    private func tabButton(title: String, index: Int) -> some View {
        Button {
            withAnimation { selectedTab = index }
        } label: {
            Text(title)
                .font(PixelTheme.captionFont)
                .foregroundStyle(selectedTab == index ? PixelTheme.bgDark : PixelTheme.textSecondary)
                .padding(.vertical, 8)
                .frame(maxWidth: .infinity)
                .background(selectedTab == index ? PixelTheme.accent : Color.clear)
                .clipShape(RoundedRectangle(cornerRadius: 6))
        }
        .padding(3)
    }

    // MARK: - Plans tab

    private var plansTab: some View {
        ScrollView {
            LazyVStack(spacing: 12) {
                Text("3 jours gratuits · Pas de rollover mensuel")
                    .font(PixelTheme.captionFont)
                    .foregroundStyle(PixelTheme.textSecondary)
                    .padding(.top, 8)

                ForEach(plans) { plan in
                    PlanCard(
                        plan: plan,
                        isCurrentPlan: plan.isCurrent,
                        isLoading: loadingItemId == plan.id
                    ) {
                        await subscribe(planId: plan.id)
                    }
                }
            }
            .padding(.horizontal)
            .padding(.bottom, 24)
        }
    }

    // MARK: - Packs tab

    private var packsTab: some View {
        ScrollView {
            LazyVStack(spacing: 12) {
                Text("Ajout immédiat · S'accumule avec votre plan")
                    .font(PixelTheme.captionFont)
                    .foregroundStyle(PixelTheme.textSecondary)
                    .padding(.top, 8)

                ForEach(packs) { pack in
                    PackCard(
                        pack: pack,
                        isLoading: loadingItemId == pack.id
                    ) {
                        await buyPack(packId: pack.id)
                    }
                }
            }
            .padding(.horizontal)
            .padding(.bottom, 24)
        }
    }

    // MARK: - Actions

    private func subscribe(planId: String) async {
        await openCheckout(type: "subscription", id: planId)
    }

    private func buyPack(packId: String) async {
        await openCheckout(type: "pack", id: packId)
    }

    private func openCheckout(type: String, id: String) async {
        loadingItemId = id
        defer { loadingItemId = nil }
        do {
            let url = try await APIClient.shared.createCheckoutSession(
                companyId: companyId,
                type: type,
                planOrPackId: id
            )
            if let parsed = URL(string: url) {
                checkoutURL = parsed
                showSafari = true
            }
        } catch {
            errorMessage = "Erreur : \(error.localizedDescription)"
        }
    }

    private func loadBillingData() async {
        isLoading = true
        defer { isLoading = false }
        do {
            let response = try await APIClient.shared.fetchBillingPlans(companyId: companyId)
            plans = response.plans
            packs = response.packs
            subscription = response.currentSubscription
        } catch {
            errorMessage = "Chargement impossible"
        }
    }

    private func loadActiveGodMode() async {
        let resp = try? await APIClient.shared.fetchActiveGodMode(companyId: companyId)
        activeGodMode = resp?.session
    }

    private func openPortal() async {
        do {
            let urlStr = try await APIClient.shared.fetchBillingPortalURL(companyId: companyId)
            if let url = URL(string: urlStr) {
                portalURL = url
                showPortalSafari = true
            }
        } catch {
            errorMessage = "Portail indisponible"
        }
    }

    private func refreshSubscription() {
        Task {
            try? await Task.sleep(nanoseconds: 1_500_000_000)
            let sub = try? await APIClient.shared.fetchSubscription(companyId: companyId)
            await MainActor.run {
                subscription = sub
                appState.subscription = sub
            }
        }
    }

    private func statusColor(_ status: String) -> Color {
        switch status {
        case "active": return PixelTheme.accentGreen
        case "trial": return PixelTheme.accent
        default: return PixelTheme.accentRed
        }
    }
}

// MARK: - PlanCard

struct PlanCard: View {
    let plan: BillingPlan
    let isCurrentPlan: Bool
    let isLoading: Bool
    let onTap: () async -> Void

    var body: some View {
        Button {
            Task { await onTap() }
        } label: {
            HStack(spacing: 12) {
                VStack(alignment: .leading, spacing: 4) {
                    Text(plan.label.uppercased())
                        .font(PixelTheme.headlineFont)
                        .foregroundStyle(isCurrentPlan ? PixelTheme.accent : PixelTheme.textPrimary)
                    Text(plan.creditsDisplay)
                        .font(PixelTheme.captionFont)
                        .foregroundStyle(PixelTheme.textSecondary)
                }
                Spacer()
                if isLoading {
                    ProgressView().tint(PixelTheme.accent).scaleEffect(0.8)
                } else {
                    VStack(alignment: .trailing, spacing: 2) {
                        Text(plan.priceDisplay)
                            .font(PixelTheme.headlineFont)
                            .foregroundStyle(isCurrentPlan ? PixelTheme.accent : PixelTheme.accentGreen)
                        if isCurrentPlan {
                            Text("PLAN ACTUEL")
                                .font(PixelTheme.microFont)
                                .foregroundStyle(PixelTheme.accent)
                        }
                    }
                }
            }
            .padding()
            .background(isCurrentPlan ? PixelTheme.accent.opacity(0.15) : PixelTheme.bgMedium)
            .clipShape(RoundedRectangle(cornerRadius: 10))
            .overlay(
                RoundedRectangle(cornerRadius: 10)
                    .stroke(isCurrentPlan ? PixelTheme.accent : PixelTheme.cardBorder, lineWidth: isCurrentPlan ? 1.5 : 0.5)
            )
        }
        .disabled(isLoading)
    }
}

// MARK: - PackCard

struct PackCard: View {
    let pack: CreditPack
    let isLoading: Bool
    let onTap: () async -> Void

    var body: some View {
        Button {
            Task { await onTap() }
        } label: {
            HStack(spacing: 12) {
                HStack(spacing: 6) {
                    Image(systemName: "bolt.fill")
                        .font(.system(size: 18))
                        .foregroundStyle(PixelTheme.accent)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(pack.label.uppercased())
                            .font(PixelTheme.headlineFont)
                            .foregroundStyle(PixelTheme.textPrimary)
                        Text("One-shot · ne réinitialise pas")
                            .font(PixelTheme.captionFont)
                            .foregroundStyle(PixelTheme.textSecondary)
                    }
                }
                Spacer()
                if isLoading {
                    ProgressView().tint(PixelTheme.accent).scaleEffect(0.8)
                } else {
                    Text(pack.priceDisplay)
                        .font(PixelTheme.headlineFont)
                        .foregroundStyle(PixelTheme.accentBlue)
                }
            }
            .padding()
            .background(PixelTheme.bgMedium)
            .clipShape(RoundedRectangle(cornerRadius: 10))
            .overlay(RoundedRectangle(cornerRadius: 10).stroke(PixelTheme.cardBorder, lineWidth: 0.5))
        }
        .disabled(isLoading)
    }
}

// SafariView is defined in Views/Base/SafariView.swift
