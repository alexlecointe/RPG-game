import SpriteKit

struct GameCallbacks {
    var onBuildingEnter: ((VillageMap.BuildingDef) -> Void)?
    var onNPCInteract: ((VillageMap.NPCDef) -> Void)?
    var onCollectLoot: ((String) -> Void)?
    var onDailyChest: (() -> Void)?
    var onNearSage: ((Bool) -> Void)?
}

enum BuildingMissionState {
    case idle
    case running
    case completed(missionId: String)
}

final class GameScene: SKScene {
    let player = PlayerSprite()
    private let joystick = VirtualJoystick()
    private var actionButton: SKNode!
    var callbacks = GameCallbacks()

    private let ts = TilesetManager.tileSize  // 32

    private var buildingStates: [String: BuildingMissionState] = [:]
    private var buildingEmitters: [String: SKEmitterNode] = [:]
    private var buildingIndicators: [String: SKNode] = [:]
    private var npcSprites: [String: SKSpriteNode] = [:]
    private var dailyChestNode: SKSpriteNode?
    var playerLevel: Int = 1
    var activeAgentTypes: Set<String> = VillageMap.polisiaBuildingAgents
    private var lockedZoneOverlays: [SKNode] = []
    private var wasNearSage = false
    private var wasNearInteractable = false

    var activeBuildings: [VillageMap.BuildingDef] {
        VillageMap.activeBuildings(for: activeAgentTypes)
    }

    var activeNPCs: [VillageMap.NPCDef] {
        VillageMap.activeNPCs(for: activeAgentTypes)
    }

    override func didMove(to view: SKView) {
        backgroundColor = UIColor(red: 0.28, green: 0.50, blue: 0.81, alpha: 1)
        buildTileMap()
        placeDecorations()
        placeBuildings()
        placeNPCs()
        spawnPlayer()
        setupCamera()
        setupJoystick()
        setupActionButton()
        setupLockedZones()
    }

    // MARK: - Mission status updates from AppState

    func updateBuildingMissionState(buildingId: String, state: BuildingMissionState) {
        buildingStates[buildingId] = state

        guard let bld = activeBuildings.first(where: { $0.id == buildingId }) else { return }
        let buildingSprite = childNode(withName: "building_\(buildingId)")
        guard let sprite = buildingSprite as? SKSpriteNode else { return }

        let w = CGFloat(bld.pixelW)
        let indicatorPos = CGPoint(
            x: sprite.position.x + w / 2,
            y: sprite.position.y + 16
        )

        switch state {
        case .running:
            removeIndicator(for: buildingId)
            let emitter = createSmokeEmitter()
            emitter.position = indicatorPos
            emitter.zPosition = 200
            addChild(emitter)
            buildingEmitters[buildingId] = emitter

            let bar = createProgressBar()
            bar.position = CGPoint(x: indicatorPos.x, y: sprite.position.y - 4)
            bar.zPosition = 200
            bar.name = "bar_\(buildingId)"
            addChild(bar)
            buildingIndicators[buildingId] = bar
            animateProgressBar(bar)

        case .completed:
            removeIndicator(for: buildingId)
            let excl = createCompletionIndicator()
            excl.position = indicatorPos
            excl.zPosition = 200
            excl.name = "indicator_\(buildingId)"
            addChild(excl)
            buildingIndicators[buildingId] = excl

        case .idle:
            removeIndicator(for: buildingId)
        }
    }

    private func removeIndicator(for buildingId: String) {
        buildingEmitters[buildingId]?.removeFromParent()
        buildingEmitters.removeValue(forKey: buildingId)
        buildingIndicators[buildingId]?.removeFromParent()
        buildingIndicators.removeValue(forKey: buildingId)
    }

    private func createSmokeEmitter() -> SKEmitterNode {
        let emitter = SKEmitterNode()
        emitter.particleBirthRate = 8
        emitter.numParticlesToEmit = 0
        emitter.particleLifetime = 1.5
        emitter.particleLifetimeRange = 0.5
        emitter.emissionAngle = .pi / 2
        emitter.emissionAngleRange = .pi / 4
        emitter.particleSpeed = 15
        emitter.particleSpeedRange = 5
        emitter.particleAlpha = 0.6
        emitter.particleAlphaRange = 0.2
        emitter.particleAlphaSpeed = -0.4
        emitter.particleScale = 0.15
        emitter.particleScaleRange = 0.05
        emitter.particleScaleSpeed = 0.1
        emitter.particleColor = .lightGray
        emitter.particleColorBlendFactor = 1.0
        emitter.particleBlendMode = .alpha
        return emitter
    }

