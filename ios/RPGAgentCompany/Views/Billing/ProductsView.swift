import SafariServices
import SwiftUI

// MARK: - ProductsView — Payment Links du founder (Système B)

struct ProductsView: View {
    let companyId: String
    @Environment(\.dismiss) private var dismiss

    @State private var products: [StripeProduct] = []
    @State private var isLoading = true
    @State private var errorMessage: String?

    // Create new payment link
    @State private var showCreateSheet = false

    var body: some View {
        NavigationStack {
            ZStack {
                PixelTheme.bgDark.ignoresSafeArea()
                VStack(spacing: 0) {
                    if isLoading {
                        Spacer()
                        ProgressView().tint(PixelTheme.accent)
                        Spacer()
                    } else if let error = errorMessage {
                        Spacer()
                        Text(error).foregroundStyle(PixelTheme.accentRed).font(PixelTheme.bodyFont).padding()
                        Spacer()
                    } else if products.isEmpty {
                        emptyState
                    } else {
                        productList
                    }
                }
            }
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .principal) {
                    Text("PRODUITS & LIENS")
                        .font(PixelTheme.headlineFont)
                        .foregroundStyle(PixelTheme.accent)
                }
                ToolbarItem(placement: .cancellationAction) {
                    Button { dismiss() } label: {
                        Text("✕").font(PixelTheme.bodyFont).foregroundStyle(PixelTheme.textSecondary)
                    }
                }
                ToolbarItem(placement: .primaryAction) {
                    Button { showCreateSheet = true } label: {
                        Image(systemName: "plus.circle.fill")
                            .foregroundStyle(PixelTheme.accent)
                    }
                }
            }
            .toolbarBackground(PixelTheme.bgMedium, for: .navigationBar)
            .toolbarBackground(.visible, for: .navigationBar)
        }
        .sheet(isPresented: $showCreateSheet, onDismiss: { Task { await loadProducts() } }) {
            CreatePaymentLinkSheet(companyId: companyId)
        }
        .task { await loadProducts() }
    }

    // MARK: - List

    private var productList: some View {
        ScrollView {
            LazyVStack(spacing: 0) {
                Text("\(products.count) produit(s) Stripe")
                    .font(PixelTheme.captionFont)
                    .foregroundStyle(PixelTheme.textSecondary)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.horizontal)
                    .padding(.top, 12)
                    .padding(.bottom, 4)

                ForEach(products) { product in
                    ProductRow(product: product)
                    Divider().background(PixelTheme.cardBorder).padding(.leading, 16)
                }
            }
            .padding(.bottom, 32)
        }
    }

    // MARK: - Empty

    private var emptyState: some View {
        VStack(spacing: 14) {
            Spacer()
            Image(systemName: "link.badge.plus")
                .font(.system(size: 48))
                .foregroundStyle(PixelTheme.textSecondary)
            Text("Aucun produit")
                .font(PixelTheme.headlineFont)
                .foregroundStyle(PixelTheme.textSecondary)
            Text("Appuyez sur + pour créer votre premier Payment Link Stripe. Vos agents peuvent aussi en créer automatiquement.")
                .font(PixelTheme.captionFont)
                .foregroundStyle(PixelTheme.textSecondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 32)
            Button { showCreateSheet = true } label: {
                Label("Créer un Payment Link", systemImage: "plus")
                    .font(PixelTheme.bodyFont)
                    .foregroundStyle(PixelTheme.bgDark)
                    .padding(.horizontal, 20)
                    .padding(.vertical, 10)
                    .background(PixelTheme.accent)
                    .clipShape(RoundedRectangle(cornerRadius: 8))
            }
            Spacer()
        }
    }

    // MARK: - Load

    private func loadProducts() async {
        isLoading = true
        defer { isLoading = false }
        do {
            let resp = try await APIClient.shared.fetchProducts(companyId: companyId)
            products = resp.products
        } catch {
            errorMessage = "Chargement impossible"
        }
    }
}

// MARK: - ProductRow

private struct ProductRow: View {
    let product: StripeProduct
    @State private var showSafari = false
    @State private var safariURL: URL?
    @State private var copied = false

    var body: some View {
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 4) {
                Text(product.name)
                    .font(PixelTheme.bodyFont)
                    .foregroundStyle(PixelTheme.textPrimary)
                if let price = product.prices.first {
                    Text(priceLabel(price))
                        .font(PixelTheme.captionFont)
                        .foregroundStyle(PixelTheme.accentGreen)
                }
                if let url = product.paymentLinkUrl {
                    Text(url)
                        .font(PixelTheme.microFont)
                        .foregroundStyle(PixelTheme.textSecondary)
                        .lineLimit(1)
                }
                if product.requiresConnect == true {
                    Text("PAYOUT EN ATTENTE — CONNECTER STRIPE")
                        .font(PixelTheme.microFont)
                        .foregroundStyle(PixelTheme.accent)
                }
            }
            Spacer()
            VStack(spacing: 6) {
                if let url = product.paymentLinkUrl {
                    Button {
                        UIPasteboard.general.string = url
                        copied = true
                        DispatchQueue.main.asyncAfter(deadline: .now() + 2) { copied = false }
                    } label: {
                        Image(systemName: copied ? "checkmark" : "doc.on.doc")
                            .font(.system(size: 14))
                            .foregroundStyle(copied ? PixelTheme.accentGreen : PixelTheme.accent)
                    }
                    Button {
                        if let parsed = URL(string: url) { safariURL = parsed; showSafari = true }
                    } label: {
                        Image(systemName: "safari")
                            .font(.system(size: 14))
                            .foregroundStyle(PixelTheme.textSecondary)
                    }
                }
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
        .sheet(isPresented: $showSafari) {
            if let url = safariURL { SafariView(url: url).ignoresSafeArea() }
        }
    }

