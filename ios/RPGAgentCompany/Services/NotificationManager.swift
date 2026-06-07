import UserNotifications

final class NotificationManager {
    static let shared = NotificationManager()

    private init() {}

    func requestPermission() {
        UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .badge, .sound]) { _, _ in }
    }

    func scheduleMissionComplete(agentType: String, missionType: String) {
        let content = UNMutableNotificationContent()

        let agentName: String
        switch agentType {
        case "builder": agentName = "Le Forgeron"
        case "marketer": agentName = "Le Marchand"
        case "researcher": agentName = "Le Chercheur"
        default: agentName = "Un agent"
        }

        let taskName = missionType.replacingOccurrences(of: "_", with: " ")
        content.title = "\(agentName) a termine !"
        content.body = "Ton livrable \"\(taskName)\" est pret. Reviens au village pour le recuperer !"
        content.sound = .default

        let trigger = UNTimeIntervalNotificationTrigger(timeInterval: 1, repeats: false)
        let request = UNNotificationRequest(
            identifier: "mission_\(missionType)_\(UUID().uuidString.prefix(8))",
            content: content,
            trigger: trigger
        )
        UNUserNotificationCenter.current().add(request)
    }

    func scheduleReengagementReminder() {
        UNUserNotificationCenter.current().removePendingNotificationRequests(
            withIdentifiers: ["reengagement_j1"]
        )

        let content = UNMutableNotificationContent()
        content.title = "Ton agent t'attend"
        content.body = "Tu as peut-etre un livrable pret. Reviens au village recuperer ton loot !"
        content.sound = .default

        let trigger = UNTimeIntervalNotificationTrigger(timeInterval: 86400, repeats: false)
        let request = UNNotificationRequest(
            identifier: "reengagement_j1",
            content: content,
            trigger: trigger
        )
        UNUserNotificationCenter.current().add(request)
    }

    func cancelReengagementReminder() {
        UNUserNotificationCenter.current().removePendingNotificationRequests(
            withIdentifiers: ["reengagement_j1"]
        )
    }
}
