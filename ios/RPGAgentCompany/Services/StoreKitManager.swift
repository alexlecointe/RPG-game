import Foundation
import StoreKit

/// Stub StoreKit — produits consumables pour crédits (voir docs/05-app-store-compliance.md)
@MainActor
final class StoreKitManager: ObservableObject {
    static let productIds = ["credits_100", "credits_500"]

    @Published var products: [Product] = []
    @Published var purchaseMessage: String?

    func loadProducts() async {
        do {
            products = try await Product.products(for: Self.productIds)
        } catch {
            purchaseMessage = "Impossible de charger les produits: \(error.localizedDescription)"
        }
    }

    func purchase(_ product: Product) async {
        do {
            let result = try await product.purchase()
            switch result {
            case .success(let verification):
                switch verification {
                case .verified:
                    purchaseMessage = "Achat validé — sync serveur à brancher (Phase 2)"
                case .unverified:
                    purchaseMessage = "Achat non vérifié"
                }
            case .userCancelled:
                purchaseMessage = "Annulé"
            case .pending:
                purchaseMessage = "En attente"
            @unknown default:
                break
            }
        } catch {
            purchaseMessage = error.localizedDescription
        }
    }
}
