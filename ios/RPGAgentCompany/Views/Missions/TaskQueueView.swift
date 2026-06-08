import SwiftUI

// MARK: - Shared agent color helper

func agentTypeColor(_ agentType: String) -> Color {
    switch agentType {
    case "builder":     return PixelTheme.accentBlue
    case "marketer":    return PixelTheme.accentPurple
    case "researcher":  return PixelTheme.accentGreen
    case "orchestrator": return PixelTheme.accent
    case "browser":     return Color(red: 0.2, green: 0.7, blue: 0.9)
    case "data":        return Color(red: 0.4, green: 0.8, blue: 0.6)
    case "ops":         return Color(red: 0.7, green: 0.5, blue: 0.3)
    case "growth":      return Color(red: 0.9, green: 0.7, blue: 0.1)
    case "content":     return Color(red: 0.9, green: 0.5, blue: 0.2)
    case "support":     return Color(red: 0.3, green: 0.8, blue: 0.8)
    case "finance":     return Color(red: 0.2, green: 0.85, blue: 0.4)
    case "outreach":    return Color(red: 0.8, green: 0.3, blue: 0.6)
    default:            return PixelTheme.textSecondary
    }
}

// MARK: - TaskQueueView

struct TaskQueueView: View {
    @EnvironmentObject private var appState: AppState
    let companyId: String

    @State private var selectedTab: QueueTab = .queue
    @State private var showCreateTask = false
    @State private var actionLoading: String?
    @State private var errorMessage: String?
    @State private var editingTask: Mission?

    enum QueueTab { case queue, recurring }

    var body: some View {
        ZStack {
            PixelTheme.bgDark.ignoresSafeArea()

            VStack(spacing: 0) {
                queueHeader
                    .padding(.horizontal)
                    .padding(.vertical, 10)
                    .background(PixelTheme.bgMedium)

                tabBar

                if appState.isLoading && appState.taskQueue.isEmpty && selectedTab == .queue {
                    Spacer()
                    ProgressView().tint(PixelTheme.accent)
                    Spacer()
                } else if selectedTab == .queue {
                    queueList
                } else {
                    RecurringTasksView(companyId: companyId)
                        .environmentObject(appState)
                }
            }

            if let error = errorMessage {
                VStack {
                    Spacer()
                    Text(error)
                        .font(PixelTheme.captionFont)
                        .foregroundStyle(PixelTheme.textPrimary)
                        .padding()
                        .background(PixelTheme.accentRed.opacity(0.9))
                        .clipShape(RoundedRectangle(cornerRadius: 8))
                        .padding()
                        .onTapGesture { errorMessage = nil }
                }
            }
        }
        .sheet(isPresented: $showCreateTask) {
            CreateTaskSheet(companyId: companyId)
                .environmentObject(appState)
        }
        .sheet(item: $editingTask) { task in
            EditTaskSheet(task: task)
                .environmentObject(appState)
        }
        .task {
            await appState.fetchTaskQueue()
            await appState.fetchRecurringMissions()
        }
        .refreshable {
            await appState.fetchTaskQueue()
            await appState.fetchRecurringMissions()
        }
    }

    private var tabBar: some View {
        HStack(spacing: 0) {
            tabButton("FILE", tab: .queue, count: appState.taskQueue.count)
            tabButton("RÉCURRENTES", tab: .recurring, count: appState.recurringMissions.count)
        }
        .background(PixelTheme.bgMedium)
    }

    private func tabButton(_ label: String, tab: QueueTab, count: Int) -> some View {
        Button { selectedTab = tab } label: {
            VStack(spacing: 4) {
                HStack(spacing: 4) {
                    Text(label).font(PixelTheme.microFont)
                    if count > 0 {
                        Text("\(count)")
                            .font(PixelTheme.microFont)
                            .foregroundStyle(PixelTheme.bgDark)
                            .padding(.horizontal, 5)
                            .padding(.vertical, 1)
                            .background(selectedTab == tab ? PixelTheme.accent : PixelTheme.textSecondary, in: Capsule())
                    }
                }
                .foregroundStyle(selectedTab == tab ? PixelTheme.accent : PixelTheme.textSecondary)
                Rectangle()
                    .fill(selectedTab == tab ? PixelTheme.accent : Color.clear)
                    .frame(height: 2)
            }
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 8)
    }

    // MARK: - Header

