import Foundation

/// Pokémon GBA coastal town — 64×40 tiles, landscape orientation.
/// Reproduces the reference screenshot: mountains → ocean → trees → town → trees → beach.
enum VillageMap {
    static let width  = 64
    static let height = 40

    // MARK: - Tile types — each maps to a real Figma-exported PNG

    enum Tile: String {
        // Base terrain
        case g0 = "base_property_1_0"   // grass (green)
        case g1 = "base_property_1_1"   // grass variant
        case g2 = "base_property_1_2"   // sand / light ground
        case g3 = "base_property_1_3"   // darker ground
        case g4 = "base_property_1_4"   // clay/brown
        case g5 = "base_property_1_5"   // dark earth
        case tg = "base_property_1_tall_grass"

        // Mountains (brown)
        case mtl = "mtn_position_tl_top_left_type_brown_invert_false"
        case mtr = "mtn_position_tr_top_right_type_brown_invert_false"
        case mbl = "mtn_position_bl_bottom_left_type_brown_invert_false"
        case mbr = "mtn_position_br_bottom_right_type_brown_invert_false"
        case mtp = "mtn_position_up_top_type_brown_invert_false"
        case mbt = "mtn_position_down_bottom_type_brown_invert_false"
        case mle = "mtn_position_left_left_type_brown_invert_false"
        case mri = "mtn_position_right_right_type_brown_invert_false"
        case mcc = "mtn_position_center_center_type_brown_invert_false"

        // Still water (edges with grass base)
        case wcc = "swater_position_center_center_corner_base_none_invert_false"
        case wtp = "swater_position_up_top_corner_base_none_invert_false"
        case wbt = "swater_position_down_bottom_corner_base_none_invert_false"
        case wle = "swater_position_left_left_corner_base_none_invert_false"
        case wri = "swater_position_right_right_corner_base_none_invert_false"
        case wtl = "swater_position_tl_top_left_corner_base_grass_invert_false"
        case wtr = "swater_position_tr_top_right_corner_base_grass_invert_false"
        case wbl = "swater_position_bl_bottom_left_corner_base_grass_invert_false"
        case wbr = "swater_position_br_bottom_right_corner_base_grass_invert_false"
        // Water corners with mountain base
        case wmtl = "swater_position_tl_top_left_corner_base_mountains_invert_false"
        case wmtr = "swater_position_tr_top_right_corner_base_mountains_invert_false"
        // Inverted water corners
        case witl = "swater_position_tl_top_left_corner_base_none_invert_true"
        case witr = "swater_position_tr_top_right_corner_base_none_invert_true"
        case wibl = "swater_position_bl_bottom_left_corner_base_none_invert_true"
        case wibr = "swater_position_br_bottom_right_corner_base_none_invert_true"

        // Path (ground type for sandy paths in town)
        case pcc = "path_type_ground_position_center_center_invert_false"
        case ptp = "path_type_ground_position_up_top_invert_false"
        case pbt = "path_type_ground_position_down_bottom_invert_false"
        case ple = "path_type_ground_position_left_left_invert_false"
        case pri = "path_type_ground_position_right_right_invert_false"
        case ptl = "path_type_ground_position_tl_top_left_invert_false"
        case ptr = "path_type_ground_position_tr_top_right_invert_false"
        case pbl = "path_type_ground_position_bl_bottom_left_invert_false"
        case pbr = "path_type_ground_position_br_bottom_right_invert_false"

        // Path (grass type for grass-to-ground transitions)
        case gptl = "path_type_grass_position_tl_top_left_invert_false"
        case gptr = "path_type_grass_position_tr_top_right_invert_false"
        case gpbl = "path_type_grass_position_bl_bottom_left_invert_false"
        case gpbr = "path_type_grass_position_br_bottom_right_invert_false"
        case gptp = "path_type_grass_position_up_top_invert_false"
        case gpbt = "path_type_grass_position_down_bottom_invert_false"
        case gple = "path_type_grass_position_left_left_invert_false"
        case gpri = "path_type_grass_position_right_right_invert_false"
        case gpcc = "path_type_grass_position_center_center_invert_false"

