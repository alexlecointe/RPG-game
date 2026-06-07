import SwiftUI

struct QuestChainView: View {
    @EnvironmentObject private var appState: AppState
    @Environment(\.dismiss) private var dismiss
    @State private var launchingStep: Int?
    @State private var isRetrying = false

    var body: some View {
        NavigationStack {
            ZStack {
                PixelTheme.bgDark.ignoresSafeArea()

                if appState.questChain.isEmpty {
                    emptyState
                } else {
                    ScrollViewReader { proxy in
                        ScrollView {
                            VStack(spacing: 0) {
                                headerSection

                                ForEach(Array(appState.questChain.enumerated()), id: \.element.id) { index, step in
                                    VStack(spacing: 0) {
                                        if index > 0 {
                                            connectorLine(from: appState.questChain[index - 1], to: step)
                                        }
                                        QuestStepRow(
                                            step: step,
                                            stepIndex: index,
                                            isLaunching: launchingStep == step.stepNumber,
                                            onStart: { startStep(step) }
                                        )
                                        .id(step.id)
                                    }
                                }

                                Spacer(minLength: 40)
                            }
                            .padding(.horizontal, 16)
                        }
                        .refreshable {
                            await appState.fetchQuestChain()
                        }
                        .onAppear {
                            if let first = appState.questChain.first(where: { $0.isAvailable }) {
                                DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
                                    withAnimation { proxy.scrollTo(first.id, anchor: .center) }
                                }
                            }
                        }
                    }
                }
            }
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .principal) {
                    Text("QUEST CHAIN")
                        .font(PixelTheme.headlineFont)
                        .foregroundStyle(PixelTheme.accent)
                }
                ToolbarItem(placement: .cancellationAction) {
                    Button(action: { dismiss() }) {
                        Text("✕")
                            .font(PixelTheme.bodyFont)
                            .foregroundStyle(PixelTheme.textSecondary)
                    }
                }
            }
            .toolbarBackground(PixelTheme.bgMedium, for: .navigationBar)
            .toolbarBackground(.visible, for: .navigationBar)
            .task {
                await appState.fetchQuestChain()
            }
        }
    }

    private var emptyState: some View {
        VStack(spacing: 16) {
            Image(systemName: "scroll")
                .font(.system(size: 48))
                .foregroundStyle(PixelTheme.textSecondary)
            Text("CHARGEMENT DES QUÊTES...")
                .font(PixelTheme.bodyFont)
                .foregroundStyle(PixelTheme.textSecondary)
            if !isRetrying {
                Button(action: {
                    isRetrying = true
                    Task {
                        await appState.fetchQuestChain()
                        isRetrying = false
                    }
                }) {
                    Text("RÉESSAYER")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(PixelButtonStyle())
                .padding(.horizontal, 40)
            } else {
                ProgressView().tint(PixelTheme.accent)
            }
        }
    }

    // MARK: - Header

    private var businessType: BusinessType {
        appState.company?.businessType ?? .ecommerce
    }

    private var headerSection: some View {
        VStack(spacing: 8) {
            let completed = appState.questChain.filter { $0.isCompleted }.count
            let total = appState.questChain.count

            Text(businessType.questChainTitle)
                .font(PixelTheme.bodyFont)
                .foregroundStyle(PixelTheme.textPrimary)

            HStack(spacing: 8) {
                Text("\(completed)/\(total)")
                    .font(PixelTheme.headlineFont)
                    .foregroundStyle(PixelTheme.accentGreen)

                GeometryReader { geo in
                    ZStack(alignment: .leading) {
                        RoundedRectangle(cornerRadius: 3)
                            .fill(PixelTheme.bgDark)
                        RoundedRectangle(cornerRadius: 3)
                            .fill(PixelTheme.accentGreen)
                            .frame(width: total > 0 ? geo.size.width * CGFloat(completed) / CGFloat(total) : 0)
                    }
                }
                .frame(height: 8)
            }

            Text(businessType.questChainSubtitle)
                .font(PixelTheme.microFont)
                .foregroundStyle(PixelTheme.textSecondary)
        }
        .pixelCard()
        .padding(.top, 12)
        .padding(.bottom, 8)
    }

    // MARK: - Connector line

    private func connectorLine(from prev: QuestStep, to current: QuestStep) -> some View {
        Rectangle()
            .fill(prev.isCompleted ? PixelTheme.accentGreen.opacity(0.6) : PixelTheme.bgLight)
            .frame(width: 3, height: 20)
    }

    // MARK: - Actions

    private func startStep(_ step: QuestStep) {
        guard step.isAvailable, launchingStep == nil else { return }
        launchingStep = step.stepNumber
        Task {
            await appState.startQuestStep(stepNumber: step.stepNumber)
            launchingStep = nil
        }
    }
}

