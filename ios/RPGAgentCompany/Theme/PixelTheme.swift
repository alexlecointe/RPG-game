import SwiftUI

enum PixelTheme {
    // MARK: - Colors (Game Boy–inspired palette)

    static let bgDark = Color(red: 0.05, green: 0.05, blue: 0.12)
    static let bgMedium = Color(red: 0.10, green: 0.10, blue: 0.20)
    static let bgLight = Color(red: 0.16, green: 0.16, blue: 0.28)
    static let accent = Color(red: 1.0, green: 0.78, blue: 0.20)       // gold / gems
    static let accentGreen = Color(red: 0.20, green: 0.85, blue: 0.40)  // XP / success
    static let accentRed = Color(red: 0.90, green: 0.25, blue: 0.30)    // HP / fail
    static let accentBlue = Color(red: 0.30, green: 0.60, blue: 1.0)    // info / builder
    static let accentPurple = Color(red: 0.65, green: 0.35, blue: 0.90) // marketer
    static let textPrimary = Color.white
    static let textSecondary = Color.white.opacity(0.65)
    static let cardBorder = Color.white.opacity(0.15)

    // MARK: - Typography

    static func pixelFont(_ size: CGFloat) -> Font {
        .system(size: size, weight: .bold, design: .monospaced)
    }

    static let titleFont = pixelFont(22)
    static let headlineFont = pixelFont(16)
    static let bodyFont = pixelFont(13)
    static let captionFont = pixelFont(11)
    static let microFont = pixelFont(9)

    // MARK: - Shapes

    static let cardRadius: CGFloat = 8
    static let buttonRadius: CGFloat = 6
}

// MARK: - Reusable pixel-style card background

struct PixelCard: ViewModifier {
    var highlighted: Bool = false

    func body(content: Content) -> some View {
        content
            .padding(12)
            .background(
                RoundedRectangle(cornerRadius: PixelTheme.cardRadius)
                    .fill(PixelTheme.bgLight)
                    .overlay(
                        RoundedRectangle(cornerRadius: PixelTheme.cardRadius)
                            .stroke(highlighted ? PixelTheme.accent : PixelTheme.cardBorder, lineWidth: highlighted ? 2 : 1)
                    )
            )
    }
}

extension View {
    func pixelCard(highlighted: Bool = false) -> some View {
        modifier(PixelCard(highlighted: highlighted))
    }
}

// MARK: - Pixel button style

struct PixelButtonStyle: ButtonStyle {
    var color: Color = PixelTheme.accent

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(PixelTheme.bodyFont)
            .foregroundStyle(PixelTheme.bgDark)
            .padding(.horizontal, 16)
            .padding(.vertical, 10)
            .background(
                RoundedRectangle(cornerRadius: PixelTheme.buttonRadius)
                    .fill(configuration.isPressed ? color.opacity(0.7) : color)
            )
            .scaleEffect(configuration.isPressed ? 0.95 : 1.0)
    }
}

// MARK: - XP progress bar

struct XPBar: View {
    let current: Int
    let nextLevel: Int
    let level: Int

    private var progress: Double {
        guard nextLevel > 0 else { return 0 }
        return min(Double(current) / Double(nextLevel), 1.0)
    }

    var body: some View {
        VStack(spacing: 4) {
            HStack {
                Text("LV.\(level)")
                    .font(PixelTheme.captionFont)
                    .foregroundStyle(PixelTheme.accent)
                Spacer()
                Text("\(current)/\(nextLevel) XP")
                    .font(PixelTheme.microFont)
                    .foregroundStyle(PixelTheme.textSecondary)
            }
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 3)
                        .fill(PixelTheme.bgDark)
                    RoundedRectangle(cornerRadius: 3)
                        .fill(PixelTheme.accentGreen)
                        .frame(width: geo.size.width * progress)
                }
            }
            .frame(height: 8)
        }
    }
}

// MARK: - Gem counter

struct GemCounter: View {
    let balance: Int
    let cap: Int

    var body: some View {
        HStack(spacing: 2) {
            Text("◆")
                .font(PixelTheme.microFont)
                .foregroundStyle(PixelTheme.accent)
            Text("\(balance)/\(cap)")
                .font(PixelTheme.microFont)
                .foregroundStyle(PixelTheme.textPrimary)
                .lineLimit(1)
                .fixedSize()
        }
    }
}