    private func priceLabel(_ price: StripePrice) -> String {
        guard let amount = price.amount else { return "Prix non défini" }
        return String(format: "%.2f %@", Double(amount) / 100.0, price.currency.uppercased())
    }
}

// MARK: - CreatePaymentLinkSheet

struct CreatePaymentLinkSheet: View {
    let companyId: String
    @Environment(\.dismiss) private var dismiss

    @State private var productName = ""
    @State private var amountStr = ""
    @State private var currency = "EUR"
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var createdURL: String?

    private let currencies = ["EUR", "USD", "GBP"]

    var body: some View {
        NavigationStack {
            ZStack {
                PixelTheme.bgDark.ignoresSafeArea()
                ScrollView {
                    VStack(spacing: 20) {
                        if let url = createdURL {
                            successView(url: url)
                        } else {
                            formView
                        }
                    }
                    .padding()
                }
            }
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .principal) {
                    Text("NOUVEAU PAYMENT LINK")
                        .font(PixelTheme.captionFont)
                        .foregroundStyle(PixelTheme.accent)
                }
                ToolbarItem(placement: .cancellationAction) {
                    Button { dismiss() } label: {
                        Text("Fermer").font(PixelTheme.captionFont).foregroundStyle(PixelTheme.textSecondary)
                    }
                }
            }
            .toolbarBackground(PixelTheme.bgMedium, for: .navigationBar)
            .toolbarBackground(.visible, for: .navigationBar)
        }
    }

    private var formView: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Créez un Payment Link permanent que vos clients pourront utiliser pour acheter votre produit.")
                .font(PixelTheme.captionFont)
                .foregroundStyle(PixelTheme.textSecondary)

            pixelField(label: "Nom du produit", placeholder: "ex : Formation SEO Premium", text: $productName)
            pixelField(label: "Prix (en centimes)", placeholder: "ex : 4900 = 49€", text: $amountStr)
                .keyboardType(.numberPad)

            VStack(alignment: .leading, spacing: 6) {
                Text("DEVISE").font(PixelTheme.captionFont).foregroundStyle(PixelTheme.textSecondary)
                Picker("Devise", selection: $currency) {
                    ForEach(currencies, id: \.self) { Text($0) }
                }
                .pickerStyle(.segmented)
            }

            if let error = errorMessage {
                Text(error).foregroundStyle(PixelTheme.accentRed).font(PixelTheme.captionFont)
            }

            Button {
                Task { await create() }
            } label: {
                Group {
                    if isLoading {
                        ProgressView().tint(PixelTheme.bgDark)
                    } else {
                        Text("CRÉER LE PAYMENT LINK")
                            .font(PixelTheme.headlineFont)
                    }
                }
                .foregroundStyle(PixelTheme.bgDark)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 14)
                .background(canCreate ? PixelTheme.accent : PixelTheme.textSecondary)
                .clipShape(RoundedRectangle(cornerRadius: 8))
            }
            .disabled(!canCreate || isLoading)
        }
    }

    private func successView(url: String) -> some View {
        VStack(spacing: 16) {
            Image(systemName: "checkmark.circle.fill")
                .font(.system(size: 56))
                .foregroundStyle(PixelTheme.accentGreen)
            Text("Payment Link créé !")
                .font(PixelTheme.headlineFont)
                .foregroundStyle(PixelTheme.textPrimary)
            Text(url)
                .font(PixelTheme.captionFont)
                .foregroundStyle(PixelTheme.accent)
                .multilineTextAlignment(.center)
            Button {
                UIPasteboard.general.string = url
            } label: {
                Label("Copier le lien", systemImage: "doc.on.doc")
                    .font(PixelTheme.bodyFont)
                    .foregroundStyle(PixelTheme.bgDark)
                    .padding(.horizontal, 20).padding(.vertical, 10)
                    .background(PixelTheme.accent)
                    .clipShape(RoundedRectangle(cornerRadius: 8))
            }
            Text("Intégrez ce lien dans votre site ou partagez-le directement.")
                .font(PixelTheme.captionFont)
                .foregroundStyle(PixelTheme.textSecondary)
                .multilineTextAlignment(.center)
            Text("Si Stripe Connect n'est pas encore prêt, les ventes passent par la plateforme et les payouts seront à finaliser après connexion.")
                .font(PixelTheme.microFont)
                .foregroundStyle(PixelTheme.textSecondary)
                .multilineTextAlignment(.center)
        }
        .padding(.top, 40)
    }

    private func pixelField(label: String, placeholder: String, text: Binding<String>) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(label.uppercased()).font(PixelTheme.captionFont).foregroundStyle(PixelTheme.textSecondary)
            TextField(placeholder, text: text)
                .font(PixelTheme.bodyFont)
                .foregroundStyle(PixelTheme.textPrimary)
                .padding(10)
                .background(PixelTheme.bgMedium)
                .clipShape(RoundedRectangle(cornerRadius: 6))
                .overlay(RoundedRectangle(cornerRadius: 6).stroke(PixelTheme.cardBorder, lineWidth: 1))
        }
    }

    private var canCreate: Bool {
        !productName.trimmingCharacters(in: .whitespaces).isEmpty
        && Int(amountStr) != nil
        && Int(amountStr)! > 0
    }

    private func create() async {
        guard let amount = Int(amountStr) else { return }
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        do {
            let url = try await APIClient.shared.createPaymentLink(
                companyId: companyId,
                productName: productName.trimmingCharacters(in: .whitespaces),
                amountCents: amount,
                currency: currency.lowercased()
            )
            createdURL = url
        } catch {
            errorMessage = "Erreur : \(error.localizedDescription)"
        }
    }
}