        var isSolid: Bool {
            switch self {
            case .wcc, .wtp, .wbt, .wle, .wri, .wtl, .wtr, .wbl, .wbr,
                 .wmtl, .wmtr, .witl, .witr, .wibl, .wibr,
                 .mtl, .mtr, .mbl, .mbr, .mtp, .mbt, .mle, .mri, .mcc:
                return true
            default:
                return false
            }
        }
    }

    // MARK: - Building definitions

    struct BuildingDef: Identifiable {
        let id: String
        let agentType: String
        let name: String
        let asset: String
        let tileX: Int
        let tileY: Int
        let pixelW: Int
        let pixelH: Int
        var widthTiles: Int { (pixelW + 31) / 32 }
        var heightTiles: Int { (pixelH + 31) / 32 }
        let doorTileX: Int
        let doorTileY: Int
    }

    struct NPCDef: Identifiable {
        let id: String
        let name: String
        let tileX: Int
        let tileY: Int
        let dialogue: String
        let agentType: String?
        var patrolRadius: Int = 0
    }

    struct Decoration {
        let asset: String
        let tileX: Int
        let tileY: Int
        let pixelW: Int
        let pixelH: Int
    }

    struct LockedZone {
        let id: String
        let requiredLevel: Int
        let minCol: Int
        let maxCol: Int
        let minRow: Int
        let maxRow: Int
    }

    struct DialoguePage {
        let text: String
        let choices: [(label: String, action: DialogueAction)]?
    }

    enum DialogueAction {
        case nextPage
        case close
        case openQuests
        case openSageChat
    }

    static let lockedZones: [LockedZone] = [
        LockedZone(id: "beach_south", requiredLevel: 3,
                   minCol: 0, maxCol: 63, minRow: 30, maxRow: 37),
    ]

    // MARK: - Map grid (64 × 40)
    // Layout: mountains → ocean → tree line → ONE horizontal town alley → tree line → beach

    static let grid: [[Tile]] = buildGrid()

    private static func buildGrid() -> [[Tile]] {
        var g = Array(repeating: Array(repeating: Tile.g0, count: width), count: height)

        // === Rows 0-4: Mountain ridge (5 rows thick) ===
        for c in 0..<width {
            g[0][c] = c == 0 ? .mtl : c == width-1 ? .mtr : .mtp
        }
        for r in 1...3 {
            for c in 0..<width {
                g[r][c] = c == 0 ? .mle : c == width-1 ? .mri : .mcc
            }
        }
        for c in 0..<width {
            g[4][c] = c == 0 ? .mbl : c == width-1 ? .mbr : .mbt
        }

        // === Row 5: Mountain → Water transition ===
        for c in 0..<width {
            g[5][c] = c == 0 ? .wmtl : c == width-1 ? .wmtr : .wtp
        }

        // === Rows 6-11: Open ocean ===
        for r in 6...11 {
            for c in 0..<width {
                g[r][c] = c == 0 ? .wle : c == width-1 ? .wri : .wcc
            }
        }

        // === Row 12: Water → Grass transition ===
        for c in 0..<width {
            g[12][c] = c == 0 ? .wbl : c == width-1 ? .wbr : .wbt
        }

        // === Row 13: Sand strip by the shore ===
        for c in 0..<width { g[13][c] = .g2 }

        // === Rows 14-16: Upper tree line + grass buffer (trees placed as decorations) ===

        // === Rows 17-20: Building zone — sandy ground under building clusters ===
        // Left cluster (QG + Agence)
        for r in 18...20 { for c in 3...15 { g[r][c] = .g2 } }
        // Center (Observatoire)
        for r in 18...20 { for c in 21...27 { g[r][c] = .g2 } }
        // Right cluster (Forge + houses)
        for r in 18...20 { for c in 32...55 { g[r][c] = .g2 } }

        // === Rows 21-23: MAIN HORIZONTAL ALLEY (one wide path, full width) ===
        for c in 1...60 {
            g[21][c] = c == 1 ? .ptl : c == 60 ? .ptr : .ptp
            g[22][c] = c == 1 ? .ple : c == 60 ? .pri : .pcc
            g[23][c] = c == 1 ? .pbl : c == 60 ? .pbr : .pbt
        }

        // === Rows 24-25: Grass south of alley ===

        // === Rows 26-27: Lower tree line (trees as decorations) ===

        // === Rows 28-29: Grass ===

        // === Rows 30-37: Beach / sand ===
        for r in 30...37 { for c in 0..<width { g[r][c] = .g2 } }

        // === Rows 38-39: Bottom water ===
        for c in 0..<width {
            g[38][c] = c == 0 ? .wtl : c == width-1 ? .wtr : .wtp
        }
        for c in 0..<width {
            g[39][c] = c == 0 ? .wle : c == width-1 ? .wri : .wcc
        }

        return g
    }

