import SafariServices
import SwiftUI

// MARK: - InvoicesView — Historique factures Stripe

struct InvoicesView: View {
    let companyId: String
    @Environment(\.dismiss) private var dismiss

    @State private var invoices: [Invoice] = []
    @State private var isLoading = true
    @State private var errorMessage: String?
    @State private var safariURL: URL?
    @State private var showSafari = false

    var body: some View {
        NavigationStack {
            ZStack {
                PixelTheme.bgDark.ignoresSafeArea()
                Group {
                    if isLoading {
                        ProgressView().tint(PixelTheme.accent)
                    } else if let error = errorMessage {
                        Text(error).foregroundStyle(PixelTheme.accentRed).font(PixelTheme.bodyFont).padding()
                    } else if invoices.isEmpty {
                        VStack(spacing: 12) {
                            Image(systemName: "doc.text")
                                .font(.system(size: 44))
                                .foregroundStyle(PixelTheme.textSecondary)
                            Text("Aucune facture")
                                .font(PixelTheme.bodyFont)
                                .foregroundStyle(PixelTheme.textSecondary)
                        }
                    } else {
                        List {
                            ForEach(invoices) { invoice in
                                InvoiceRow(invoice: invoice) { url in
                                    safariURL = url
                                    showSafari = true
                                }
                                .listRowBackground(PixelTheme.bgMedium)
                            }
                        }
                        .listStyle(.plain)
                        .scrollContentBackground(.hidden)
                    }
                }
            }
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .principal) {
                    Text("FACTURES")
                        .font(PixelTheme.headlineFont)
                        .foregroundStyle(PixelTheme.accent)
                }
                ToolbarItem(placement: .cancellationAction) {
                    Button { dismiss() } label: {
                        Text("✕").font(PixelTheme.bodyFont).foregroundStyle(PixelTheme.textSecondary)
                    }
                }
            }
            .toolbarBackground(PixelTheme.bgMedium, for: .navigationBar)
            .toolbarBackground(.visible, for: .navigationBar)
        }
        .sheet(isPresented: $showSafari) {
            if let url = safariURL { SafariView(url: url).ignoresSafeArea() }
        }
        .task { await loadInvoices() }
    }

    private func loadInvoices() async {
        isLoading = true
        defer { isLoading = false }
        do {
            let resp = try await APIClient.shared.fetchInvoices(companyId: companyId)
            invoices = resp.invoices
        } catch {
            errorMessage = "Chargement impossible"
        }
    }
}

// MARK: - InvoiceRow

private struct InvoiceRow: View {
    let invoice: Invoice
    let onOpen: (URL) -> Void

    var body: some View {
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 4) {
                Text(invoice.number ?? invoice.id)
                    .font(PixelTheme.bodyFont)
                    .foregroundStyle(PixelTheme.textPrimary)
                Text(formattedDate(invoice.created))
                    .font(PixelTheme.captionFont)
                    .foregroundStyle(PixelTheme.textSecondary)
            }
            Spacer()
            Text(invoice.amountDisplay)
                .font(PixelTheme.bodyFont)
                .foregroundStyle(PixelTheme.accentGreen)
            statusBadge
            if let urlStr = invoice.hostedInvoiceUrl, let url = URL(string: urlStr) {
                Button { onOpen(url) } label: {
                    Image(systemName: "arrow.up.right.square")
                        .foregroundStyle(PixelTheme.accent)
                }
            }
        }
        .padding(.vertical, 4)
    }

    private var statusBadge: some View {
        Text(invoice.status.uppercased())
            .font(PixelTheme.microFont)
            .foregroundStyle(invoice.status == "paid" ? PixelTheme.accentGreen : PixelTheme.accentRed)
            .padding(.horizontal, 6).padding(.vertical, 2)
            .background((invoice.status == "paid" ? PixelTheme.accentGreen : PixelTheme.accentRed).opacity(0.15))
            .clipShape(RoundedRectangle(cornerRadius: 4))
    }

    private func formattedDate(_ timestamp: Int) -> String {
        let date = Date(timeIntervalSince1970: TimeInterval(timestamp))
        let df = DateFormatter()
        df.dateStyle = .medium; df.timeStyle = .none; df.locale = Locale(identifier: "fr_FR")
        return df.string(from: date)
    }
}