    private var queueHeader: some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text("FILE D'ATTENTE")
                    .font(PixelTheme.headlineFont)
                    .foregroundStyle(PixelTheme.accent)
                Text("\(appState.taskQueue.count) tâche(s) en attente")
                    .font(PixelTheme.captionFont)
                    .foregroundStyle(PixelTheme.textSecondary)
            }
            Spacer()
            HStack(spacing: 8) {
                // Auto-pilot toggle
                autoPilotToggle

                // Credits badge
                if let sub = appState.subscription {
                    HStack(spacing: 3) {
                        Image(systemName: "bolt.fill").font(.system(size: 10))
                        Text("\(sub.totalCredits) CR")
                            .font(PixelTheme.captionFont)
                    }
                    .foregroundStyle(sub.isLowCredits ? PixelTheme.accentRed : PixelTheme.accent)
                }
                Button(action: { showCreateTask = true }) {
                    Label("Nouvelle", systemImage: "plus")
                        .font(PixelTheme.captionFont)
                        .padding(.horizontal, 10)
                        .padding(.vertical, 6)
                        .background(PixelTheme.accent)
                        .foregroundStyle(PixelTheme.bgDark)
                        .clipShape(RoundedRectangle(cornerRadius: 6))
                }
            }
        }
    }

    private var autoPilotToggle: some View {
        let isOn = appState.company?.autoPilot ?? false
        return Button {
            Task { await appState.toggleAutoPilot() }
        } label: {
            HStack(spacing: 4) {
                Image(systemName: isOn ? "bolt.fill" : "bolt.slash")
                    .font(.system(size: 9, weight: .bold))
                Text("AUTO")
                    .font(PixelTheme.microFont)
            }
            .foregroundStyle(isOn ? PixelTheme.bgDark : PixelTheme.textSecondary)
            .padding(.horizontal, 8)
            .padding(.vertical, 5)
            .background(isOn ? PixelTheme.accentGreen : PixelTheme.bgMedium)
            .clipShape(RoundedRectangle(cornerRadius: 6))
            .overlay(
                RoundedRectangle(cornerRadius: 6)
                    .stroke(isOn ? PixelTheme.accentGreen : PixelTheme.cardBorder, lineWidth: 0.5)
            )
        }
    }

    // MARK: - Queue list (supports drag reorder)

    private var queueList: some View {
        List {
            if appState.taskQueue.isEmpty {
                Section {
                    emptyQueueView
                        .listRowBackground(Color.clear)
                        .listRowInsets(EdgeInsets())
                        .listRowSeparator(.hidden)
                }
            } else {
                Section(header: queueSectionHeader) {
                    ForEach(Array(appState.taskQueue.enumerated()), id: \.element.id) { index, task in
                        TaskQueueRow(
                            task: task,
                            position: index + 1,
                            isActionLoading: actionLoading == task.id,
                            onMoveToTop: { await moveToTop(task: task) },
                            onReject: { await reject(task: task) },
                            onExecute: { await execute(task: task) }
                        )
                        .swipeActions(edge: .leading, allowsFullSwipe: false) {
                            Button { editingTask = task } label: {
                                Label("Modifier", systemImage: "pencil")
                            }
                            .tint(PixelTheme.accentBlue)
                        }
                        .listRowInsets(EdgeInsets())
                        .listRowBackground(Color.clear)
                        .listRowSeparatorTint(PixelTheme.cardBorder)
                    }
                    .onMove { from, to in
                        appState.taskQueue.move(fromOffsets: from, toOffset: to)
                        Task { await syncQueueOrder() }
                    }
                }
            }

            let history = Array(appState.missions.filter { !$0.isPending }.prefix(15))
            if !history.isEmpty {
                Section(header: historySectionHeader(count: history.count)) {
                    ForEach(history) { mission in
                        TaskHistoryRow(mission: mission)
                            .listRowInsets(EdgeInsets())
                            .listRowBackground(Color.clear)
                            .listRowSeparatorTint(PixelTheme.cardBorder)
                    }
                }
            }
        }
        .listStyle(.plain)
        .background(PixelTheme.bgDark)
        .environment(\.editMode, .constant(.active))
        .scrollContentBackground(.hidden)
    }

    private var queueSectionHeader: some View {
        HStack {
            Text("EN ATTENTE")
                .font(PixelTheme.microFont)
                .foregroundStyle(PixelTheme.textSecondary)
            Text("(\(appState.taskQueue.count))")
                .font(PixelTheme.microFont)
                .foregroundStyle(PixelTheme.textSecondary.opacity(0.6))
            Spacer()
            Image(systemName: "line.3.horizontal")
                .font(.system(size: 10))
                .foregroundStyle(PixelTheme.textSecondary.opacity(0.5))
            Text("glisser pour ordonner")
                .font(PixelTheme.microFont)
                .foregroundStyle(PixelTheme.textSecondary.opacity(0.5))
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 8)
        .background(PixelTheme.bgMedium.opacity(0.5))
        .textCase(nil)
        .listRowInsets(EdgeInsets())
    }

    private func historySectionHeader(count: Int) -> some View {
        HStack {
            Text("HISTORIQUE")
                .font(PixelTheme.microFont)
                .foregroundStyle(PixelTheme.textSecondary)
            Text("(\(count))")
                .font(PixelTheme.microFont)
                .foregroundStyle(PixelTheme.textSecondary.opacity(0.6))
            Spacer()
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 8)
        .background(PixelTheme.bgMedium.opacity(0.5))
        .textCase(nil)
        .listRowInsets(EdgeInsets())
    }

    // MARK: - Empty state

    private var emptyQueueView: some View {
        VStack(spacing: 16) {
            Image(systemName: "checkmark.circle.fill")
                .font(.system(size: 48))
                .foregroundStyle(PixelTheme.accentGreen.opacity(0.6))
                .padding(.top, 40)
            Text("File vide")
                .font(PixelTheme.headlineFont)
                .foregroundStyle(PixelTheme.textSecondary)
            Text("Demandez au Sage de créer des tâches\nou utilisez le bouton + ci-dessus.")
                .font(PixelTheme.captionFont)
                .foregroundStyle(PixelTheme.textSecondary)
                .multilineTextAlignment(.center)
        }
        .padding(.vertical, 32)
    }

    // MARK: - Actions

    private func syncQueueOrder() async {
        for (index, task) in appState.taskQueue.enumerated() {
            _ = try? await APIClient.shared.reorderTask(missionId: task.id, position: index + 1)
        }
    }

    private func moveToTop(task: Mission) async {
        actionLoading = task.id
        defer { actionLoading = nil }
        do {
            let updated = try await APIClient.shared.moveTaskToTop(missionId: task.id)
            await MainActor.run {
                if let idx = appState.taskQueue.firstIndex(where: { $0.id == task.id }) {
                    appState.taskQueue.remove(at: idx)
                    appState.taskQueue.insert(updated, at: 0)
                }
            }
        } catch {
            errorMessage = "Impossible de déplacer la tâche"
        }
    }

    private func reject(task: Mission) async {
        actionLoading = task.id
        defer { actionLoading = nil }
        do {
            try await APIClient.shared.rejectTask(missionId: task.id, reason: "user_cancelled")
            await MainActor.run {
                appState.taskQueue.removeAll { $0.id == task.id }
            }
        } catch {
            errorMessage = "Impossible de rejeter la tâche"
        }
    }

    private func execute(task: Mission) async {
        actionLoading = task.id
        defer { actionLoading = nil }
        do {
            let updated = try await APIClient.shared.executeTask(missionId: task.id)
            await MainActor.run {
                // Task is now RUNNING — remove from pending queue
                appState.taskQueue.removeAll { $0.id == task.id }
                // Add to missions list if not present
                if !appState.missions.contains(where: { $0.id == updated.id }) {
                    appState.missions.insert(updated, at: 0)
                }
            }
            await appState.fetchSubscription()
        } catch {
            if let apiErr = error as? APIError, case .http(let code, _) = apiErr, code == 402 {
                errorMessage = "Plus de crédits. Achetez un pack dans Crédits & Plans."
            } else {
                errorMessage = "Impossible de lancer la tâche"
            }
        }
    }
}