    private func createProgressBar() -> SKNode {
        let container = SKNode()
        let bgBar = SKShapeNode(rectOf: CGSize(width: 30, height: 4), cornerRadius: 2)
        bgBar.fillColor = UIColor(white: 0, alpha: 0.7)
        bgBar.strokeColor = .clear
        container.addChild(bgBar)

        let fill = SKShapeNode(rectOf: CGSize(width: 1, height: 4), cornerRadius: 2)
        fill.fillColor = UIColor(red: 1, green: 0.78, blue: 0.20, alpha: 1)
        fill.strokeColor = .clear
        fill.position = CGPoint(x: -14.5, y: 0)
        fill.name = "fill"
        container.addChild(fill)
        return container
    }

    private func animateProgressBar(_ bar: SKNode) {
        guard let fill = bar.childNode(withName: "fill") as? SKShapeNode else { return }
        let grow = SKAction.customAction(withDuration: 3.0) { node, elapsed in
            let progress = elapsed / 3.0
            let path = CGPath(
                roundedRect: CGRect(x: 0, y: -2, width: CGFloat(progress) * 29, height: 4),
                cornerWidth: 2, cornerHeight: 2, transform: nil
            )
            (node as? SKShapeNode)?.path = path
        }
        fill.run(.repeatForever(.sequence([grow, .run {
            fill.path = CGPath(
                roundedRect: CGRect(x: 0, y: -2, width: 1, height: 4),
                cornerWidth: 2, cornerHeight: 2, transform: nil
            )
        }])))
    }

    private func createCompletionIndicator() -> SKNode {
        let container = SKNode()

        let bg = SKShapeNode(circleOfRadius: 8)
        bg.fillColor = UIColor(red: 1, green: 0.78, blue: 0.20, alpha: 0.9)
        bg.strokeColor = .white
        bg.lineWidth = 1
        container.addChild(bg)

        let excl = SKLabelNode(text: "!")
        excl.fontName = "Courier-Bold"
        excl.fontSize = 12
        excl.fontColor = .white
        excl.verticalAlignmentMode = .center
        container.addChild(excl)

        let bounce = SKAction.sequence([
            .moveBy(x: 0, y: 3, duration: 0.4),
            .moveBy(x: 0, y: -3, duration: 0.4)
        ])
        container.run(.repeatForever(bounce))

        let pulse = SKAction.sequence([
            .scale(to: 1.15, duration: 0.5),
            .scale(to: 1.0, duration: 0.5)
        ])
        bg.run(.repeatForever(pulse))

        return container
    }

    // MARK: - Floating Text

    func showFloatingText(_ text: String, color: UIColor, at position: CGPoint? = nil) {
        let pos = position ?? player.position
        let label = SKLabelNode(text: text)
        label.fontName = "Courier-Bold"
        label.fontSize = 12
        label.fontColor = color
        label.position = CGPoint(x: pos.x, y: pos.y + 30)
        label.zPosition = 500

        let outline = SKLabelNode(text: text)
        outline.fontName = "Courier-Bold"
        outline.fontSize = 12
        outline.fontColor = UIColor(white: 0, alpha: 0.7)
        outline.position = CGPoint(x: 1, y: -1)
        outline.zPosition = -1
        label.addChild(outline)

        addChild(label)
        let anim = SKAction.group([
            .moveBy(x: 0, y: 40, duration: 1.2),
            .sequence([
                .wait(forDuration: 0.6),
                .fadeOut(withDuration: 0.6)
            ]),
            .sequence([
                .scale(to: 1.3, duration: 0.15),
                .scale(to: 1.0, duration: 0.15)
            ])
        ])
        label.run(.sequence([anim, .removeFromParent()]))
    }