    // MARK: - Buildings

    static let buildings: [BuildingDef] = [
        // === LEFT CLUSTER (2 large buildings) ===
        BuildingDef(id: "hq", agentType: "orchestrator", name: "QG",
                    asset: "bld_type_mansion",
                    tileX: 4, tileY: 18, pixelW: 112, pixelH: 96,
                    doorTileX: 6, doorTileY: 20),
        BuildingDef(id: "market", agentType: "marketer", name: "AGENCE",
                    asset: "bld_type_gym",
                    tileX: 11, tileY: 18, pixelW: 96, pixelH: 88,
                    doorTileX: 12, doorTileY: 20),
        // === CENTER (1 prominent building) ===
        BuildingDef(id: "lab", agentType: "researcher", name: "OBSERVATOIRE",
                    asset: "bld_type_oaks_lab",
                    tileX: 22, tileY: 18, pixelW: 112, pixelH: 72,
                    doorTileX: 24, doorTileY: 20),
        // === RIGHT CLUSTER (5 smaller buildings / houses) ===
        BuildingDef(id: "forge", agentType: "builder", name: "FORGE",
                    asset: "bld_type_pokemart",
                    tileX: 33, tileY: 19, pixelW: 64, pixelH: 64,
                    doorTileX: 34, doorTileY: 20),
        BuildingDef(id: "post_office", agentType: "outreach", name: "POSTE",
                    asset: "bld_type_house_1",
                    tileX: 37, tileY: 18, pixelW: 80, pixelH: 72,
                    doorTileX: 38, doorTileY: 20),
        BuildingDef(id: "inn", agentType: "support", name: "AUBERGE",
                    asset: "bld_type_house_3",
                    tileX: 42, tileY: 19, pixelW: 80, pixelH: 56,
                    doorTileX: 43, doorTileY: 20),
        BuildingDef(id: "bank", agentType: "finance", name: "BANQUE",
                    asset: "bld_type_house_5",
                    tileX: 47, tileY: 19, pixelW: 64, pixelH: 56,
                    doorTileX: 48, doorTileY: 20),
        BuildingDef(id: "workshop", agentType: "content", name: "ATELIER",
                    asset: "bld_type_house_2",
                    tileX: 51, tileY: 19, pixelW: 96, pixelH: 56,
                    doorTileX: 52, doorTileY: 20),
    ]

    // MARK: - Trees (placed as 64×96 sprites = 2×3 tiles)

