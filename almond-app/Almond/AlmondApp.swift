import SwiftUI
import BackgroundTasks

@main
struct AlmondApp: App {
    @StateObject private var authManager = AuthManager()

    init() {
        BackgroundSync.register()
    }

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(authManager)
        }
    }
}