    func showLevelUp(level: Int) {
        let label = SKLabelNode(text: "NIVEAU \(level) !")
        label.fontName = "Courier-Bold"
        label.fontSize = 18
        label.fontColor = UIColor(red: 1, green: 0.78, blue: 0.20, alpha: 1)
        label.position = player.position
        label.zPosition = 600

        let flash = SKShapeNode(rectOf: CGSize(width: 200, height: 40), cornerRadius: 6)
        flash.fillColor = UIColor(red: 1, green: 0.78, blue: 0.20, alpha: 0.15)
        flash.strokeColor = UIColor(red: 1, green: 0.78, blue: 0.20, alpha: 0.6)
        flash.lineWidth = 2
        flash.zPosition = -1
        label.addChild(flash)

        addChild(label)
        let anim = SKAction.sequence([
            .group([
                .scale(to: 1.5, duration: 0.2),
                .fadeIn(withDuration: 0.1)
            ]),
            .scale(to: 1.0, duration: 0.15),
            .wait(forDuration: 1.5),
            .group([
                .moveBy(x: 0, y: 30, duration: 0.5),
                .fadeOut(withDuration: 0.5)
            ]),
            .removeFromParent()
        ])
        label.setScale(0.3)
        label.alpha = 0
        label.run(anim)
    }

    // MARK: - Daily Chest

    func showDailyChest(at tileX: Int, tileY: Int) {
        dailyChestNode?.removeFromParent()

        let sprite = SKSpriteNode(color: UIColor(red: 0.85, green: 0.65, blue: 0.13, alpha: 1), size: CGSize(width: 24, height: 24))
        let flippedRow = VillageMap.height - 1 - tileY
        sprite.position = CGPoint(
            x: CGFloat(tileX) * ts + ts / 2,
            y: CGFloat(flippedRow) * ts + ts / 2
        )
        sprite.zPosition = 95
        sprite.name = "dailyChest"

        let shine = SKAction.sequence([
            .scale(to: 1.1, duration: 0.8),
            .scale(to: 0.95, duration: 0.8)
        ])
        sprite.run(.repeatForever(shine))

        let sparkle = SKShapeNode(circleOfRadius: 2)
        sparkle.fillColor = .yellow
        sparkle.strokeColor = .clear
        sparkle.position = CGPoint(x: 0, y: 16)
        sparkle.zPosition = 1
        sparkle.run(.repeatForever(.sequence([
            .fadeAlpha(to: 0.2, duration: 0.4),
            .fadeAlpha(to: 1.0, duration: 0.4)
        ])))
        sprite.addChild(sparkle)

        addChild(sprite)
        dailyChestNode = sprite
    }

    func removeDailyChest() {
        dailyChestNode?.run(.sequence([
            .group([.scale(to: 1.5, duration: 0.3), .fadeOut(withDuration: 0.3)]),
            .removeFromParent()
        ]))
        dailyChestNode = nil
    }

    func nearbyDailyChest() -> Bool {
        guard let chest = dailyChestNode else { return false }
        let dist = hypot(player.position.x - chest.position.x, player.position.y - chest.position.y)
        return dist < ts * 1.5
    }

    // MARK: - Locked Zones

    private func setupLockedZones() {
        updateLockedZones(playerLevel: playerLevel)
    }

    func updateLockedZones(playerLevel: Int) {
        self.playerLevel = playerLevel
        lockedZoneOverlays.forEach { $0.removeFromParent() }
        lockedZoneOverlays.removeAll()

        for zone in VillageMap.lockedZones {
            guard playerLevel < zone.requiredLevel else { continue }

            let overlay = SKNode()
            overlay.name = "lockedZone_\(zone.id)"
            overlay.zPosition = 300

            let sign = SKSpriteNode(color: UIColor(red: 0.3, green: 0.15, blue: 0.05, alpha: 0.85),
                                     size: CGSize(width: 100, height: 24))
            let centerCol = (zone.minCol + zone.maxCol) / 2
            let centerRow = (zone.minRow + zone.maxRow) / 2
            let flippedRow = VillageMap.height - 1 - centerRow
            sign.position = CGPoint(
                x: CGFloat(centerCol) * ts + ts / 2,
                y: CGFloat(flippedRow) * ts + ts / 2
            )
            sign.zPosition = 301

            let label = SKLabelNode(text: "NIV.\(zone.requiredLevel) REQUIS")
            label.fontName = "Courier-Bold"
            label.fontSize = 8
            label.fontColor = UIColor(red: 1, green: 0.78, blue: 0.20, alpha: 1)
            label.verticalAlignmentMode = .center
            sign.addChild(label)

            let border = SKShapeNode(rectOf: CGSize(width: 102, height: 26), cornerRadius: 3)
            border.strokeColor = UIColor(red: 1, green: 0.78, blue: 0.20, alpha: 0.5)
            border.fillColor = .clear
            border.lineWidth = 1
            sign.addChild(border)

            overlay.addChild(sign)
            addChild(overlay)
            lockedZoneOverlays.append(overlay)
        }
    }

