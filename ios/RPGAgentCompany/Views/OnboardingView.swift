import SwiftUI

struct OnboardingView: View {
    @EnvironmentObject private var appState: AppState
    @State private var companyName = ""
    @State private var mission = ""
    @State private var productDescription = ""
    @State private var targetAudience = ""
    @State private var selectedBusinessType: BusinessType = .ecommerce
    @State private var step: OnboardingStep = .welcome
    @FocusState private var focusedField: Field?

    enum OnboardingStep { case welcome, businessType, nameInput, detailInput, agentsWorking }
    enum Field { case name, mission, product, audience }

    var body: some View {
        ZStack {
            PixelTheme.bgDark.ignoresSafeArea()

            VStack(spacing: 0) {
                Spacer()
                content
                Spacer()
            }
            .padding(.horizontal, 24)
        }
    }

    @ViewBuilder
    private var content: some View {
        switch step {
        case .welcome:
            welcomeScreen
        case .businessType:
            businessTypeScreen
        case .nameInput:
            nameInputScreen
        case .detailInput:
            detailInputScreen
        case .agentsWorking:
            agentsWorkingScreen
        }
    }

    // MARK: - Welcome

    private var welcomeScreen: some View {
        VStack(spacing: 24) {
            pixelLogo
            Text("RPG AGENT CO.")
                .font(PixelTheme.titleFont)
                .foregroundStyle(PixelTheme.accent)
            Text("Construis ta vraie boite\ncomme un village RPG.")
                .font(PixelTheme.bodyFont)
                .foregroundStyle(PixelTheme.textSecondary)
                .multilineTextAlignment(.center)
            Spacer().frame(height: 20)
            Button("NOUVELLE PARTIE") {
                withAnimation(.easeInOut(duration: 0.3)) { step = .businessType }
            }
            .buttonStyle(PixelButtonStyle())
        }
    }

    // MARK: - Business Type Selection

    private var businessTypeScreen: some View {
        VStack(spacing: 20) {
            Text("CHOISIS TON BUSINESS")
                .font(PixelTheme.headlineFont)
                .foregroundStyle(PixelTheme.accent)

            Text("Chaque type a sa propre strategie et ses batiments.")
                .font(PixelTheme.captionFont)
                .foregroundStyle(PixelTheme.textSecondary)
                .multilineTextAlignment(.center)

            VStack(spacing: 10) {
                ForEach(BusinessType.allCases, id: \.rawValue) { bt in
                    businessTypeCard(bt)
                }
            }

            Spacer().frame(height: 8)

            Button("SUIVANT") {
                withAnimation(.easeInOut(duration: 0.3)) { step = .nameInput }
            }
            .buttonStyle(PixelButtonStyle())
        }
    }

    private func businessTypeCard(_ bt: BusinessType) -> some View {
        let isSelected = selectedBusinessType == bt
        return Button(action: {
            withAnimation(.easeOut(duration: 0.15)) { selectedBusinessType = bt }
        }) {
            HStack(spacing: 12) {
                Image(systemName: bt.icon)
                    .font(.system(size: 22))
                    .foregroundStyle(isSelected ? PixelTheme.accent : PixelTheme.textSecondary)
                    .frame(width: 36)

                VStack(alignment: .leading, spacing: 2) {
                    Text(bt.displayName)
                        .font(PixelTheme.bodyFont)
                        .foregroundStyle(isSelected ? PixelTheme.accent : PixelTheme.textPrimary)
                    Text(bt.subtitle)
                        .font(PixelTheme.microFont)
                        .foregroundStyle(PixelTheme.textSecondary)
                }

                Spacer()

                if isSelected {
                    Text("✓")
                        .font(PixelTheme.bodyFont)
                        .foregroundStyle(PixelTheme.accentGreen)
                }
            }
            .padding(12)
            .background(
                RoundedRectangle(cornerRadius: PixelTheme.cardRadius)
                    .fill(isSelected ? PixelTheme.accent.opacity(0.1) : PixelTheme.bgMedium)
            )
            .overlay(
                RoundedRectangle(cornerRadius: PixelTheme.cardRadius)
                    .stroke(isSelected ? PixelTheme.accent : PixelTheme.cardBorder, lineWidth: isSelected ? 2 : 1)
            )
        }
        .buttonStyle(.plain)
    }

    // MARK: - Name input

    private var nameInputScreen: some View {
        VStack(spacing: 20) {
            Text("FONDE TA COMPANY")
                .font(PixelTheme.headlineFont)
                .foregroundStyle(PixelTheme.accent)

            pixelField(label: "NOM", placeholder: "Ex: NovaCraft", text: $companyName, field: .name)
            pixelField(label: "MISSION", placeholder: "En 1 phrase : que fait ta boite ?", text: $mission, field: .mission)

            Spacer().frame(height: 12)
            Button("SUIVANT") {
                withAnimation(.easeInOut(duration: 0.3)) { step = .detailInput }
            }
            .buttonStyle(PixelButtonStyle())
            .disabled(companyName.trimmingCharacters(in: .whitespaces).isEmpty)
        }
    }

    // MARK: - Detail input (product + audience)