// MARK: - Quest Step Row

struct QuestStepRow: View {
    let step: QuestStep
    let stepIndex: Int
    let isLaunching: Bool
    let onStart: () -> Void

    var body: some View {
        HStack(spacing: 12) {
            stepIndicator
            stepContent
        }
        .pixelCard(highlighted: step.isAvailable)
        .opacity(step.isLocked ? 0.5 : 1.0)
    }

    private var stepIndicator: some View {
        ZStack {
            Circle()
                .fill(indicatorColor.opacity(0.2))
                .frame(width: 44, height: 44)
                .overlay(
                    Circle().stroke(indicatorColor, lineWidth: 2)
                )

            if step.isCompleted {
                Image(systemName: "checkmark")
                    .font(.system(size: 18, weight: .bold))
                    .foregroundStyle(PixelTheme.accentGreen)
            } else if step.isRunning {
                ProgressView()
                    .scaleEffect(0.8)
                    .tint(PixelTheme.accent)
            } else if step.isLocked {
                Image(systemName: "lock.fill")
                    .font(.system(size: 14))
                    .foregroundStyle(PixelTheme.textSecondary)
            } else {
                Text("\(step.stepNumber)")
                    .font(PixelTheme.bodyFont)
                    .foregroundStyle(PixelTheme.accent)
            }
        }
    }

    private var stepContent: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text("ETAPE \(step.stepNumber)")
                    .font(PixelTheme.microFont)
                    .foregroundStyle(indicatorColor)

                Spacer()

                Text(step.buildingName.uppercased())
                    .font(PixelTheme.microFont)
                    .foregroundStyle(PixelTheme.textSecondary)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(PixelTheme.bgMedium, in: RoundedRectangle(cornerRadius: 3))
            }

            Text(step.title.uppercased())
                .font(PixelTheme.captionFont)
                .foregroundStyle(PixelTheme.textPrimary)

            Text(step.description)
                .font(PixelTheme.microFont)
                .foregroundStyle(PixelTheme.textSecondary)
                .lineLimit(2)

            if step.isAvailable {
                Button(action: onStart) {
                    HStack {
                        if isLaunching {
                            ProgressView().tint(PixelTheme.bgDark).scaleEffect(0.7)
                        }
                        Text(isLaunching ? "LANCEMENT..." : "LANCER LA MISSION")
                    }
                    .frame(maxWidth: .infinity)
                }
                .buttonStyle(PixelButtonStyle())
                .disabled(isLaunching)
                .padding(.top, 4)
            } else if step.isCompleted {
                HStack(spacing: 4) {
                    Text("✓")
                        .foregroundStyle(PixelTheme.accentGreen)
                    Text("TERMINÉ")
                        .foregroundStyle(PixelTheme.accentGreen)
                }
                .font(PixelTheme.microFont)
                .padding(.top, 2)
            } else if step.isRunning {
                Text("EN COURS...")
                    .font(PixelTheme.microFont)
                    .foregroundStyle(PixelTheme.accent)
                    .padding(.top, 2)
            } else if step.isLocked {
                HStack(spacing: 4) {
                    Image(systemName: "lock.fill")
                        .font(.system(size: 10))
                    Text("VERROUILLÉ")
                }
                .font(PixelTheme.microFont)
                .foregroundStyle(PixelTheme.textSecondary)
                .padding(.top, 2)
            }
        }
    }

    private var indicatorColor: Color {
        if step.isCompleted { return PixelTheme.accentGreen }
        if step.isRunning { return PixelTheme.accent }
        if step.isAvailable { return PixelTheme.accent }
        return PixelTheme.textSecondary
    }
}
