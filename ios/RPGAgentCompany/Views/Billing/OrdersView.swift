import SwiftUI

// MARK: - OrdersView — Revenus founder (Système B)

struct OrdersView: View {
    let companyId: String

    @State private var ordersResponse: OrdersResponse?
    @State private var isLoading = true
    @State private var errorMessage: String?

    var body: some View {
        ZStack {
            PixelTheme.bgDark.ignoresSafeArea()
            VStack(spacing: 0) {
                headerBar
                if isLoading {
                    Spacer()
                    ProgressView().tint(PixelTheme.accent)
                    Spacer()
                } else if let error = errorMessage {
                    Spacer()
                    Text(error).foregroundStyle(PixelTheme.accentRed).font(PixelTheme.bodyFont).padding()
                    Spacer()
                } else {
                    ScrollView {
                        LazyVStack(spacing: 0) {
                            revenueBanner
                                .padding(.horizontal)
                                .padding(.top, 16)
                                .padding(.bottom, 8)

                            if let orders = ordersResponse?.orders, orders.isEmpty {
                                emptyState
                            } else {
                                ForEach(ordersResponse?.orders ?? []) { order in
                                    OrderRow(order: order)
                                    Divider().background(PixelTheme.cardBorder).padding(.leading, 16)
                                }
                            }
                        }
                        .padding(.bottom, 24)
                    }
                }
            }
        }
        .task { await loadOrders() }
    }

    // MARK: - Header

    private var headerBar: some View {
        HStack {
            Text("VENTES")
                .font(PixelTheme.headlineFont)
                .foregroundStyle(PixelTheme.accent)
            Spacer()
            Button { Task { await loadOrders() } } label: {
                Image(systemName: "arrow.clockwise")
                    .foregroundStyle(PixelTheme.textSecondary)
            }
        }
        .padding(.horizontal)
        .padding(.vertical, 12)
        .background(PixelTheme.bgMedium)
        .overlay(Rectangle().frame(height: 1).foregroundStyle(PixelTheme.cardBorder), alignment: .bottom)
    }

    // MARK: - Revenue banner

    private var revenueBanner: some View {
        HStack(spacing: 16) {
            VStack(alignment: .leading, spacing: 4) {
                Text("REVENU TOTAL")
                    .font(PixelTheme.captionFont)
                    .foregroundStyle(PixelTheme.textSecondary)
                Text(ordersResponse?.totalRevenueDisplay ?? "0.00 EUR")
                    .font(PixelTheme.headlineFont)
                    .foregroundStyle(PixelTheme.accentGreen)
            }
            Spacer()
            VStack(alignment: .trailing, spacing: 4) {
                Text("COMMANDES")
                    .font(PixelTheme.captionFont)
                    .foregroundStyle(PixelTheme.textSecondary)
                Text("\(ordersResponse?.total ?? 0)")
                    .font(PixelTheme.headlineFont)
                    .foregroundStyle(PixelTheme.accent)
            }
        }
        .padding()
        .background(PixelTheme.bgMedium)
        .clipShape(RoundedRectangle(cornerRadius: 10))
        .overlay(RoundedRectangle(cornerRadius: 10).stroke(PixelTheme.cardBorder, lineWidth: 1))
    }

    // MARK: - Empty state

    private var emptyState: some View {
        VStack(spacing: 12) {
            Image(systemName: "cart")
                .font(.system(size: 44))
                .foregroundStyle(PixelTheme.textSecondary)
            Text("Aucune vente pour l'instant")
                .font(PixelTheme.bodyFont)
                .foregroundStyle(PixelTheme.textSecondary)
            Text("Demandez à votre agent Builder de créer un Payment Link pour commencer à vendre.")
                .font(PixelTheme.captionFont)
                .foregroundStyle(PixelTheme.textSecondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 32)
        }
        .padding(.top, 60)
    }

    // MARK: - Load

    private func loadOrders() async {
        isLoading = true
        defer { isLoading = false }
        do {
            ordersResponse = try await APIClient.shared.fetchOrders(companyId: companyId)
        } catch {
            errorMessage = "Impossible de charger les ventes"
        }
    }
}

// MARK: - OrderRow

private struct OrderRow: View {
    let order: Order

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: "checkmark.circle.fill")
                .foregroundStyle(PixelTheme.accentGreen)
                .font(.system(size: 20))

            VStack(alignment: .leading, spacing: 4) {
                Text(order.productName ?? "Produit")
                    .font(PixelTheme.bodyFont)
                    .foregroundStyle(PixelTheme.textPrimary)
                Text(order.customerEmail ?? "Client inconnu")
                    .font(PixelTheme.captionFont)
                    .foregroundStyle(PixelTheme.textSecondary)
                Text(formattedDate(order.createdAt))
                    .font(PixelTheme.microFont)
                    .foregroundStyle(PixelTheme.textSecondary)
            }
            Spacer()
            Text(order.amountDisplay)
                .font(PixelTheme.bodyFont)
                .foregroundStyle(PixelTheme.accentGreen)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
    }

    private func formattedDate(_ iso: String) -> String {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = formatter.date(from: iso) {
            let display = DateFormatter()
            display.dateStyle = .short
            display.timeStyle = .short
            display.locale = Locale(identifier: "fr_FR")
            return display.string(from: date)
        }
        return iso
    }
}