    static let trees: [Decoration] = {
        var t: [Decoration] = []
        // Upper tree line (row 14, dense, full width — no gap since no vertical path)
        for c in stride(from: 0, to: width, by: 2) {
            t.append(Decoration(asset: "plant_type_tree", tileX: c, tileY: 14, pixelW: 64, pixelH: 96))
        }
        // Lower tree line (row 26, dense, full width)
        for c in stride(from: 0, to: width, by: 2) {
            t.append(Decoration(asset: "plant_type_tree", tileX: c, tileY: 26, pixelW: 64, pixelH: 96))
        }
        // Trees filling gap between left cluster and center (cols 16-20)
        for c in stride(from: 16, to: 22, by: 2) {
            t.append(Decoration(asset: "plant_type_tree", tileX: c, tileY: 17, pixelW: 64, pixelH: 96))
        }
        // Trees filling gap between center and right cluster (cols 28-32)
        for c in stride(from: 28, to: 33, by: 2) {
            t.append(Decoration(asset: "plant_type_tree", tileX: c, tileY: 17, pixelW: 64, pixelH: 96))
        }
        // Edge trees on left and right of town
        t.append(Decoration(asset: "plant_type_tree", tileX: 0, tileY: 17, pixelW: 64, pixelH: 96))
        t.append(Decoration(asset: "plant_type_tree", tileX: 56, tileY: 17, pixelW: 64, pixelH: 96))
        t.append(Decoration(asset: "plant_type_tree", tileX: 58, tileY: 17, pixelW: 64, pixelH: 96))
        t.append(Decoration(asset: "plant_type_tree", tileX: 60, tileY: 17, pixelW: 64, pixelH: 96))
        t.append(Decoration(asset: "plant_type_tree", tileX: 62, tileY: 17, pixelW: 64, pixelH: 96))
        // Scattered trees in lower grass/beach transition
        for pos in [(4, 29), (12, 29), (50, 29), (58, 29)] {
            t.append(Decoration(asset: "plant_type_tree", tileX: pos.0, tileY: pos.1, pixelW: 64, pixelH: 96))
        }
        return t
    }()

    // MARK: - Flowers / Rocks decorations

    static let decorations: [Decoration] = [
        // Flowers along the building fronts
        Decoration(asset: "plant_type_flowers_red", tileX: 9, tileY: 20, pixelW: 32, pixelH: 32),
        Decoration(asset: "plant_type_flowers_white", tileX: 15, tileY: 20, pixelW: 32, pixelH: 32),
        Decoration(asset: "plant_type_flowers_red", tileX: 27, tileY: 20, pixelW: 32, pixelH: 32),
        Decoration(asset: "plant_type_flowers_red_and_white", tileX: 36, tileY: 20, pixelW: 32, pixelH: 32),
        Decoration(asset: "plant_type_flowers_red_and_white", tileX: 46, tileY: 20, pixelW: 32, pixelH: 32),
        Decoration(asset: "plant_type_flowers_white", tileX: 54, tileY: 20, pixelW: 32, pixelH: 32),
        // Flowers south of alley
        Decoration(asset: "plant_type_flowers_red", tileX: 10, tileY: 24, pixelW: 32, pixelH: 32),
        Decoration(asset: "plant_type_flowers_red_and_white", tileX: 35, tileY: 24, pixelW: 32, pixelH: 32),
        Decoration(asset: "plant_type_flowers_white", tileX: 50, tileY: 24, pixelW: 32, pixelH: 32),
        // Bushes in tree gaps
        Decoration(asset: "plant_type_bush", tileX: 19, tileY: 20, pixelW: 32, pixelH: 32),
        Decoration(asset: "plant_type_bush", tileX: 30, tileY: 20, pixelW: 32, pixelH: 32),
        // Beach decorations
        Decoration(asset: "plant_type_flower_patch", tileX: 8, tileY: 32, pixelW: 32, pixelH: 32),
        Decoration(asset: "plant_type_flower_patch", tileX: 52, tileY: 32, pixelW: 32, pixelH: 32),
        Decoration(asset: "rock_grey_false_type_1", tileX: 15, tileY: 34, pixelW: 32, pixelH: 32),
        Decoration(asset: "rock_grey_false_type_2", tileX: 45, tileY: 34, pixelW: 32, pixelH: 32),
        Decoration(asset: "rock_grey_false_type_3", tileX: 30, tileY: 33, pixelW: 32, pixelH: 32),
    ]

