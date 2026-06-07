import SwiftUI

struct SageChatView: View {
    @EnvironmentObject private var appState: AppState
    @Environment(\.dismiss) private var dismiss
    @State private var inputText = ""
    @FocusState private var isInputFocused: Bool

    var body: some View {
        NavigationStack {
            ZStack {
                PixelTheme.bgDark.ignoresSafeArea()

                VStack(spacing: 0) {
                    messagesList
                    inputBar
                }
            }
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .principal) {
                    HStack(spacing: 6) {
                        Text("🧙‍♂️")
                            .font(.system(size: 16))
                        Text("LE SAGE")
                            .font(PixelTheme.headlineFont)
                            .foregroundStyle(PixelTheme.textPrimary)
                    }
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
            .onAppear {
                if appState.sageMessages.isEmpty {
                    let nextQuestHint: String
                    if let step = appState.currentQuestStep {
                        nextQuestHint = " Ta prochaine quete : \(step.title). Va au batiment \(step.buildingName) ou ouvre la quest chain."
                    } else {
                        nextQuestHint = ""
                    }
                    let welcome = SageMessage(
                        role: "assistant",
                        content: "Bienvenue, fondateur ! Je suis Le Sage du village.\(nextQuestHint) Pose-moi tes questions sur ta strategie ou demande-moi conseil pour avancer.",
                        timestamp: Date()
                    )
                    appState.sageMessages.append(welcome)
                }
            }
        }
    }

    // MARK: - Messages List

    private var messagesList: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(spacing: 8) {
                    ForEach(appState.sageMessages) { message in
                        messageBubble(message)
                            .id(message.id)
                    }

                    if appState.isSageLoading {
                        typingIndicator
                            .id("typing")
                    }
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 12)
            }
            .onChange(of: appState.sageMessages.count) {
                withAnimation(.easeOut(duration: 0.2)) {
                    if appState.isSageLoading {
                        proxy.scrollTo("typing", anchor: .bottom)
                    } else if let last = appState.sageMessages.last {
                        proxy.scrollTo(last.id, anchor: .bottom)
                    }
                }
            }
            .onChange(of: appState.isSageLoading) {
                withAnimation(.easeOut(duration: 0.2)) {
                    if appState.isSageLoading {
                        proxy.scrollTo("typing", anchor: .bottom)
                    } else if let last = appState.sageMessages.last {
                        proxy.scrollTo(last.id, anchor: .bottom)
                    }
                }
            }
        }
    }

    private func messageBubble(_ message: SageMessage) -> some View {
        HStack(alignment: .top, spacing: 8) {
            if message.isUser {
                Spacer(minLength: 48)
            } else {
                Text("🧙‍♂️")
                    .font(.system(size: 24))
                    .frame(width: 32, height: 32)
            }

            VStack(alignment: message.isUser ? .trailing : .leading, spacing: 4) {
                Text(message.content)
                    .font(PixelTheme.captionFont)
                    .foregroundStyle(message.isUser ? PixelTheme.bgDark : PixelTheme.textPrimary)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 8)
                    .background(
                        RoundedRectangle(cornerRadius: 12)
                            .fill(message.isUser ? PixelTheme.accent : PixelTheme.bgMedium)
                    )
                    .overlay(
                        RoundedRectangle(cornerRadius: 12)
                            .stroke(message.isUser ? Color.clear : PixelTheme.cardBorder, lineWidth: 1)
                    )
                    .textSelection(.enabled)

                Text(message.timestamp, style: .time)
                    .font(PixelTheme.microFont)
                    .foregroundStyle(PixelTheme.textSecondary)
            }

            if !message.isUser {
                Spacer(minLength: 48)
            }
        }
    }

    private var typingIndicator: some View {
        HStack(alignment: .top, spacing: 8) {
            Text("🧙‍♂️")
                .font(.system(size: 24))
                .frame(width: 32, height: 32)

            HStack(spacing: 4) {
                ForEach(0..<3, id: \.self) { i in
                    Circle()
                        .fill(PixelTheme.textSecondary)
                        .frame(width: 6, height: 6)
                        .opacity(0.5)
                        .animation(
                            .easeInOut(duration: 0.6)
                                .repeatForever()
                                .delay(Double(i) * 0.2),
                            value: appState.isSageLoading
                        )
                }
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 12)
            .background(
                RoundedRectangle(cornerRadius: 12)
                    .fill(PixelTheme.bgMedium)
            )
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(PixelTheme.cardBorder, lineWidth: 1)
            )

            Spacer(minLength: 48)
        }
    }

    // MARK: - Input Bar

    private var inputBar: some View {
        HStack(spacing: 8) {
            TextField("", text: $inputText, prompt: Text("Demande au Sage...").foregroundStyle(PixelTheme.textSecondary.opacity(0.6)), axis: .vertical)
                .lineLimit(1...4)
                .font(PixelTheme.captionFont)
                .foregroundStyle(PixelTheme.textPrimary)
                .padding(.horizontal, 12)
                .padding(.vertical, 8)
                .background(PixelTheme.bgMedium, in: RoundedRectangle(cornerRadius: 16))
                .overlay(
                    RoundedRectangle(cornerRadius: 16)
                        .stroke(PixelTheme.cardBorder)
                )
                .focused($isInputFocused)

            Button(action: sendMessage) {
                Text("SEND")
                    .font(PixelTheme.microFont)
                    .foregroundStyle(canSend ? PixelTheme.bgDark : PixelTheme.textSecondary)
                    .padding(.horizontal, 14)
                    .padding(.vertical, 8)
                    .background(
                        RoundedRectangle(cornerRadius: 12)
                            .fill(canSend ? PixelTheme.accent : PixelTheme.bgLight)
                    )
            }
            .disabled(!canSend)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background(PixelTheme.bgDark.opacity(0.95).background(.ultraThinMaterial))
    }

    private var canSend: Bool {
        !inputText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && !appState.isSageLoading
    }

    private func sendMessage() {
        let text = inputText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        inputText = ""
        Task {
            await appState.sendSageMessage(text)
        }
    }
}
