import SpriteKit
import UIKit

/// Loads real Pokémon tileset PNGs exported from Figma.
/// Base tile = 32×32 px native. Display at 1× (camera zoom handles viewport).
enum TilesetManager {
    static let tileSize: CGFloat = 32

    private static var cache: [String: SKTexture] = [:]

    static func tex(_ name: String) -> SKTexture {
        if let t = cache[name] { return t }
        let t = SKTexture(imageNamed: name)
        t.filteringMode = .nearest
        cache[name] = t
        return t
    }

    // MARK: - Base terrain

    static func base(_ variant: Int) -> SKTexture { tex("base_property_1_\(variant)") }
    static var tallGrass: SKTexture { tex("base_property_1_tall_grass") }

    // MARK: - Paths (ground type with edge/corner transitions)

    static func pathGround(_ pos: String) -> SKTexture {
        tex("path_type_ground_position_\(pos)_invert_false")
    }
    static func pathGrass(_ pos: String) -> SKTexture {
        tex("path_type_grass_position_\(pos)_invert_false")
    }
    static func pathGrassInv(_ pos: String) -> SKTexture {
        tex("path_type_grass_position_\(pos)_invert_true")
    }

    // MARK: - Still water (with edge/corner transitions)

    static func stillWater(_ pos: String, cornerBase: String = "none") -> SKTexture {
        tex("swater_position_\(pos)_corner_base_\(cornerBase)_invert_false")
    }
    static func stillWaterInv(_ pos: String) -> SKTexture {
        tex("swater_position_\(pos)_corner_base_none_invert_true")
    }

    // MARK: - Moving water (8-frame animation)

    static func movingWaterFrames() -> [SKTexture] {
        (1...8).map { tex("mwater_stage_\($0)") }
    }

    // MARK: - Mountains (brown)

    static func mountain(_ pos: String) -> SKTexture {
        tex("mtn_position_\(pos)_type_brown_invert_false")
    }

    // MARK: - Plants

    static var tree: SKTexture { tex("plant_type_tree") }
    static var bush: SKTexture { tex("plant_type_bush") }
    static var flowersRed: SKTexture { tex("plant_type_flowers_red") }
    static var flowersWhite: SKTexture { tex("plant_type_flowers_white") }
    static var flowersRedWhite: SKTexture { tex("plant_type_flowers_red_and_white") }
    static var flowerPatch: SKTexture { tex("plant_type_flower_patch") }
    static var treePlanted: SKTexture { tex("plant_type_tree_planted") }

    // MARK: - Rocks

    static func rock(grey: Bool, type: Int) -> SKTexture {
        tex("rock_grey_\(grey)_type_\(type)")
    }

    // MARK: - Buildings

    static func building(_ name: String) -> SKTexture { tex("bld_type_\(name)") }

    // MARK: - Character Brock (4 dir × 4 frames)

    static func brockFrames(direction: String) -> [SKTexture] {
        (1...4).map { step in
            tex("char_character_brock_steps_\(step)_orientation_\(direction)")
        }
    }

    // MARK: - Oldman / Le Sage (4 dir × 4 frames)

    static func oldmanFrames(direction: String) -> [SKTexture] {
        (1...4).map { step in
            tex("char_oldman_steps_\(step)_orientation_\(direction)")
        }
    }
}

extension UIColor {
    func adjusted(by delta: CGFloat) -> UIColor {
        var r: CGFloat = 0, g: CGFloat = 0, b: CGFloat = 0, a: CGFloat = 0
        getRed(&r, green: &g, blue: &b, alpha: &a)
        return UIColor(red: max(0, min(1, r + delta)), green: max(0, min(1, g + delta)), blue: max(0, min(1, b + delta)), alpha: a)
    }
}