    // MARK: - NPCs

    static let npcs: [NPCDef] = [
        NPCDef(id: "npc_orchestrator", name: "Maire", tileX: 6, tileY: 21,
               dialogue: "Bienvenue au QG ! Je coordonne tous les agents et definis la strategie.",
               agentType: "orchestrator", patrolRadius: 0),
        NPCDef(id: "npc_marketer", name: "Agent", tileX: 12, tileY: 21,
               dialogue: "Salut ! A l'Agence, on ecrit tes pubs, analyse la concurrence et planifie tes campagnes ads.",
               agentType: "marketer", patrolRadius: 0),
        NPCDef(id: "npc_researcher", name: "Observateur", tileX: 24, tileY: 21,
               dialogue: "L'Observatoire analyse les donnees du marche. Confie-moi une mission de recherche !",
               agentType: "researcher", patrolRadius: 0),
        NPCDef(id: "npc_guide", name: "Le Sage", tileX: 30, tileY: 22,
               dialogue: "Bienvenue, fondateur ! Explore le village. Chaque batiment abrite un agent specialise.",
               agentType: nil, patrolRadius: 0),
        NPCDef(id: "npc_builder", name: "Forgeron", tileX: 34, tileY: 21,
               dialogue: "Bienvenue a la Forge ! Je code des landings, des sites et des briefs produit.",
               agentType: "builder", patrolRadius: 0),
        NPCDef(id: "npc_outreach", name: "Messager", tileX: 38, tileY: 21,
               dialogue: "Au Bureau de Poste, je gere la prospection et les emails de ta boite.",
               agentType: "outreach", patrolRadius: 0),
        NPCDef(id: "npc_support", name: "Aubergiste", tileX: 43, tileY: 21,
               dialogue: "Bienvenue a l'Auberge ! Je reponds aux clients et gere le support.",
               agentType: "support", patrolRadius: 0),
        NPCDef(id: "npc_finance", name: "Banquier", tileX: 48, tileY: 21,
               dialogue: "A la Banque, je suis les revenus, les depenses et le budget de ta company.",
               agentType: "finance", patrolRadius: 0),
        NPCDef(id: "npc_content", name: "Scribe", tileX: 52, tileY: 21,
               dialogue: "A l'Atelier, je cree des articles, des visuels et des documents pour ta marque.",
               agentType: "content", patrolRadius: 0),
    ]

    // MARK: - Quest-chain-aware NPC dialogues

