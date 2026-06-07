import SpriteKit

final class PlayerSprite: SKSpriteNode {
    enum Direction: String {
        case down  = "down_front"
        case up    = "up_back"
        case left  = "-_left"
        case right = "-_right"
    }

    private var walkFrames: [Direction: [SKTexture]] = [:]
    private(set) var facing: Direction = .down
    private var isWalking = false
    private let moveSpeed: CGFloat = 90

    init() {
        let frames = TilesetManager.brockFrames(direction: Direction.down.rawValue)
        let tex = frames.first ?? SKTexture()
        super.init(texture: tex, color: .clear, size: CGSize(width: 32, height: 48))
        self.zPosition = 100

        for dir in [Direction.down, .up, .left, .right] {
            walkFrames[dir] = TilesetManager.brockFrames(direction: dir.rawValue)
        }
    }

    required init?(coder: NSCoder) { fatalError() }

    func move(dx: CGFloat, dy: CGFloat, in scene: GameScene) {
        guard dx != 0 || dy != 0 else { stopWalking(); return }

        let newDir: Direction
        if abs(dx) > abs(dy) { newDir = dx > 0 ? .right : .left }
        else { newDir = dy > 0 ? .up : .down }

        if newDir != facing || !isWalking {
            facing = newDir
            startWalking()
        }

        let dt = CGFloat(1.0 / 60.0)
        let len = sqrt(dx * dx + dy * dy)
        let newX = position.x + (dx / len) * moveSpeed * dt
        let newY = position.y + (dy / len) * moveSpeed * dt

        let ts = TilesetManager.tileSize
        let col = Int(newX / ts)
        let row = VillageMap.height - 1 - Int(newY / ts)

        if col >= 0, col < VillageMap.width, row >= 0, row < VillageMap.height {
            let tile = VillageMap.grid[row][col]
            if !tile.isSolid && !scene.isBuildingAt(col: col, row: row)
                && !scene.isTreeAt(col: col, row: row)
                && !scene.isZoneLocked(col: col, row: row) {
                position = CGPoint(x: newX, y: newY)
            }
        }
    }

    private func startWalking() {
        guard let frames = walkFrames[facing], frames.count > 1 else { return }
        if isWalking { removeAction(forKey: "walk") }
        isWalking = true
        run(.repeatForever(.animate(with: frames, timePerFrame: 0.15)), withKey: "walk")
    }

    func stopWalking() {
        guard isWalking else { return }
        isWalking = false
        removeAction(forKey: "walk")
        if let frames = walkFrames[facing] { texture = frames[0] }
    }

    func nearbyBuilding(activeBuildings: [VillageMap.BuildingDef]? = nil) -> VillageMap.BuildingDef? {
        let ts = TilesetManager.tileSize
        let col = Int(position.x / ts)
        let row = VillageMap.height - 1 - Int(position.y / ts)
        let blds = activeBuildings ?? VillageMap.buildings
        return blds.first { abs(col - $0.doorTileX) <= 1 && abs(row - $0.doorTileY) <= 1 }
    }

    func nearbyNPC(activeNPCs: [VillageMap.NPCDef]? = nil) -> VillageMap.NPCDef? {
        let ts = TilesetManager.tileSize
        let col = Int(position.x / ts)
        let row = VillageMap.height - 1 - Int(position.y / ts)
        let npcs = activeNPCs ?? VillageMap.npcs
        return npcs.first { abs(col - $0.tileX) <= 1 && abs(row - $0.tileY) <= 1 }
    }
}
