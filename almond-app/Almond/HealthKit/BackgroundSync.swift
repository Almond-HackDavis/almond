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
                let payload = try await HealthKitManager().buildUploadPayload()
                let response = try await APIClient.shared.uploadHealthKit(payload)
                if response.processed {
                    _ = try? await APIClient.shared.getRisk()
                }
                task.setTaskCompleted(success: true)
            } catch {
                task.setTaskCompleted(success: false)
            }
        }

        task.expirationHandler = { syncTask.cancel() }
    }
}
