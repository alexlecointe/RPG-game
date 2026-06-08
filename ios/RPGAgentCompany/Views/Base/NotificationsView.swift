import SwiftUI

struct NotificationsView: View {
    @EnvironmentObject private var appState: AppState
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            ZStack {
                PixelTheme.bgDark.ignoresSafeArea()

                if appState.notifications.isEmpty {
                    VStack(spacing: 12) {
                        Image(systemName: "bell.slash")
                            .font(.system(size: 40))
                            .foregroundStyle(PixelTheme.textSecondary.opacity(0.4))
                        Text("Aucune notification")
                            .font(PixelTheme.captionFont)
                            .foregroundStyle(PixelTheme.textSecondary)
                    }
                } else {
                    ScrollView {
                        LazyVStack(spacing: 0) {
                            ForEach(appState.notifications) { notif in
                                NotificationRow(notif: notif)
                                Divider().background(PixelTheme.cardBorder)
                            }
                        }
                        .padding(.bottom, 32)
                    }
                }
            }
            .navigationTitle("NOTIFICATIONS")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Fermer") { dismiss() }
                        .foregroundStyle(PixelTheme.textSecondary)
                }
                if appState.unreadNotificationCount > 0 {
                    ToolbarItem(placement: .primaryAction) {
                        Button("Tout lire") {
                            Task { await appState.markNotificationsRead() }
                        }
                        .font(PixelTheme.captionFont)
                        .foregroundStyle(PixelTheme.accent)
                    }
                }
            }
        }
        .task { await appState.fetchNotifications() }
    }
}

struct NotificationRow: View {
    let notif: CompanyNotification

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: notif.icon)
                .font(.system(size: 16))
                .foregroundStyle(iconColor)
                .frame(width: 28)

            VStack(alignment: .leading, spacing: 3) {
                Text(notif.title)
                    .font(PixelTheme.captionFont)
                    .foregroundStyle(notif.read ? PixelTheme.textSecondary : PixelTheme.textPrimary)
                    .lineLimit(1)
                Text(notif.message)
                    .font(PixelTheme.microFont)
                    .foregroundStyle(PixelTheme.textSecondary)
                    .lineLimit(2)
            }

            Spacer()

            if !notif.read {
                Circle()
                    .fill(PixelTheme.accent)
                    .frame(width: 6, height: 6)
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
        .background(notif.read ? PixelTheme.bgDark : PixelTheme.bgMedium.opacity(0.5))
    }

    private var iconColor: Color {
        switch notif.iconColor {
        case "green": return PixelTheme.accentGreen
        case "red": return PixelTheme.accentRed
        case "accent": return PixelTheme.accent
        default: return PixelTheme.textSecondary
        }
    }
}