// MARK: - TaskQueueRow

struct TaskQueueRow: View {
    let task: Mission
    let position: Int
    let isActionLoading: Bool
    let onMoveToTop: () async -> Void
    let onReject: () async -> Void
    let onExecute: () async -> Void

    private var isCEO: Bool { task.source == "ceo_proposal" }

    var body: some View {
        VStack(spacing: 0) {
            // CEO banner
            if isCEO {
                HStack(spacing: 6) {
                    Image(systemName: "brain.head.profile")
                        .font(.system(size: 9))
                    Text("PROPOSITION CEO")
                        .font(PixelTheme.microFont)
                    Spacer()
                    Text("Recommandé")
                        .font(PixelTheme.microFont)
                        .opacity(0.7)
                }
                .foregroundStyle(PixelTheme.accentPurple)
                .padding(.horizontal, 16)
                .padding(.vertical, 5)
                .background(PixelTheme.accentPurple.opacity(0.12))
            }

            HStack(spacing: 12) {
                // Position badge
                Text("#\(position)")
                    .font(PixelTheme.microFont)
                    .foregroundStyle(PixelTheme.textSecondary)
                    .frame(width: 24)

                // Agent color dot
                Circle()
                    .fill(agentColor)
                    .frame(width: 8, height: 8)

                // Task info
                VStack(alignment: .leading, spacing: 3) {
                    HStack(spacing: 6) {
                        if !isCEO {
                            Image(systemName: task.taskSourceIcon)
                                .font(.system(size: 9))
                                .foregroundStyle(PixelTheme.textSecondary)
                            Text(task.taskSourceDisplay)
                                .font(PixelTheme.microFont)
                                .foregroundStyle(PixelTheme.textSecondary)
                            Text("·")
                                .font(PixelTheme.microFont)
                                .foregroundStyle(PixelTheme.textSecondary)
                        }
                        Text(task.agentType.uppercased())
                            .font(PixelTheme.microFont)
                            .foregroundStyle(agentColor.opacity(0.9))
                    }
                    Text(task.displayTitle)
                        .font(PixelTheme.captionFont)
                        .foregroundStyle(PixelTheme.textPrimary)
                        .lineLimit(2)
                }

                Spacer()

                // Actions
                if isActionLoading {
                    ProgressView().tint(PixelTheme.accent).scaleEffect(0.7)
                } else {
                    HStack(spacing: 4) {
                        if position > 1 {
                            Button {
                                Task { await onMoveToTop() }
                            } label: {
                                Image(systemName: "arrow.up.to.line")
                                    .font(.system(size: 11, weight: .bold))
                                    .foregroundStyle(PixelTheme.accentGreen)
                                    .frame(width: 28, height: 28)
                                    .background(PixelTheme.accentGreen.opacity(0.15))
                                    .clipShape(RoundedRectangle(cornerRadius: 6))
                            }
                        }
                        Button {
                            Task { await onReject() }
                        } label: {
                            Image(systemName: "xmark")
                                .font(.system(size: 11, weight: .bold))
                                .foregroundStyle(PixelTheme.accentRed)
                                .frame(width: 28, height: 28)
                                .background(PixelTheme.accentRed.opacity(0.15))
                                .clipShape(RoundedRectangle(cornerRadius: 6))
                        }
                    }
                }
            }
            .padding(.horizontal, 16)
            .padding(.top, 12)
            .padding(.bottom, 8)

            // Run link button (Polsia equivalent)
            Button {
                Task { await onExecute() }
            } label: {
                HStack(spacing: 6) {
                    Image(systemName: "play.fill").font(.system(size: 9))
                    Text("LANCER — 1 CR")
                }
                .font(PixelTheme.microFont)
                .foregroundStyle(isCEO ? PixelTheme.accentPurple : agentColor)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 6)
                .background((isCEO ? PixelTheme.accentPurple : agentColor).opacity(0.08))
                .overlay(
                    RoundedRectangle(cornerRadius: 0)
                        .frame(height: 1)
                        .foregroundStyle((isCEO ? PixelTheme.accentPurple : agentColor).opacity(0.2)),
                    alignment: .top
                )
            }
        }
        .background(isCEO ? PixelTheme.accentPurple.opacity(0.05) : PixelTheme.bgDark)
        .overlay(
            Rectangle()
                .fill(isCEO ? PixelTheme.accentPurple : Color.clear)
                .frame(width: 3),
            alignment: .leading
        )
    }

    private var agentColor: Color {
        agentTypeColor(task.agentType)
    }
}