    func isZoneLocked(col: Int, row: Int) -> Bool {
        VillageMap.lockedZones.contains { zone in
            playerLevel < zone.requiredLevel
            && col >= zone.minCol && col <= zone.maxCol
            && row >= zone.minRow && row <= zone.maxRow
        }
    }

    // MARK: - Tile map (real Figma PNGs)

    private func buildTileMap() {
        let tileLayer = SKNode()
        tileLayer.name = "tileLayer"
        let size = CGSize(width: ts, height: ts)

        for row in 0..<VillageMap.height {
            for col in 0..<VillageMap.width {
                let tile = VillageMap.grid[row][col]
                let texture = TilesetManager.tex(tile.rawValue)
                let sprite = SKSpriteNode(texture: texture, size: size)
                let flippedRow = VillageMap.height - 1 - row
                sprite.position = CGPoint(
                    x: CGFloat(col) * ts + ts / 2,
                    y: CGFloat(flippedRow) * ts + ts / 2
                )
                sprite.zPosition = 0
                tileLayer.addChild(sprite)

                if tile.rawValue.contains("swater_position_center") || tile.rawValue.contains("mwater") {
                    let frames = TilesetManager.movingWaterFrames()
                    let delay = SKAction.wait(forDuration: Double.random(in: 0...1.0))
                    let anim = SKAction.animate(with: frames, timePerFrame: 0.4)
                    sprite.run(.sequence([delay, .repeatForever(anim)]))
                }
            }
        }
        addChild(tileLayer)
    }

    // MARK: - Decorations (trees, flowers, rocks)

    private func placeDecorations() {
        for tree in VillageMap.trees {
            let texture = TilesetManager.tex(tree.asset)
            let sprite = SKSpriteNode(texture: texture,
                size: CGSize(width: CGFloat(tree.pixelW), height: CGFloat(tree.pixelH)))
            let flippedRow = VillageMap.height - 1 - tree.tileY
            sprite.anchorPoint = CGPoint(x: 0, y: 0)
            sprite.position = CGPoint(
                x: CGFloat(tree.tileX) * ts,
                y: CGFloat(flippedRow) * ts
            )
            sprite.zPosition = 10
            addChild(sprite)
        }

        for deco in VillageMap.decorations {
            let texture = TilesetManager.tex(deco.asset)
            let sprite = SKSpriteNode(texture: texture,
                size: CGSize(width: CGFloat(deco.pixelW), height: CGFloat(deco.pixelH)))
            let flippedRow = VillageMap.height - 1 - deco.tileY
            sprite.position = CGPoint(
                x: CGFloat(deco.tileX) * ts + CGFloat(deco.pixelW) / 2,
                y: CGFloat(flippedRow) * ts + CGFloat(deco.pixelH) / 2
            )
            sprite.zPosition = 10
            addChild(sprite)
        }
    }

    // MARK: - Buildings