    private var detailInputScreen: some View {
        VStack(spacing: 20) {
            Text("DECRIS TON PRODUIT")
                .font(PixelTheme.headlineFont)
                .foregroundStyle(PixelTheme.accent)

            Text("Plus tu donnes de details, plus les agents seront precis.")
                .font(PixelTheme.captionFont)
                .foregroundStyle(PixelTheme.textSecondary)
                .multilineTextAlignment(.center)

            pixelField(label: "PRODUIT", placeholder: "Decris ton produit en 2-3 phrases...", text: $productDescription, field: .product, isLarge: true)
            pixelField(label: "CLIENTS CIBLES", placeholder: "Qui sont tes clients ideaux ?", text: $targetAudience, field: .audience)

            Spacer().frame(height: 12)

            if appState.isLoading {
                ProgressView()
                    .tint(PixelTheme.accent)
            } else {
                Button("LANCER LE JEU") {
                    Task { await launchGame() }
                }
                .buttonStyle(PixelButtonStyle())
            }

            Button("PASSER") {
                Task { await launchGame() }
            }
            .font(PixelTheme.captionFont)
            .foregroundStyle(PixelTheme.textSecondary)
        }
    }

    // MARK: - Agents working screen

    private var agentsWorkingScreen: some View {
        VStack(spacing: 20) {
            Text("TES AGENTS S'ACTIVENT")
                .font(PixelTheme.headlineFont)
                .foregroundStyle(PixelTheme.accent)

            VStack(alignment: .leading, spacing: 12) {
                agentStatusRow(
                    name: "Chercheur",
                    task: "analyse le marche...",
                    status: appState.onboardingAgentStatus["researcher"] ?? .pending
                )
                agentStatusRow(
                    name: "Forgeron",
                    task: "prepare le brief produit...",
                    status: appState.onboardingAgentStatus["builder"] ?? .pending
                )
                agentStatusRow(
                    name: "Marchand",
                    task: "genere des idees...",
                    status: appState.onboardingAgentStatus["marketer"] ?? .pending
                )
            }
            .pixelCard()

            if appState.onboardingReady {
                Button("ENTRER DANS LE VILLAGE") {
                    appState.hasCompletedOnboarding = true
                }
                .buttonStyle(PixelButtonStyle())
                .transition(.scale.combined(with: .opacity))
            } else {
                ProgressView()
                    .tint(PixelTheme.accent)
                Text("Le village se prepare...")
                    .font(PixelTheme.captionFont)
                    .foregroundStyle(PixelTheme.textSecondary)
            }
        }
    }

    private func agentStatusRow(name: String, task: String, status: AgentOnboardingStatus) -> some View {
        HStack(spacing: 8) {
            switch status {
            case .pending:
                Text("○")
                    .font(PixelTheme.bodyFont)
                    .foregroundStyle(PixelTheme.textSecondary)
            case .running:
                ProgressView()
                    .scaleEffect(0.7)
                    .tint(PixelTheme.accent)
            case .done:
                Text("✓")
                    .font(PixelTheme.bodyFont)
                    .foregroundStyle(PixelTheme.accentGreen)
            }

            VStack(alignment: .leading, spacing: 2) {
                Text(name.uppercased())
                    .font(PixelTheme.captionFont)
                    .foregroundStyle(status == .done ? PixelTheme.accentGreen : PixelTheme.textPrimary)
                Text(status == .done ? "termine !" : task)
                    .font(PixelTheme.microFont)
                    .foregroundStyle(PixelTheme.textSecondary)
            }
            Spacer()
        }
    }

    // MARK: - Helpers

    private func launchGame() async {
        await appState.createNewCompany(
            name: companyName.isEmpty ? "Ma Base" : companyName,
            missionStatement: mission.isEmpty ? "Construire mon empire" : mission,
            productDescription: productDescription,
            targetAudience: targetAudience,
            businessType: selectedBusinessType
        )
        appState.completeQuest("talk_guide")
    }

    private func pixelField(label: String, placeholder: String, text: Binding<String>, field: Field, isLarge: Bool = false) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(label)
                .font(PixelTheme.captionFont)
                .foregroundStyle(PixelTheme.textSecondary)
            if isLarge {
                TextField("", text: text, prompt: Text(placeholder).foregroundStyle(PixelTheme.textSecondary.opacity(0.5)), axis: .vertical)
                    .lineLimit(3...5)
                    .font(PixelTheme.captionFont)
                    .foregroundStyle(PixelTheme.textPrimary)
                    .padding(10)
                    .background(PixelTheme.bgMedium, in: RoundedRectangle(cornerRadius: PixelTheme.buttonRadius))
                    .overlay(RoundedRectangle(cornerRadius: PixelTheme.buttonRadius).stroke(PixelTheme.cardBorder))
                    .focused($focusedField, equals: field)
                    .autocorrectionDisabled()
            } else {
                TextField("", text: text, prompt: Text(placeholder).foregroundStyle(PixelTheme.textSecondary.opacity(0.5)))
                    .font(PixelTheme.bodyFont)
                    .foregroundStyle(PixelTheme.textPrimary)
                    .padding(10)
                    .background(PixelTheme.bgMedium, in: RoundedRectangle(cornerRadius: PixelTheme.buttonRadius))
                    .overlay(RoundedRectangle(cornerRadius: PixelTheme.buttonRadius).stroke(PixelTheme.cardBorder))
                    .focused($focusedField, equals: field)
                    .autocorrectionDisabled()
            }
        }
    }

    private var pixelLogo: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 12)
                .fill(PixelTheme.bgLight)
                .frame(width: 100, height: 100)
                .overlay(
                    RoundedRectangle(cornerRadius: 12)
                        .stroke(PixelTheme.accent, lineWidth: 2)
                )
            VStack(spacing: 2) {
                Text("⚔️")
                    .font(.system(size: 40))
                Text("▪▪▪")
                    .font(.system(size: 8))
                    .foregroundStyle(PixelTheme.accent)
            }
        }
    }
}