// MARK: - TaskHistoryRow

struct TaskHistoryRow: View {
    let mission: Mission

    var body: some View {
        HStack(spacing: 12) {
            statusIcon
                .frame(width: 24)

            VStack(alignment: .leading, spacing: 2) {
                Text(mission.displayTitle)
                    .font(PixelTheme.captionFont)
                    .foregroundStyle(mission.isRejected ? PixelTheme.textSecondary : PixelTheme.textPrimary)
                    .lineLimit(1)
                Text(mission.agentType.uppercased())
                    .font(PixelTheme.microFont)
                    .foregroundStyle(PixelTheme.textSecondary)
            }

            Spacer()

            Text(statusLabel)
                .font(PixelTheme.microFont)
                .foregroundStyle(statusColor)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
        .background(PixelTheme.bgDark.opacity(mission.isRejected ? 0.5 : 1))
    }

    private var statusIcon: some View {
        Group {
            if mission.isCompleted {
                Image(systemName: "checkmark.circle.fill").foregroundStyle(PixelTheme.accentGreen)
            } else if mission.isFailed {
                Image(systemName: "xmark.circle.fill").foregroundStyle(PixelTheme.accentRed)
            } else if mission.isRejected {
                Image(systemName: "minus.circle.fill").foregroundStyle(PixelTheme.textSecondary)
            } else if mission.isRunning {
                Image(systemName: "clock.fill").foregroundStyle(PixelTheme.accent)
            } else {
                Image(systemName: "circle").foregroundStyle(PixelTheme.textSecondary)
            }
        }
        .font(.system(size: 14))
    }

    private var statusLabel: String {
        if mission.isCompleted { return "DONE" }
        if mission.isFailed { return "FAILED" }
        if mission.isRejected { return "REJETÉ" }
        if mission.isRunning { return "EN COURS" }
        return ""
    }

    private var statusColor: Color {
        if mission.isCompleted { return PixelTheme.accentGreen }
        if mission.isFailed { return PixelTheme.accentRed }
        if mission.isRejected { return PixelTheme.textSecondary }
        return PixelTheme.accent
    }
}

// MARK: - CreateTaskSheet

struct CreateTaskSheet: View {
    let companyId: String
    @EnvironmentObject private var appState: AppState
    @Environment(\.dismiss) private var dismiss