    static func dialoguePages(
        for npc: NPCDef,
        hasRunningMission: Bool,
        hasCompletedMission: Bool,
        isFirstVisit: Bool,
        missionCount: Int,
        justCompletedMission: Bool = false,
        questChain: [QuestStep] = [],
        businessType: BusinessType = .ecommerce
    ) -> [DialoguePage] {

        // --- Guide / Le Sage (no agentType) ---
        guard let agentType = npc.agentType else {
            return guideDialogue(isFirstVisit: isFirstVisit, questChain: questChain)
        }

        // --- Building NPC with quest chain context ---
        let buildingName = buildingDisplayName(for: agentType)
        let buildingDesc = buildingDescription(for: agentType)

        let myStep = questChain.first { $0.agentType == agentType && !$0.isCompleted }
        let myCompletedSteps = questChain.filter { $0.agentType == agentType && $0.isCompleted }

        if justCompletedMission {
            let nextStep = questChain.first { $0.isAvailable && $0.agentType != agentType }
            var pages: [DialoguePage] = [
                DialoguePage(text: "Bravo ! La mission est terminee.", choices: nil),
                DialoguePage(text: "Ton livrable est pret. Approche-toi du batiment pour le recuperer.", choices: nil),
            ]
            if let next = nextStep {
                let nextBuilding = buildingDisplayName(for: next.agentType)
                let nextNPC = npcName(for: next.agentType)
                pages.append(DialoguePage(
                    text: "Prochaine etape : va voir \(nextNPC) a \(nextBuilding) pour \"\(next.title)\".",
                    choices: [("RECUPERER", .openQuests), ("COMPRIS", .close)]
                ))
            } else {
                pages.append(DialoguePage(text: "Reviens me voir si tu as besoin d'autre chose.", choices: [
                    ("RECUPERER", .openQuests), ("PLUS TARD", .close)
                ]))
            }
            return pages
        }

        if hasCompletedMission {
            let nextStep = questChain.first { $0.isAvailable && $0.agentType != agentType }
            if let next = nextStep {
                let nextBuilding = buildingDisplayName(for: next.agentType)
                let nextNPC = npcName(for: next.agentType)
                return [
                    DialoguePage(text: "Tu as deja recupere ton livrable. Bien joue !", choices: nil),
                    DialoguePage(
                        text: "Prochaine etape : va voir \(nextNPC) a \(nextBuilding) pour \"\(next.title)\".",
                        choices: [("COMPRIS", .close)]
                    ),
                ]
            } else {
                return [
                    DialoguePage(text: "Bien joue, ta mission ici est terminee !", choices: [("COMPRIS", .close)]),
                ]
            }
        }

        if hasRunningMission || (myStep?.isRunning == true) {
            return [
                DialoguePage(text: "Patience... je travaille sur ta mission.", choices: nil),
                DialoguePage(text: "Je te previens des que c'est pret !", choices: [
                    ("D'ACCORD", .close)
                ])
            ]
        }

        if let step = myStep, step.isAvailable {
            return [
                DialoguePage(text: "Je suis le responsable de \(buildingName).", choices: nil),
                DialoguePage(text: buildingDesc, choices: nil),
                DialoguePage(text: "Etape \(step.stepNumber) : \"\(step.title)\"", choices: nil),
                DialoguePage(text: step.description, choices: [
                    ("LANCER", .openQuests),
                    ("PLUS TARD", .close)
                ])
            ]
        }

        if let step = myStep, step.isLocked {
            let prereqs = prerequisiteSteps(for: step.stepNumber, in: questChain, businessType: businessType)
            let prereqNames = prereqs.map { s in
                let npc = npcName(for: s.agentType)
                let bld = buildingDisplayName(for: s.agentType)
                return "\(npc) a \(bld) (\"\(s.title)\")"
            }
            var pages: [DialoguePage] = [
                DialoguePage(text: "Je suis le responsable de \(buildingName).", choices: nil),
                DialoguePage(text: buildingDesc, choices: nil),
                DialoguePage(text: "Pour l'instant, c'est trop tot pour lancer \"\(step.title)\".", choices: nil),
            ]
            if !prereqNames.isEmpty {
                let targets = prereqNames.joined(separator: ", puis ")
                pages.append(DialoguePage(
                    text: "Tu dois d'abord completer : \(targets).",
                    choices: [("COMPRIS", .close)]
                ))
            } else {
                pages.append(DialoguePage(text: "Reviens quand tu auras progresse dans les etapes precedentes.", choices: [
                    ("COMPRIS", .close)
                ]))
            }
            return pages
        }

        if !myCompletedSteps.isEmpty && myStep == nil {
            return [
                DialoguePage(text: "Toutes mes etapes sont terminees. Bon travail !", choices: nil),
                DialoguePage(text: "Tu veux revoir les quetes disponibles ici ?", choices: [
                    ("VOIR LES QUETES", .openQuests),
                    ("PLUS TARD", .close)
                ])
            ]
        }

        if isFirstVisit {
            return [
                DialoguePage(text: "Je suis le responsable de \(buildingName).", choices: nil),
                DialoguePage(text: buildingDesc, choices: nil),
                DialoguePage(text: "Tu veux voir les quetes disponibles ?", choices: [
                    ("VOIR LES QUETES", .openQuests),
                    ("PLUS TARD", .close)
                ])
            ]
        }

        return [
            DialoguePage(text: npc.dialogue, choices: nil),
            DialoguePage(text: "J'ai des quetes pour toi.", choices: [
                ("VOIR LES QUETES", .openQuests),
                ("PLUS TARD", .close)
            ])
        ]
    }

