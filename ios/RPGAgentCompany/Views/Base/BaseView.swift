import SwiftUI

struct BaseView: View {
    @EnvironmentObject private var appState: AppState
    @State private var selectedBuilding: Building?
    @State private var showMissionBoard = false
    @State private var buildingBounce: String?

    var body: some View {
        NavigationStack {
            ZStack {
                PixelTheme.bgDark.ignoresSafeArea()

                ScrollView(showsIndicators: false) {
                    VStack(spacing: 16) {
                        statusBar
                        villageScene
                        missionsSection
                    }
                    .padding(.horizontal, 16)
                    .padding(.bottom, 24)
                }
            }
            .refreshable { await appState.refreshCompany() }
            .sheet(item: $selectedBuilding) { building in
                BuildingDetailView(building: building)
                    .environmentObject(appState)
            }
            .sheet(isPresented: $showMissionBoard) {
                MissionBoardView()
                    .environmentObject(appState)
            }
        }
    }

    // MARK: - Status bar (top HUD)

    private var statusBar: some View {
        VStack(spacing: 8) {
            HStack {
                Text(appState.company?.name.uppercased() ?? "BASE")
                    .font(PixelTheme.headlineFont)
                    .foregroundStyle(PixelTheme.textPrimary)
                Spacer()
                GemCounter(
                    balance: appState.company?.wallet.creditsBalance ?? 0,
                    cap: appState.company?.wallet.creditsCap ?? 100
                )
            }
            XPBar(
                current: appState.company?.xp ?? 0,
                nextLevel: appState.xpForNextLevel,
                level: appState.company?.level ?? 1
            )
        }
        .pixelCard()
        .padding(.top, 8)
    }

    // MARK: - Village / buildings

    private var villageScene: some View {
        VStack(spacing: 12) {
            Text("— VILLAGE —")
                .font(PixelTheme.captionFont)
                .foregroundStyle(PixelTheme.textSecondary)
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
                ForEach(appState.company?.buildings ?? []) { building in
                    PixelBuildingCard(
                        building: building,
                        isBouncing: buildingBounce == building.id
                    )
                    .onTapGesture {
                        withAnimation(.interpolatingSpring(stiffness: 400, damping: 8)) {
                            buildingBounce = building.id
                        }
                        DispatchQueue.main.asyncAfter(deadline: .now() + 0.2) {
                            buildingBounce = nil
                            selectedBuilding = building
                        }
                    }
                }
            }

            Button(action: { showMissionBoard = true }) {
                HStack {
                    Text("⚙")
                    Text("QG — TOUTES LES QUÊTES")
                        .font(PixelTheme.captionFont)
                }
                .foregroundStyle(PixelTheme.accent)
                .padding(.vertical, 8)
                .frame(maxWidth: .infinity)
                .overlay(
                    RoundedRectangle(cornerRadius: PixelTheme.buttonRadius)
                        .stroke(PixelTheme.accent.opacity(0.4), lineWidth: 1)
                )
            }
        }
    }

    // MARK: - Recent missions

    private var missionsSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("MISSIONS RÉCENTES")
                .font(PixelTheme.captionFont)
                .foregroundStyle(PixelTheme.textSecondary)
            if appState.missions.isEmpty {
                Text("Aucune mission. Tape un bâtiment !")
                    .font(PixelTheme.captionFont)
                    .foregroundStyle(PixelTheme.textSecondary.opacity(0.6))
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 20)
            } else {
                ForEach(appState.missions.prefix(5)) { mission in
                    NavigationLink {
                        if mission.status == "completed", mission.deliverable != nil {
                            LootRevealView(mission: mission)
                        } else {
                            MissionStatusView(mission: mission)
                        }
                    } label: {
                        MissionRow(mission: mission)
                    }
                }
            }
        }
        .pixelCard()
    }
}

// MARK: - Pixel building card

struct PixelBuildingCard: View {
    let building: Building
    var isBouncing: Bool = false

    var body: some View {
        VStack(spacing: 6) {
            ZStack {
                RoundedRectangle(cornerRadius: 6)
                    .fill(agentColor.opacity(0.15))
                    .frame(width: 56, height: 56)
                    .overlay(
                        RoundedRectangle(cornerRadius: 6)
                            .stroke(agentColor.opacity(0.4), lineWidth: 1)
                    )
                Text(agentEmoji)
                    .font(.system(size: 28))
            }
            .scaleEffect(isBouncing ? 1.15 : 1.0)

            Text(building.displayName.uppercased())
                .font(PixelTheme.captionFont)
                .foregroundStyle(PixelTheme.textPrimary)
            Text("LV.\(building.level)")
                .font(PixelTheme.microFont)
                .foregroundStyle(agentColor)
        }
        .frame(maxWidth: .infinity, minHeight: 120)
        .pixelCard(highlighted: isBouncing)
    }

    private var agentEmoji: String {
        switch building.agentType {
        case "builder": return "🏗"
        case "marketer": return "📣"
        case "researcher": return "📚"
        default: return "🏛"
        }
    }

    private var agentColor: Color {
        switch building.agentType {
        case "builder": return PixelTheme.accentBlue
        case "marketer": return PixelTheme.accentPurple
        case "researcher": return PixelTheme.accentGreen
        default: return PixelTheme.accent
        }
    }
}

// MARK: - Mission row

struct MissionRow: View {
    let mission: Mission

    var body: some View {
        HStack(spacing: 8) {
            Text(missionEmoji)
                .font(.system(size: 16))
            VStack(alignment: .leading, spacing: 2) {
                Text(mission.missionType.replacingOccurrences(of: "_", with: " ").uppercased())
                    .font(PixelTheme.captionFont)
                    .foregroundStyle(PixelTheme.textPrimary)
                    .lineLimit(1)
                Text("+\(mission.xpReward) XP")
                    .font(PixelTheme.microFont)
                    .foregroundStyle(PixelTheme.accentGreen)
            }
            Spacer()
            Text(mission.status.uppercased())
                .font(PixelTheme.microFont)
                .foregroundStyle(statusColor)
                .padding(.horizontal, 6)
                .padding(.vertical, 3)
                .background(statusColor.opacity(0.15), in: RoundedRectangle(cornerRadius: 4))
        }
        .padding(.vertical, 4)
    }

    private var missionEmoji: String {
        switch mission.agentType {
        case "builder": return "🏗"
        case "marketer": return "📣"
        default: return "📚"
        }
    }

    private var statusColor: Color {
        switch mission.status {
        case "completed": return PixelTheme.accentGreen
        case "running", "pending": return PixelTheme.accent
        case "failed": return PixelTheme.accentRed
        default: return PixelTheme.textSecondary
        }
    }
}
