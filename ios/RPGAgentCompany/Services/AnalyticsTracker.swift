import Foundation

/// Lightweight product analytics — events stored locally and logged for beta review.
enum AnalyticsTracker {
    private static let storageKey = "rpg_analytics_events"
    private static let maxEvents = 500

    static func track(_ name: String, properties: [String: String] = [:]) {
        var event: [String: String] = ["name": name, "ts": ISO8601DateFormatter().string(from: Date())]
        for (k, v) in properties { event[k] = v }

        var events = loadEvents()
        events.insert(event, at: 0)
        if events.count > maxEvents { events = Array(events.prefix(maxEvents)) }
        UserDefaults.standard.set(events, forKey: storageKey)

        #if DEBUG
        print("[Analytics] \(name) \(properties)")
        #endif
    }

    static func loadEvents() -> [[String: String]] {
        UserDefaults.standard.array(forKey: storageKey) as? [[String: String]] ?? []
    }

    static func eventCount(for name: String) -> Int {
        loadEvents().filter { $0["name"] == name }.count
    }

    static func exportJSON() -> String {
        guard let data = try? JSONSerialization.data(withJSONObject: loadEvents(), options: .prettyPrinted),
              let str = String(data: data, encoding: .utf8) else { return "[]" }
        return str
    }
}
