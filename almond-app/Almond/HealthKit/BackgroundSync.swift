import BackgroundTasks
import Foundation

enum BackgroundSync {
    static let taskIdentifier = "com.almond.app.refresh"

    static func register() {
        BGTaskScheduler.shared.register(
            forTaskWithIdentifier: taskIdentifier,
            using: nil
        ) { task in
            guard let refreshTask = task as? BGAppRefreshTask else {
                task.setTaskCompleted(success: false)
                return
            }
            handleRefresh(task: refreshTask)
        }
    }

    static func schedule() {
        let request = BGAppRefreshTaskRequest(identifier: taskIdentifier)
        request.earliestBeginDate = Date(timeIntervalSinceNow: 4 * 3600)
        try? BGTaskScheduler.shared.submit(request)
    }

    private static func handleRefresh(task: BGAppRefreshTask) {
        schedule()
        let syncTask = Task {
            do {
                let samples = try await HealthKitManager().buildUploadPayload()
                _ = try await APIClient.shared.submitInput(samples: samples)
                // Fire-and-forget — result will be visible next time the app opens
                task.setTaskCompleted(success: true)
            } catch {
                task.setTaskCompleted(success: false)
            }
        }
        task.expirationHandler = { syncTask.cancel() }
    }
}