    @State private var taskTitle = ""
    @State private var taskDescription = ""
    @State private var selectedAgent: String? = nil
    @State private var isCreating = false
    @State private var errorMessage: String?

    private let agents = [
        ("builder", "Forge", "hammer.fill"),
        ("marketer", "Ads", "megaphone.fill"),
        ("researcher", "Labo", "magnifyingglass"),
        ("orchestrator", "CEO", "brain.head.profile"),
        ("browser", "Browser", "safari.fill"),
        ("data", "Data", "chart.bar.fill"),
        ("ops", "Ops", "server.rack"),
        ("growth", "Growth", "arrow.up.right"),
        ("content", "Contenu", "pencil.and.outline"),
        ("support", "Support", "message.fill"),
        ("outreach", "Outreach", "envelope.fill"),
        ("finance", "Finance", "dollarsign.circle.fill"),
    ]

    var body: some View {
        NavigationStack {
            ZStack {
                PixelTheme.bgDark.ignoresSafeArea()

                ScrollView {
                    VStack(spacing: 20) {
                        titleField
                        descriptionField
                        agentPicker
                        if let error = errorMessage {
                            Text(error).font(PixelTheme.captionFont).foregroundStyle(PixelTheme.accentRed)
                        }
                        createButton
                    }
                    .padding()
                }
            }
            .navigationTitle("Nouvelle Tâche")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Annuler") { dismiss() }
                        .foregroundStyle(PixelTheme.textSecondary)
                }
            }
        }
    }

    private var titleField: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("TITRE").font(PixelTheme.microFont).foregroundStyle(PixelTheme.textSecondary)
            TextField("Ex : Diagnostiquer les Meta Ads", text: $taskTitle)
                .font(PixelTheme.bodyFont)
                .foregroundStyle(PixelTheme.textPrimary)
                .padding()
                .background(PixelTheme.bgMedium)
                .clipShape(RoundedRectangle(cornerRadius: 8))
                .overlay(RoundedRectangle(cornerRadius: 8).stroke(PixelTheme.cardBorder, lineWidth: 0.5))
        }
    }

    private var descriptionField: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("DESCRIPTION (OPTIONNEL)").font(PixelTheme.microFont).foregroundStyle(PixelTheme.textSecondary)
            TextField("Décris ce que l'agent doit faire...", text: $taskDescription, axis: .vertical)
                .lineLimit(3...6)
                .font(PixelTheme.captionFont)
                .foregroundStyle(PixelTheme.textPrimary)
                .padding()
                .background(PixelTheme.bgMedium)
                .clipShape(RoundedRectangle(cornerRadius: 8))
                .overlay(RoundedRectangle(cornerRadius: 8).stroke(PixelTheme.cardBorder, lineWidth: 0.5))
        }
    }

    private var agentPicker: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("AGENT (AUTO SI VIDE)").font(PixelTheme.microFont).foregroundStyle(PixelTheme.textSecondary)
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 8) {
                ForEach(agents, id: \.0) { id, name, icon in
                    Button {
                        selectedAgent = selectedAgent == id ? nil : id
                    } label: {
                        HStack(spacing: 6) {
                            Image(systemName: icon).font(.system(size: 12))
                            Text(name).font(PixelTheme.captionFont)
                        }
                        .foregroundStyle(selectedAgent == id ? PixelTheme.bgDark : PixelTheme.textPrimary)
                        .padding(.vertical, 8)
                        .frame(maxWidth: .infinity)
                        .background(selectedAgent == id ? PixelTheme.accent : PixelTheme.bgMedium)
                        .clipShape(RoundedRectangle(cornerRadius: 6))
                        .overlay(RoundedRectangle(cornerRadius: 6).stroke(PixelTheme.cardBorder, lineWidth: 0.5))
                    }
                }
            }
        }
    }

    private var createButton: some View {
        VStack(spacing: 6) {
            Button {
                Task { await createTask() }
            } label: {
                HStack {
                    if isCreating {
                        ProgressView().tint(PixelTheme.bgDark).scaleEffect(0.8)
                    }
                    Text(isCreating ? "AJOUT EN COURS..." : "AJOUTER À LA QUEUE")
                }
                .frame(maxWidth: .infinity)
            }
            .buttonStyle(PixelButtonStyle(color: taskTitle.isEmpty ? PixelTheme.textSecondary : PixelTheme.accentGreen))
            .disabled(taskTitle.trimmingCharacters(in: .whitespaces).isEmpty || isCreating)

            Text("0 CR maintenant · 1 CR débité à l'exécution")
                .font(PixelTheme.microFont)
                .foregroundStyle(PixelTheme.textSecondary)
        }
    }

    private func createTask() async {
        isCreating = true
        errorMessage = nil
        defer { isCreating = false }
        do {
            let mission = try await APIClient.shared.createFreeformTask(
                companyId: companyId,
                title: taskTitle.trimmingCharacters(in: .whitespaces),
                description: taskDescription,
                agentType: selectedAgent
            )
            await MainActor.run {
                appState.taskQueue.append(mission)
                appState.taskQueue.sort { ($0.queueOrder ?? 999) < ($1.queueOrder ?? 999) }
                dismiss()
            }
            await appState.fetchSubscription()
        } catch {
            if let apiErr = error as? APIError, case .http(let code, _) = apiErr, code == 402 {
                errorMessage = "Plus de crédits. Achetez un pack dans Crédits & Plans."
            } else {
                errorMessage = "Impossible de créer la tâche : \(error.localizedDescription)"
            }
        }
    }
}