    private func placeBuildings() {
        for bld in activeBuildings {
            let texture = TilesetManager.tex(bld.asset)
            let w = CGFloat(bld.pixelW)
            let h = CGFloat(bld.pixelH)
            let sprite = SKSpriteNode(texture: texture, size: CGSize(width: w, height: h))
            let flippedRow = VillageMap.height - 1 - bld.tileY
            sprite.anchorPoint = CGPoint(x: 0, y: 1)
            sprite.position = CGPoint(
                x: CGFloat(bld.tileX) * ts,
                y: CGFloat(flippedRow + 1) * ts
            )
            sprite.zPosition = 50
            sprite.name = "building_\(bld.id)"
            addChild(sprite)

            let label = SKLabelNode(text: bld.name)
            label.fontName = "Courier-Bold"
            label.fontSize = 9
            label.fontColor = .white
            let bgW = CGFloat(bld.name.count) * 6 + 8
            let bg = SKShapeNode(rectOf: CGSize(width: bgW, height: 13), cornerRadius: 2)
            bg.fillColor = UIColor(white: 0, alpha: 0.6)
            bg.strokeColor = .clear
            bg.position = CGPoint(x: sprite.position.x + w / 2, y: sprite.position.y + 8)
            bg.zPosition = 51
            bg.name = "label_\(bld.id)"
            label.position = .zero
            label.verticalAlignmentMode = .center
            bg.addChild(label)
            addChild(bg)
        }
    }

    func isBuildingAt(col: Int, row: Int) -> Bool {
        activeBuildings.contains { bld in
            col >= bld.tileX && col < bld.tileX + bld.widthTiles
            && row >= bld.tileY && row < bld.tileY + bld.heightTiles
        }
    }

    func isTreeAt(col: Int, row: Int) -> Bool {
        VillageMap.trees.contains { t in
            let tw = t.pixelW / 32
            let th = t.pixelH / 32
            return col >= t.tileX && col < t.tileX + tw
                && row >= t.tileY && row < t.tileY + th
        }
    }

    // MARK: - NPCs with patrol

    private func placeNPCs() {
        for npc in activeNPCs {
            let isOldman = npc.id == "npc_guide"
            let tex = isOldman
                ? TilesetManager.oldmanFrames(direction: "down_front")[0]
                : TilesetManager.brockFrames(direction: "down_front")[0]
            let sprite = SKSpriteNode(texture: tex, size: CGSize(width: 32, height: 48))
            let flippedRow = VillageMap.height - 1 - npc.tileY
            let homePos = CGPoint(
                x: CGFloat(npc.tileX) * ts + ts / 2,
                y: CGFloat(flippedRow) * ts + ts / 2
            )
            sprite.position = homePos
            sprite.zPosition = 90
            sprite.name = "npc_\(npc.id)"

            let excl = SKLabelNode(text: "!")
            excl.fontName = "Courier-Bold"
            excl.fontSize = 10
            excl.fontColor = UIColor(red: 1, green: 0.85, blue: 0.2, alpha: 1)
            excl.position = CGPoint(x: 0, y: 28)
            excl.zPosition = 91
            excl.name = "npcExcl"
            excl.run(.repeatForever(.sequence([
                .fadeAlpha(to: 0.3, duration: 0.6),
                .fadeAlpha(to: 1.0, duration: 0.6)
            ])))
            sprite.addChild(excl)
            addChild(sprite)
            npcSprites[npc.id] = sprite

            startNPCPatrol(sprite: sprite, home: homePos, npc: npc)
        }
    }

    private func startNPCPatrol(sprite: SKSpriteNode, home: CGPoint, npc: VillageMap.NPCDef) {
        let patrolDist: CGFloat = ts * CGFloat(npc.patrolRadius)
        guard patrolDist > 0 else {
            let sway = SKAction.sequence([
                .moveBy(x: 0, y: 1.5, duration: 1.0),
                .moveBy(x: 0, y: -1.5, duration: 1.0)
            ])
            sprite.run(.repeatForever(sway), withKey: "patrol")
            return
        }

        let walkSpeed: CGFloat = 30
        let tileSize = ts
        let step = SKAction.customAction(withDuration: 0) { [weak self] node, _ in
            guard self != nil else { return }
            let angle = CGFloat.random(in: 0...(2 * .pi))
            let dist = CGFloat.random(in: tileSize...(patrolDist))
            let targetX = home.x + cos(angle) * dist
            let targetY = home.y + sin(angle) * dist
            let dx = targetX - node.position.x
            let dy = targetY - node.position.y
            let moveDist = hypot(dx, dy)
            let duration = TimeInterval(moveDist / walkSpeed)

            let move = SKAction.move(to: CGPoint(x: targetX, y: targetY), duration: duration)
            move.timingMode = .easeInEaseOut
            node.run(move, withKey: "npcMove")
        }

        let patrol = SKAction.sequence([
            step,
            .wait(forDuration: 2.0, withRange: 2.0),
            .wait(forDuration: 1.5, withRange: 1.0),
        ])
        sprite.run(.repeatForever(patrol), withKey: "patrol")
    }

