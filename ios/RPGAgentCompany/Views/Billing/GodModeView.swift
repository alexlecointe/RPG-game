import SafariServices
import SwiftUI

// MARK: - GodModeView — Session autonome (Polsia exact)

struct GodModeView: View {
    let companyId: String
    @Environment(\.dismiss) private var dismiss

    @State private var plans: [GodModePlan] = []
    @State private var isLoading = true
    @State private var loadingPlanId: String?
    @State private var errorMessage: String?
    @State private var checkoutURL: URL?
    @State private var showSafari = false

    var body: some View {
        ZStack {
            PixelTheme.bgDark.ignoresSafeArea()
            VStack(spacing: 0) {
                headerBar
                ScrollView {
                    VStack(spacing: 16) {
                        godModeExplainer
                        if isLoading {
                            ProgressView().tint(PixelTheme.accent).padding(.top, 32)
                        } else if let error = errorMessage {
                            Text(error)
                                .foregroundStyle(PixelTheme.accentRed)
                                .font(PixelTheme.bodyFont)
                                .padding()
                        } else {
                            ForEach(plans) { plan in
                                GodModePlanCard(plan: plan, isLoading: loadingPlanId == plan.id) {
                                    await buy(planId: plan.id)
                                }
                            }
                        }
                    }
                    .padding(.horizontal)
                    .padding(.bottom, 32)
                }
            }
        }
        .sheet(isPresented: $showSafari) {
            if let url = checkoutURL {
                SafariView(url: url).ignoresSafeArea()
            }
        }
        .task { await loadPlans() }
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
            Text("GOD MODE")
                .font(PixelTheme.headlineFont)
                .foregroundStyle(PixelTheme.accent)
            Spacer()
            Image(systemName: "xmark").opacity(0)
        }
        .padding(.horizontal)
        .padding(.vertical, 12)
        .background(PixelTheme.bgMedium)
        .overlay(Rectangle().frame(height: 1).foregroundStyle(PixelTheme.cardBorder), alignment: .bottom)
    }

    // MARK: - Explainer

    private var godModeExplainer: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 8) {
                Image(systemName: "bolt.fill")
                    .foregroundStyle(PixelTheme.accent)
                Text("SESSION AUTONOME")
                    .font(PixelTheme.captionFont)
                    .foregroundStyle(PixelTheme.accent)
            }
            Text("Vos agents travaillent sans interruption pendant toute la durée achetée.")
                .font(PixelTheme.bodyFont)
                .foregroundStyle(PixelTheme.textPrimary)
            HStack(spacing: 4) {
                Image(systemName: "info.circle")
                    .font(.system(size: 12))
                    .foregroundStyle(PixelTheme.textSecondary)
                Text("N'utilise PAS vos task credits · Facturé séparément")
                    .font(PixelTheme.captionFont)
                    .foregroundStyle(PixelTheme.textSecondary)
            }
        }
        .padding()
        .background(PixelTheme.bgMedium)
        .clipShape(RoundedRectangle(cornerRadius: 10))
        .overlay(RoundedRectangle(cornerRadius: 10).stroke(PixelTheme.accent.opacity(0.3), lineWidth: 1))
        .padding(.top, 16)
    }

    // MARK: - Actions

    private func loadPlans() async {
        isLoading = true
        defer { isLoading = false }
        do {
            let resp = try await APIClient.shared.fetchGodModePlansFor(companyId: companyId)
            plans = resp.plans
        } catch {
            errorMessage = "Chargement impossible"
        }
    }

    private func buy(planId: String) async {
        loadingPlanId = planId
        defer { loadingPlanId = nil }
        do {
            let url = try await APIClient.shared.createGodModeCheckout(
                companyId: companyId,
                godPlanId: planId
            )
            if let parsed = URL(string: url) {
                checkoutURL = parsed
                showSafari = true
            }
        } catch {
            errorMessage = "Erreur : \(error.localizedDescription)"
        }
    }
}

// MARK: - GodModePlanCard

private struct GodModePlanCard: View {
    let plan: GodModePlan
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
                        .foregroundStyle(PixelTheme.textPrimary)
                    Text(hoursLabel)
                        .font(PixelTheme.captionFont)
                        .foregroundStyle(PixelTheme.textSecondary)
                }
                Spacer()
                if isLoading {
                    ProgressView().tint(PixelTheme.accent)
                } else {
                    Text(plan.priceDisplay)
                        .font(PixelTheme.headlineFont)
                        .foregroundStyle(PixelTheme.accent)
                        .padding(.horizontal, 12)
                        .padding(.vertical, 6)
                        .background(PixelTheme.accent.opacity(0.15))
                        .clipShape(RoundedRectangle(cornerRadius: 6))
                }
            }
            .padding()
            .background(PixelTheme.bgMedium)
            .clipShape(RoundedRectangle(cornerRadius: 10))
            .overlay(RoundedRectangle(cornerRadius: 10).stroke(PixelTheme.cardBorder, lineWidth: 1))
        }
        .disabled(isLoading)
    }

    private var hoursLabel: String {
        if plan.hours >= 168 { return "7 jours d'autonomie" }
        if plan.hours >= 24 { return "\(plan.hours / 24)j d'autonomie" }
        return "\(plan.hours)h d'autonomie"
    }
}
