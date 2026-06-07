import SwiftUI

struct RootView: View {
    @EnvironmentObject private var appState: AppState

    var body: some View {
        ZStack {
            PixelTheme.bgDark.ignoresSafeArea()

            Group {
                if appState.hasCompletedOnboarding, appState.company != nil {
                    GameContainerView()
                        .transition(.opacity)
                } else {
                    OnboardingView()
                        .transition(.opacity)
                }
            }
            .animation(.easeInOut(duration: 0.4), value: appState.hasCompletedOnboarding)
        }
        .task { await appState.bootstrap() }
        .alert("Erreur", isPresented: .constant(appState.errorMessage != nil)) {
            Button("OK") { appState.errorMessage = nil }
        } message: {
            Text(appState.errorMessage ?? "")
        }
    }
}
