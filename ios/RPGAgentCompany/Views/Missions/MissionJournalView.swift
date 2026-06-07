import SwiftUI

struct MissionJournalView: View {
    @EnvironmentObject private var appState: AppState
    @Environment(\.dismiss) private var dismiss
    @State private var selectedTab = 0

    var body: some View {
        NavigationStack {
            ZStack {
                PixelTheme.bgDark.ignoresSafeArea()

                VStack(spacing: 0) {
                    tabBar
                    TabView(selection: $selectedTab) {
                        activityFeedTab.tag(0)
                        documentsTab.tag(1)
                        statsTab.tag(2)
                    }
                    .tabViewStyle(.page(indexDisplayMode: .never))
                }
            }
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .principal) {
                    Text("JOURNAL")
                        .font(PixelTheme.headlineFont)
                        .foregroundStyle(PixelTheme.textPrimary)
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
                await appState.fetchActivityFeed()
            }
        }
    }

    // MARK: - Tab Bar

    private var tabBar: some View {
        HStack(spacing: 0) {
            tabButton("ACTIVITE", index: 0)
            tabButton("DOCS", index: 1)
            tabButton("STATS", index: 2)
        }
        .background(PixelTheme.bgMedium)
    }

    private func tabButton(_ title: String, index: Int) -> some View {
        Button(action: { withAnimation(.easeOut(duration: 0.2)) { selectedTab = index } }) {
            Text(title)
                .font(PixelTheme.microFont)
                .foregroundStyle(selectedTab == index ? PixelTheme.accent : PixelTheme.textSecondary)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 8)
                .overlay(alignment: .bottom) {
                    if selectedTab == index {
                        Rectangle()
                            .fill(PixelTheme.accent)
                            .frame(height: 2)
                    }
                }
        }
    }

    // MARK: - Activity Feed Tab (agent logs from backend)

    private var activityFeedTab: some View {
        ScrollView {
            LazyVStack(spacing: 4) {
                if appState.agentActivityFeed.isEmpty && appState.activityLog.isEmpty {
                    emptyState(text: "Aucune activite recente")
                } else {
                    ForEach(appState.agentActivityFeed) { entry in
                        agentLogRow(entry)
                    }

                    if !appState.activityLog.isEmpty && !appState.agentActivityFeed.isEmpty {
                        Divider()
                            .background(PixelTheme.cardBorder)
                            .padding(.vertical, 8)
                    }

                    ForEach(appState.activityLog) { entry in
                        HStack(alignment: .top, spacing: 8) {
                            Text("▸")
                                .font(PixelTheme.captionFont)
                                .foregroundStyle(PixelTheme.accent)
                            VStack(alignment: .leading, spacing: 2) {
                                Text(entry.message)
                                    .font(PixelTheme.captionFont)
                                    .foregroundStyle(PixelTheme.textPrimary)
                                Text(entry.timestamp, style: .relative)
                                    .font(PixelTheme.microFont)
                                    .foregroundStyle(PixelTheme.textSecondary)
                            }
                            Spacer()
                        }
                        .padding(.horizontal, 12)
                        .padding(.vertical, 4)
                    }
                }
            }
            .padding(.vertical, 12)
        }
        .refreshable {
            await appState.fetchActivityFeed()
        }
    }

    private func agentLogRow(_ entry: ActivityFeedEntry) -> some View {
        HStack(alignment: .top, spacing: 8) {
            agentStatusIcon(entry)

            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: 6) {
                    Text(agentDisplayName(entry.agentType).uppercased())
                        .font(PixelTheme.microFont)
                        .foregroundStyle(agentColor(entry.agentType))
                        .padding(.horizontal, 4)
                        .padding(.vertical, 1)
                        .background(agentColor(entry.agentType).opacity(0.15), in: RoundedRectangle(cornerRadius: 3))

                    if entry.missionStatus == "running" {
                        Text("EN COURS")
                            .font(PixelTheme.microFont)
                            .foregroundStyle(PixelTheme.accent)
                    }
                }

                Text(entry.message)
                    .font(PixelTheme.captionFont)
                    .foregroundStyle(PixelTheme.textPrimary)
                    .lineLimit(2)

                Text(formatRelativeDate(entry.createdAt))
                    .font(PixelTheme.microFont)
                    .foregroundStyle(PixelTheme.textSecondary)
            }

            Spacer()
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 6)
    }

    @ViewBuilder
    private func agentStatusIcon(_ entry: ActivityFeedEntry) -> some View {
        if entry.missionStatus == "running" || entry.step == "agent_started" {
            ProgressView()
                .scaleEffect(0.6)
                .tint(agentColor(entry.agentType))
                .frame(width: 16, height: 16)
        } else if entry.missionStatus == "completed" || entry.step == "completed" {
            Text("✓")
                .font(PixelTheme.captionFont)
                .foregroundStyle(PixelTheme.accentGreen)
                .frame(width: 16)
        } else if entry.missionStatus == "failed" || entry.step == "failed" {
            Text("✕")
                .font(PixelTheme.captionFont)
                .foregroundStyle(PixelTheme.accentRed)
                .frame(width: 16)
        } else {
            Text("▸")
                .font(PixelTheme.captionFont)
                .foregroundStyle(agentColor(entry.agentType))
                .frame(width: 16)
        }
    }

    private func agentDisplayName(_ type: String) -> String {
        switch type {
        case "builder": return "Forgeron"
        case "marketer": return "Agent"
        case "researcher": return "Observateur"
        case "orchestrator": return "Maire"
        case "outreach": return "Messager"
        case "support": return "Aubergiste"
        case "finance": return "Banquier"
        case "content": return "Scribe"
        default: return type
        }
    }

    private func formatRelativeDate(_ dateString: String) -> String {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        guard let date = formatter.date(from: dateString) else {
            let fallback = ISO8601DateFormatter()
            guard let d = fallback.date(from: dateString) else { return dateString }
            return RelativeDateTimeFormatter().localizedString(for: d, relativeTo: Date())
        }
        return RelativeDateTimeFormatter().localizedString(for: date, relativeTo: Date())
    }

    // MARK: - Documents Tab

    private var completedMissions: [Mission] {
        appState.missions.filter { $0.status == "completed" && $0.deliverable != nil }
    }

    private var documentsTab: some View {
        ScrollView {
            LazyVStack(spacing: 10) {
                businessPackHeader

                if completedMissions.isEmpty {
                    emptyState(text: "Aucun document genere")
                } else {
                    ForEach(completedMissions) { mission in
                        documentCard(mission: mission)
                    }
                }
            }
            .padding(12)
        }
    }

    private var businessPackHeader: some View {
        let progress = appState.questChainProgress
        let chainDocs = completedMissions.filter { m in
            appState.questChain.contains { $0.missionType == m.missionType && $0.isCompleted }
        }

        return VStack(alignment: .leading, spacing: 8) {
            Text("DOSSIER ENTREPRISE")
                .font(PixelTheme.captionFont)
                .foregroundStyle(PixelTheme.accent)

            Text(appState.company?.businessType.questChainTitle ?? "QUEST CHAIN")
                .font(PixelTheme.microFont)
                .foregroundStyle(PixelTheme.textSecondary)

            HStack {
                Text("\(progress.completed)/\(progress.total) etapes")
                    .font(PixelTheme.captionFont)
                    .foregroundStyle(PixelTheme.accentGreen)
                Spacer()
                Text("\(chainDocs.count) docs")
                    .font(PixelTheme.microFont)
                    .foregroundStyle(PixelTheme.textSecondary)
            }

            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 2).fill(PixelTheme.bgDark)
                    RoundedRectangle(cornerRadius: 2)
                        .fill(PixelTheme.accentGreen)
                        .frame(width: progress.total > 0
                               ? geo.size.width * CGFloat(progress.completed) / CGFloat(progress.total)
                               : 0)
                }
            }
            .frame(height: 6)
        }
        .pixelCard()
    }

    @State private var expandedDocId: String?

    private func documentCard(mission: Mission) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Button(action: {
                withAnimation(.easeOut(duration: 0.2)) {
                    expandedDocId = expandedDocId == mission.id ? nil : mission.id
                }
            }) {
                HStack {
                    Text(docIcon(for: mission.deliverableFormat))
                        .font(.system(size: 20))
                    VStack(alignment: .leading, spacing: 2) {
                        Text(mission.missionType.replacingOccurrences(of: "_", with: " ").uppercased())
                            .font(PixelTheme.captionFont)
                            .foregroundStyle(PixelTheme.textPrimary)
                        HStack(spacing: 6) {
                            Text(mission.agentType.uppercased())
                                .font(PixelTheme.microFont)
                                .foregroundStyle(agentColor(mission.agentType))
                            Text((mission.deliverableFormat ?? "text").uppercased())
                                .font(PixelTheme.microFont)
                                .foregroundStyle(PixelTheme.accent)
                                .padding(.horizontal, 4)
                                .padding(.vertical, 1)
                                .background(PixelTheme.accent.opacity(0.15), in: RoundedRectangle(cornerRadius: 3))
                        }
                    }
                    Spacer()
                    Text(expandedDocId == mission.id ? "▼" : "▸")
                        .font(PixelTheme.captionFont)
                        .foregroundStyle(PixelTheme.textSecondary)
                }
            }
            .buttonStyle(.plain)

            if expandedDocId == mission.id {
                DeliverableContentBlock(mission: mission)

                HStack(spacing: 8) {
                    Button(action: {
                        if let content = mission.deliverable {
                            UIPasteboard.general.string = content
                            AnalyticsTracker.track("deliverable_copied", properties: [
                                "mission_type": mission.missionType,
                                "source": "journal",
                            ])
                        }
                    }) {
                        Text(DeliverableHelper.copyButtonLabel(for: mission.missionType))
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(PixelButtonStyle(color: PixelTheme.bgLight))

                    ShareLink(item: mission.deliverable ?? "") {
                        Text("PARTAGER")
                            .font(PixelTheme.bodyFont)
                            .foregroundStyle(PixelTheme.bgDark)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 10)
                            .background(PixelTheme.accent, in: RoundedRectangle(cornerRadius: PixelTheme.buttonRadius))
                    }
                }
            }
        }
        .pixelCard()
    }

    private func docIcon(for format: String?) -> String {
        switch format {
        case "html": return "🌐"
        case "json": return "📊"
        default: return "📄"
        }
    }

    private func agentColor(_ type: String) -> Color {
        switch type {
        case "builder": return PixelTheme.accentBlue
        case "marketer": return PixelTheme.accentPurple
        case "researcher": return PixelTheme.accentGreen
        case "orchestrator": return PixelTheme.accent
        case "outreach": return Color(red: 0.95, green: 0.55, blue: 0.20)
        case "support": return Color(red: 0.40, green: 0.80, blue: 0.80)
        case "finance": return Color(red: 0.85, green: 0.75, blue: 0.20)
        case "content": return Color(red: 0.80, green: 0.45, blue: 0.65)
        default: return PixelTheme.textSecondary
        }
    }

    // MARK: - Stats Tab

    private var statsTab: some View {
        ScrollView {
            VStack(spacing: 16) {
                VStack(spacing: 10) {
                    Text("— COMPANY —")
                        .font(PixelTheme.captionFont)
                        .foregroundStyle(PixelTheme.textSecondary)

                    HStack(spacing: 20) {
                        statItem(value: "LV.\(appState.company?.level ?? 1)", label: "NIVEAU", color: PixelTheme.accent)
                        statItem(value: "\(appState.company?.xp ?? 0)", label: "XP", color: PixelTheme.accentGreen)
                        statItem(value: "\(appState.company?.wallet.creditsBalance ?? 0)", label: "CREDITS", color: PixelTheme.accent)
                        statItem(value: "\(appState.dailyStreak)j", label: "STREAK", color: PixelTheme.accentPurple)
                    }
                }
                .pixelCard()

                VStack(spacing: 10) {
                    Text("— MISSIONS —")
                        .font(PixelTheme.captionFont)
                        .foregroundStyle(PixelTheme.textSecondary)

                    HStack(spacing: 20) {
                        statItem(value: "\(completedMissions.count)", label: "TERMINEES", color: PixelTheme.accentGreen)
                        statItem(value: "\(appState.missions.filter { $0.status == "failed" }.count)", label: "ECHOUEES", color: PixelTheme.accentRed)
                        statItem(value: "\(appState.missions.filter { $0.status == "running" || $0.status == "pending" }.count)", label: "EN COURS", color: PixelTheme.accent)
                    }
                }
                .pixelCard()

                VStack(spacing: 10) {
                    Text("— ANALYTICS BETA —")
                        .font(PixelTheme.captionFont)
                        .foregroundStyle(PixelTheme.textSecondary)

                    HStack(spacing: 16) {
                        statItem(value: "\(AnalyticsTracker.eventCount(for: "mission_started"))", label: "LANCES", color: PixelTheme.accent)
                        statItem(value: "\(AnalyticsTracker.eventCount(for: "mission_completed"))", label: "FINIES", color: PixelTheme.accentGreen)
                        statItem(value: "\(AnalyticsTracker.eventCount(for: "deliverable_copied"))", label: "COPIES", color: PixelTheme.accentPurple)
                    }

                    ShareLink(item: AnalyticsTracker.exportJSON()) {
                        Text("EXPORTER EVENTS (JSON)")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(PixelButtonStyle(color: PixelTheme.bgLight))
                }
                .pixelCard()

                VStack(spacing: 10) {
                    Text("— BATIMENTS —")
                        .font(PixelTheme.captionFont)
                        .foregroundStyle(PixelTheme.textSecondary)

                    ForEach(appState.company?.buildings ?? []) { building in
                        HStack {
                            Text(building.displayName)
                                .font(PixelTheme.captionFont)
                                .foregroundStyle(PixelTheme.textPrimary)
                            Spacer()
                            HStack(spacing: 2) {
                                ForEach(0..<building.level, id: \.self) { _ in
                                    Text("★")
                                        .font(PixelTheme.microFont)
                                        .foregroundStyle(PixelTheme.accent)
                                }
                            }
                            Text("NIV.\(building.level)")
                                .font(PixelTheme.microFont)
                                .foregroundStyle(agentColor(building.agentType))
                        }
                    }
                }
                .pixelCard()
            }
            .padding(12)
        }
    }

    private func statItem(value: String, label: String, color: Color) -> some View {
        VStack(spacing: 2) {
            Text(value)
                .font(PixelTheme.headlineFont)
                .foregroundStyle(color)
            Text(label)
                .font(PixelTheme.microFont)
                .foregroundStyle(PixelTheme.textSecondary)
        }
    }

    private func emptyState(text: String) -> some View {
        VStack(spacing: 8) {
            Text("📜")
                .font(.system(size: 32))
            Text(text.uppercased())
                .font(PixelTheme.captionFont)
                .foregroundStyle(PixelTheme.textSecondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 40)
    }
}
