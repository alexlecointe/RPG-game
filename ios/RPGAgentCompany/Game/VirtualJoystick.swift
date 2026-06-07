import SpriteKit

final class VirtualJoystick: SKNode {
    private let base: SKShapeNode
    private let knob: SKShapeNode
    private let baseRadius: CGFloat = 50
    private let knobRadius: CGFloat = 22

    /// Normalized direction (-1…1 for x and y)
    private(set) var direction: CGVector = .zero
    private var tracking = false

    override init() {
        base = SKShapeNode(circleOfRadius: baseRadius)
        base.fillColor = UIColor.white.withAlphaComponent(0.15)
        base.strokeColor = UIColor.white.withAlphaComponent(0.3)
        base.lineWidth = 2

        knob = SKShapeNode(circleOfRadius: knobRadius)
        knob.fillColor = UIColor.white.withAlphaComponent(0.4)
        knob.strokeColor = UIColor.white.withAlphaComponent(0.6)
        knob.lineWidth = 1

        super.init()
        isUserInteractionEnabled = true
        zPosition = 1000
        addChild(base)
        addChild(knob)
    }

    required init?(coder: NSCoder) { fatalError() }

    override func touchesBegan(_ touches: Set<UITouch>, with event: UIEvent?) {
        guard let touch = touches.first else { return }
        let loc = touch.location(in: self)
        if loc.length() <= baseRadius * 1.5 {
            tracking = true
            updateKnob(loc)
        }
    }

    override func touchesMoved(_ touches: Set<UITouch>, with event: UIEvent?) {
        guard tracking, let touch = touches.first else { return }
        updateKnob(touch.location(in: self))
    }

    override func touchesEnded(_ touches: Set<UITouch>, with event: UIEvent?) {
        resetKnob()
    }

    override func touchesCancelled(_ touches: Set<UITouch>, with event: UIEvent?) {
        resetKnob()
    }

    private func updateKnob(_ loc: CGPoint) {
        let dist = min(loc.length(), baseRadius)
        let angle = atan2(loc.y, loc.x)
        let x = cos(angle) * dist
        let y = sin(angle) * dist
        knob.position = CGPoint(x: x, y: y)

        let norm = dist / baseRadius
        let deadZone: CGFloat = 0.15
        if norm < deadZone {
            direction = .zero
        } else {
            direction = CGVector(dx: cos(angle) * norm, dy: sin(angle) * norm)
        }
    }

    private func resetKnob() {
        tracking = false
        knob.position = .zero
        direction = .zero
    }
}

private extension CGPoint {
    func length() -> CGFloat {
        sqrt(x * x + y * y)
    }
}
