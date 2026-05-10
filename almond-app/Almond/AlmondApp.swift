import SwiftUI

@main
struct AlmondApp: App {
    init() {
        BackgroundSync.register()
    }

    var body: some Scene {
        WindowGroup {
            ContentView()
        }
    }
}