    // MARK: - Guide (Le Sage) dialogue

    private static func guideDialogue(isFirstVisit: Bool, questChain: [QuestStep]) -> [DialoguePage] {
        if isFirstVisit {
            let firstAvailable = questChain.first { $0.isAvailable }
            var pages: [DialoguePage] = [
                DialoguePage(text: "Bienvenue, jeune fondateur ! Je suis Le Sage du village.", choices: nil),
                DialoguePage(text: "Ce village est ta base d'operations. Chaque batiment abrite un agent specialise qui va t'aider a lancer ta marque.", choices: nil),
                DialoguePage(text: "Pour reussir, tu devras completer des quetes dans un ordre precis. Chaque etape debloque la suivante.", choices: nil),
            ]
            if let step = firstAvailable {
                let targetNPC = npcName(for: step.agentType)
                let targetBuilding = buildingDisplayName(for: step.agentType)
                pages.append(DialoguePage(
                    text: "Commence par aller voir \(targetNPC) a \(targetBuilding). Il va \(step.title.lowercased()).",
                    choices: nil
                ))
            }
            pages.append(DialoguePage(
                text: "Tu peux aussi me poser des questions a tout moment. Bonne chance !",
                choices: [("C'EST PARTI !", .close), ("PARLER AU SAGE", .openSageChat)]
            ))
            return pages
        }

        let completed = questChain.filter { $0.isCompleted }.count
        let total = questChain.count
        let runningSteps = questChain.filter { $0.isRunning }
        let availableSteps = questChain.filter { $0.isAvailable }
        let lastCompleted = questChain.last { $0.isCompleted }

        var pages: [DialoguePage] = []

        if total > 0 {
            let pct = Int(Double(completed) / Double(total) * 100)
            pages.append(DialoguePage(text: "Ah, te revoila ! Tu as complete \(completed)/\(total) etapes (\(pct)%).", choices: nil))
        }

        if let last = lastCompleted {
            pages.append(DialoguePage(
                text: "Bravo pour \"\(last.title)\" ! Ca avance bien.",
                choices: nil
            ))
        }

        if !runningSteps.isEmpty {
            let names = runningSteps.map { "\(npcName(for: $0.agentType)) a \(buildingDisplayName(for: $0.agentType))" }
            let runningDesc = names.joined(separator: " et ")
            pages.append(DialoguePage(
                text: "\(runningDesc) travaille\(runningSteps.count > 1 ? "nt" : "") en ce moment. Patiente un peu.",
                choices: nil
            ))
            if !availableSteps.isEmpty {
                let step = availableSteps[0]
                pages.append(DialoguePage(
                    text: "En attendant, tu peux aller voir \(npcName(for: step.agentType)) a \(buildingDisplayName(for: step.agentType)) pour \"\(step.title)\".",
                    choices: [("QUETES", .openQuests), ("PARLER AU SAGE", .openSageChat), ("FERMER", .close)]
                ))
            } else {
                pages.append(DialoguePage(
                    text: "Reviens me voir quand c'est termine, je te dirai la suite !",
                    choices: [("PARLER AU SAGE", .openSageChat), ("D'ACCORD", .close)]
                ))
            }
        } else if !availableSteps.isEmpty {
            let step = availableSteps[0]
            let targetNPC = npcName(for: step.agentType)
            let targetBuilding = buildingDisplayName(for: step.agentType)
            pages.append(DialoguePage(
                text: "Prochaine etape : va voir \(targetNPC) a \(targetBuilding) pour \"\(step.title)\".",
                choices: nil
            ))
            if availableSteps.count > 1 {
                let others = availableSteps.dropFirst().map { "\"\($0.title)\" chez \(npcName(for: $0.agentType))" }
                pages.append(DialoguePage(
                    text: "Tu peux aussi lancer : \(others.joined(separator: ", ")).",
                    choices: [("QUETES", .openQuests), ("PARLER AU SAGE", .openSageChat), ("FERMER", .close)]
                ))
            } else {
                pages.append(DialoguePage(
                    text: "Dirige-toi vers \(targetBuilding), \(targetNPC) t'attend !",
                    choices: [("QUETES", .openQuests), ("PARLER AU SAGE", .openSageChat), ("FERMER", .close)]
                ))
            }
        } else if completed == total && total > 0 {
            pages.append(DialoguePage(
                text: "Incroyable ! Tu as complete toutes les etapes. Ta marque est officiellement lancee !",
                choices: nil
            ))
            pages.append(DialoguePage(
                text: "Je suis fier de toi, fondateur. Le village entier celebre ton succes !",
                choices: [("PARLER AU SAGE", .openSageChat), ("MERCI !", .close)]
            ))
        } else {
            pages.append(DialoguePage(
                text: "Continue a explorer le village et parle aux habitants.",
                choices: [("PARLER AU SAGE", .openSageChat), ("MERCI", .close)]
            ))
        }

        return pages
    }