    // MARK: - Player

    private func spawnPlayer() {
        let flippedRow = VillageMap.height - 1 - VillageMap.spawnY
        player.position = CGPoint(
            x: CGFloat(VillageMap.spawnX) * ts + ts / 2,
            y: CGFloat(flippedRow) * ts + ts / 2
        )
        addChild(player)
    }

    // MARK: - Camera (landscape-optimized)

    private func setupCamera() {
        let cam = SKCameraNode()
        cam.setScale(0.65)
        addChild(cam)
        camera = cam
        cam.position = player.position
    }

    // MARK: - Controls

    private func setupJoystick() {
        guard let cam = camera, let view = view else { return }
        let halfH = (view.bounds.height / 2) / cam.yScale
        joystick.position = CGPoint(x: 0, y: -halfH * 0.68)
        joystick.setScale(1.6)
        cam.addChild(joystick)
    }

    private func setupActionButton() {
        guard let cam = camera, let view = view else { return }
        let halfH = (view.bounds.height / 2) / cam.yScale
        let bg = SKShapeNode(circleOfRadius: 26)
        bg.fillColor = UIColor(red: 1, green: 0.55, blue: 0.05, alpha: 0.7)
        bg.strokeColor = UIColor(red: 1, green: 0.85, blue: 0.30, alpha: 1)
        bg.lineWidth = 3
        bg.position = CGPoint(x: 140, y: -halfH * 0.68)
        bg.zPosition = 1000
        bg.name = "actionBtn"
        let label = SKLabelNode(text: "A")
        label.fontName = "Courier-Bold"
        label.fontSize = 20
        label.fontColor = .white
        label.verticalAlignmentMode = .center
        bg.addChild(label)
        cam.addChild(bg)
        actionButton = bg
    }

    override func touchesBegan(_ touches: Set<UITouch>, with event: UIEvent?) {
        super.touchesBegan(touches, with: event)
        guard let touch = touches.first, let cam = camera else { return }
        let loc = touch.location(in: cam)
        let btnPos = actionButton?.position ?? .zero
        let dist = hypot(loc.x - btnPos.x, loc.y - btnPos.y)
        if dist < 40 { handleAction() }
    }

    private func handleAction() {
        if nearbyDailyChest() {
            callbacks.onDailyChest?()
            return
        }

        if let npc = player.nearbyNPC(activeNPCs: activeNPCs) {
            callbacks.onNPCInteract?(npc)
            return
        }

        if let bld = player.nearbyBuilding(activeBuildings: activeBuildings) {
            if case .completed(let missionId) = buildingStates[bld.id] {
                callbacks.onCollectLoot?(missionId)
            } else {
                callbacks.onBuildingEnter?(bld)
            }
        }
    }

    // MARK: - Update

    override func update(_ currentTime: TimeInterval) {
        let dir = joystick.direction
        player.move(dx: dir.dx, dy: dir.dy, in: self)

        if let cam = camera {
            let lerp: CGFloat = 0.08
            cam.position = CGPoint(
                x: cam.position.x + (player.position.x - cam.position.x) * lerp,
                y: cam.position.y + (player.position.y - cam.position.y) * lerp
            )
        }
        let nearbyNPC = player.nearbyNPC(activeNPCs: activeNPCs)
        let isNearSage = nearbyNPC?.id == "npc_guide"
        if isNearSage != wasNearSage {
            wasNearSage = isNearSage
            callbacks.onNearSage?(isNearSage)
        }

        let near = player.nearbyBuilding(activeBuildings: activeBuildings) != nil || nearbyNPC != nil || nearbyDailyChest()
        if near && !wasNearInteractable {
            UIImpactFeedbackGenerator(style: .light).impactOccurred()
        }
        wasNearInteractable = near
        actionButton?.alpha += ((near ? 1.0 : 0.25) - (actionButton?.alpha ?? 0)) * 0.15
    }
}