// MARK: - EditTaskSheet

struct EditTaskSheet: View {
    let task: Mission
    @EnvironmentObject private var appState: AppState
    @Environment(\.dismiss) private var dismiss

    @State private var title: String
    @State private var description: String
    @State private var isSaving = false
    @State private var errorMessage: String?

    init(task: Mission) {
        self.task = task
        _title = State(initialValue: task.displayTitle)
        _description = State(initialValue: task.description ?? "")
    }

    var body: some View {
        NavigationStack {
            ZStack {
                PixelTheme.bgDark.ignoresSafeArea()
                VStack(spacing: 20) {
                    VStack(alignment: .leading, spacing: 6) {
                        Text("TITRE").font(PixelTheme.microFont).foregroundStyle(PixelTheme.textSecondary)
                        TextField("Titre de la tâche", text: $title)
                            .font(PixelTheme.bodyFont)
                            .foregroundStyle(PixelTheme.textPrimary)
                            .padding()
                            .background(PixelTheme.bgMedium)
                            .clipShape(RoundedRectangle(cornerRadius: 8))
                            .overlay(RoundedRectangle(cornerRadius: 8).stroke(PixelTheme.cardBorder, lineWidth: 0.5))
                    }

                    VStack(alignment: .leading, spacing: 6) {
                        Text("DESCRIPTION").font(PixelTheme.microFont).foregroundStyle(PixelTheme.textSecondary)
                        TextField("Description...", text: $description, axis: .vertical)
                            .lineLimit(3...6)
                            .font(PixelTheme.captionFont)
                            .foregroundStyle(PixelTheme.textPrimary)
                            .padding()
                            .background(PixelTheme.bgMedium)
                            .clipShape(RoundedRectangle(cornerRadius: 8))
                            .overlay(RoundedRectangle(cornerRadius: 8).stroke(PixelTheme.cardBorder, lineWidth: 0.5))
                    }

                    if let error = errorMessage {
                        Text(error).font(PixelTheme.captionFont).foregroundStyle(PixelTheme.accentRed)
                    }

                    Button {
                        Task { await save() }
                    } label: {
                        HStack {
                            if isSaving { ProgressView().tint(PixelTheme.bgDark).scaleEffect(0.8) }
                            Text(isSaving ? "SAUVEGARDE..." : "SAUVEGARDER")
                        }
                        .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(PixelButtonStyle(color: title.isEmpty ? PixelTheme.textSecondary : PixelTheme.accentBlue))
                    .disabled(title.isEmpty || isSaving)

                    Spacer()
                }
                .padding()
            }
            .navigationTitle("Modifier la tâche")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Annuler") { dismiss() }.foregroundStyle(PixelTheme.textSecondary)
                }
            }
        }
    }

    private func save() async {
        isSaving = true
        errorMessage = nil
        defer { isSaving = false }
        do {
            let updated = try await APIClient.shared.editTask(
                missionId: task.id,
                title: title.trimmingCharacters(in: .whitespaces),
                description: description
            )
            await MainActor.run {
                if let idx = appState.taskQueue.firstIndex(where: { $0.id == task.id }) {
                    appState.taskQueue[idx] = updated
                }
                dismiss()
            }
        } catch {
            errorMessage = "Impossible de modifier la tâche"
        }
    }
}