    // MARK: - Helpers for dialogue context

    private static func prerequisiteSteps(for stepNumber: Int, in chain: [QuestStep], businessType: BusinessType = .ecommerce) -> [QuestStep] {
        let prereqNumbers = businessType.dependencyGraph[stepNumber] ?? []
        return chain.filter { prereqNumbers.contains($0.stepNumber) && !$0.isCompleted }
    }

    static func buildingDisplayName(for agentType: String) -> String {
        switch agentType {
        case "builder": return "la Forge"
        case "marketer": return "l'Agence"
        case "researcher": return "l'Observatoire"
        case "orchestrator": return "le QG"
        case "outreach": return "le Bureau de Poste"
        case "support": return "l'Auberge"
        case "finance": return "la Banque"
        case "content": return "l'Atelier"
        default: return "ce batiment"
        }
    }

    private static func buildingDescription(for agentType: String) -> String {
        switch agentType {
        case "builder": return "Ici, on code des landing pages, des sites et des briefs produit."
        case "marketer": return "A l'Agence, on ecrit tes pubs, analyse la concurrence et planifie tes campagnes ads."
        case "researcher": return "A l'Observatoire, on analyse le marche, les concurrents et on trouve les meilleurs fournisseurs."
        case "orchestrator": return "Au QG, on coordonne la strategie, le tracking et l'optimisation globale."
        case "outreach": return "Au Bureau de Poste, on gere la prospection et les emails de ta boite."
        case "support": return "A l'Auberge, on met en place le support client, la FAQ et les templates de reponse."
        case "finance": return "A la Banque, on gere les paiements, le budget et la tresorerie."
        case "content": return "A l'Atelier, on cree la charte graphique, les visuels et les pubs creatives."
        default: return "Un batiment specialise du village."
        }
    }

    private static func npcName(for agentType: String) -> String {
        switch agentType {
        case "builder": return "le Forgeron"
        case "marketer": return "l'Agent"
        case "researcher": return "l'Observateur"
        case "orchestrator": return "le Maire"
        case "outreach": return "le Messager"
        case "support": return "l'Aubergiste"
        case "finance": return "le Banquier"
        case "content": return "le Scribe"
        default: return "l'habitant"
        }
    }

    static let spawnX = 30
    static let spawnY = 22

    // MARK: - Filtering by active agent types

    static func activeBuildings(for agentTypes: Set<String>) -> [BuildingDef] {
        buildings.filter { agentTypes.contains($0.agentType) }
    }

    static func activeNPCs(for agentTypes: Set<String>) -> [NPCDef] {
        npcs.filter { npc in
            guard let at = npc.agentType else { return true }
            return agentTypes.contains(at)
        }
    }
}
