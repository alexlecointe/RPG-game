import SwiftUI

struct BetaFeedbackView: View {
    let mission: Mission
    let onSubmit: () -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var usedDeliverable = false
    @State private var rating = 3
    @State private var comment = ""

    var body: some View {
        NavigationStack {
            ZStack {
                PixelTheme.bgDark.ignoresSafeArea()
                ScrollView {
                    VStack(alignment: .leading, spacing: 16) {
                        Text("BETA — TON AVIS")
                            .font(PixelTheme.headlineFont)
                            .foregroundStyle(PixelTheme.accent)

                        Text("As-tu utilise ce livrable pour ton business ?")
                            .font(PixelTheme.captionFont)
                            .foregroundStyle(PixelTheme.textSecondary)

                        Toggle(isOn: $usedDeliverable) {
                            Text("Oui, je l'ai utilise / copie")
                                .font(PixelTheme.captionFont)
                                .foregroundStyle(PixelTheme.textPrimary)
                        }
                        .tint(PixelTheme.accentGreen)

                        VStack(alignment: .leading, spacing: 8) {
                            Text("Note qualite : \(rating)/5")
                                .font(PixelTheme.captionFont)
                                .foregroundStyle(PixelTheme.textPrimary)
                            HStack {
                                ForEach(1...5, id: \.self) { star in
                                    Button(action: { rating = star }) {
                                        Text(star <= rating ? "★" : "☆")
                                            .font(.title2)
                                            .foregroundStyle(star <= rating ? PixelTheme.accent : PixelTheme.textSecondary)
                                    }
                                }
                            }
                        }

                        TextField("Commentaire (optionnel)", text: $comment, axis: .vertical)
                            .lineLimit(2...4)
                            .font(PixelTheme.captionFont)
                            .padding(10)
                            .background(PixelTheme.bgMedium, in: RoundedRectangle(cornerRadius: 8))

                        Button("ENVOYER") {
                            submitFeedback()
                        }
                        .buttonStyle(PixelButtonStyle(color: PixelTheme.accentGreen))

                        Button("PASSER") {
                            dismiss()
                            onSubmit()
                        }
                        .font(PixelTheme.captionFont)
                        .foregroundStyle(PixelTheme.textSecondary)
                        .frame(maxWidth: .infinity)
                    }
                    .padding(16)
                }
            }
            .navigationBarTitleDisplayMode(.inline)
        }
    }

    private func submitFeedback() {
        AnalyticsTracker.track("beta_feedback", properties: [
            "mission_type": mission.missionType,
            "used": usedDeliverable ? "yes" : "no",
            "rating": "\(rating)",
            "comment": comment.prefix(200).description,
        ])
        Task {
            if let companyId = UserDefaults.standard.string(forKey: "rpg_company_id") {
                try? await APIClient.shared.submitBetaFeedback(
                    companyId: companyId,
                    missionId: mission.id,
                    missionType: mission.missionType,
                    used: usedDeliverable,
                    rating: rating,
                    comment: comment
                )
            }
        }
        dismiss()
        onSubmit()
    }
}