// MARK: - RecurringTasksView

struct RecurringTasksView: View {
    @EnvironmentObject private var appState: AppState
    let companyId: String

    @State private var showCreateSheet = false

    var body: some View {
        ScrollView {
            LazyVStack(spacing: 0) {
                createButton
                    .padding()

                if appState.recurringMissions.isEmpty {
                    VStack(spacing: 12) {
                        Image(systemName: "arrow.clockwise.circle")
                            .font(.system(size: 40))
                            .foregroundStyle(PixelTheme.textSecondary.opacity(0.4))
                            .padding(.top, 32)
                        Text("Aucune tâche récurrente")
                            .font(PixelTheme.captionFont)
                            .foregroundStyle(PixelTheme.textSecondary)
                        Text("Automatisez des missions répétitives\n(analyses, rapports, monitoring...)")
                            .font(PixelTheme.microFont)
                            .foregroundStyle(PixelTheme.textSecondary.opacity(0.7))
                            .multilineTextAlignment(.center)
                    }
                    .padding()
                } else {
                    ForEach(appState.recurringMissions) { rm in
                        RecurringMissionRow(rm: rm) {
                            Task { await appState.deleteRecurringMission(id: rm.id) }
                        }
                        Divider().background(PixelTheme.cardBorder).padding(.leading, 16)
                    }
                }
            }
            .padding(.bottom, 32)
        }
        .sheet(isPresented: $showCreateSheet) {
            CreateRecurringSheet(companyId: companyId)
                .environmentObject(appState)
        }
    }

    private var createButton: some View {
        Button { showCreateSheet = true } label: {
            HStack(spacing: 6) {
                Image(systemName: "plus.circle.fill")
                Text("PROGRAMMER UNE TÂCHE RÉCURRENTE")
            }
            .font(PixelTheme.captionFont)
            .frame(maxWidth: .infinity)
        }
        .buttonStyle(PixelButtonStyle(color: PixelTheme.accentBlue))
    }
}

// MARK: - RecurringMissionRow

struct RecurringMissionRow: View {
    let rm: RecurringMission
    let onDelete: () -> Void

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: "arrow.clockwise")
                .font(.system(size: 14))
                .foregroundStyle(PixelTheme.accentBlue)
                .frame(width: 24)

            VStack(alignment: .leading, spacing: 3) {
                Text(rm.displayTitle)
                    .font(PixelTheme.captionFont)
                    .foregroundStyle(PixelTheme.textPrimary)
                    .lineLimit(1)
                Text(rm.frequencyLabel)
                    .font(PixelTheme.microFont)
                    .foregroundStyle(PixelTheme.textSecondary)
                if let next = rm.nextRunAt {
                    Text("Prochaine : \(next.formatted(date: .abbreviated, time: .shortened))")
                        .font(PixelTheme.microFont)
                        .foregroundStyle(PixelTheme.accentBlue.opacity(0.8))
                }
            }

            Spacer()

            Button(action: onDelete) {
                Image(systemName: "trash")
                    .font(.system(size: 12))
                    .foregroundStyle(PixelTheme.accentRed)
                    .frame(width: 28, height: 28)
                    .background(PixelTheme.accentRed.opacity(0.12))
                    .clipShape(RoundedRectangle(cornerRadius: 6))
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
        .background(PixelTheme.bgDark)
    }
}

// MARK: - CreateRecurringSheet

struct CreateRecurringSheet: View {
    let companyId: String
    @EnvironmentObject private var appState: AppState
    @Environment(\.dismiss) private var dismiss

    @State private var missionType = ""
    @State private var frequency = "weekly"
    @State private var hourUtc = 9
    @State private var dayOfWeek = 1
    @State private var dayOfMonth = 1
    @State private var isCreating = false
    @State private var errorMessage: String?

    private let frequencies = ["daily", "weekly", "monthly"]
    private let commonMissions = [
        "market_research", "competitor_analysis", "ads_performance_report",
        "content_calendar", "seo_audit", "customer_feedback_analysis",
    ]

    var body: some View {
        NavigationStack {
            ZStack {
                PixelTheme.bgDark.ignoresSafeArea()
                ScrollView {
                    VStack(spacing: 20) {
                        missionTypePicker
                        frequencyPicker
                        timingPicker
                        if let error = errorMessage {
                            Text(error).font(PixelTheme.captionFont).foregroundStyle(PixelTheme.accentRed)
                        }
                        createButton
                    }
                    .padding()
                }
            }
            .navigationTitle("Tâche Récurrente")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Annuler") { dismiss() }.foregroundStyle(PixelTheme.textSecondary)
                }
            }
        }
    }

    private var missionTypePicker: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("TYPE DE MISSION").font(PixelTheme.microFont).foregroundStyle(PixelTheme.textSecondary)
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 8) {
                ForEach(commonMissions, id: \.self) { mt in
                    Button { missionType = mt } label: {
                        Text(mt.replacingOccurrences(of: "_", with: " ").capitalized)
                            .font(PixelTheme.microFont)
                            .multilineTextAlignment(.center)
                            .foregroundStyle(missionType == mt ? PixelTheme.bgDark : PixelTheme.textPrimary)
                            .padding(8)
                            .frame(maxWidth: .infinity)
                            .background(missionType == mt ? PixelTheme.accentBlue : PixelTheme.bgMedium)
                            .clipShape(RoundedRectangle(cornerRadius: 6))
                    }
                }
            }
        }
    }

    private var frequencyPicker: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("FRÉQUENCE").font(PixelTheme.microFont).foregroundStyle(PixelTheme.textSecondary)
            HStack(spacing: 8) {
                ForEach(frequencies, id: \.self) { f in
                    Button { frequency = f } label: {
                        Text(f.uppercased())
                            .font(PixelTheme.microFont)
                            .foregroundStyle(frequency == f ? PixelTheme.bgDark : PixelTheme.textPrimary)
                            .padding(.vertical, 8)
                            .frame(maxWidth: .infinity)
                            .background(frequency == f ? PixelTheme.accentBlue : PixelTheme.bgMedium)
                            .clipShape(RoundedRectangle(cornerRadius: 6))
                    }
                }
            }
        }
    }

    private var timingPicker: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("HEURE (UTC)").font(PixelTheme.microFont).foregroundStyle(PixelTheme.textSecondary)
            Stepper("\(hourUtc)h00 UTC", value: $hourUtc, in: 0...23)
                .font(PixelTheme.captionFont)
                .foregroundStyle(PixelTheme.textPrimary)

            if frequency == "weekly" {
                Text("JOUR DE LA SEMAINE (0=Lun)").font(PixelTheme.microFont).foregroundStyle(PixelTheme.textSecondary)
                Stepper("Jour \(dayOfWeek)", value: $dayOfWeek, in: 0...6)
                    .font(PixelTheme.captionFont)
                    .foregroundStyle(PixelTheme.textPrimary)
            } else if frequency == "monthly" {
                Text("JOUR DU MOIS").font(PixelTheme.microFont).foregroundStyle(PixelTheme.textSecondary)
                Stepper("Jour \(dayOfMonth)", value: $dayOfMonth, in: 1...28)
                    .font(PixelTheme.captionFont)
                    .foregroundStyle(PixelTheme.textPrimary)
            }
        }
        .padding()
        .background(PixelTheme.bgMedium)
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }

    private var createButton: some View {
        Button {
            Task { await create() }
        } label: {
            HStack {
                if isCreating { ProgressView().tint(PixelTheme.bgDark).scaleEffect(0.8) }
                Text(isCreating ? "CRÉATION..." : "PROGRAMMER")
            }
            .frame(maxWidth: .infinity)
        }
        .buttonStyle(PixelButtonStyle(color: missionType.isEmpty ? PixelTheme.textSecondary : PixelTheme.accentBlue))
        .disabled(missionType.isEmpty || isCreating)
    }

    private func create() async {
        isCreating = true
        errorMessage = nil
        defer { isCreating = false }
        await appState.createRecurringMission(
            missionType: missionType,
            frequency: frequency,
            dayOfWeek: frequency == "weekly" ? dayOfWeek : nil,
            dayOfMonth: frequency == "monthly" ? dayOfMonth : nil,
            hourUtc: hourUtc
        )
        dismiss()
    }
}
