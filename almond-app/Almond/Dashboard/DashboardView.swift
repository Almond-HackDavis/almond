import SwiftUI

struct DashboardView: View {
    @EnvironmentObject var authManager: AuthManager
    @StateObject private var vm = DashboardViewModel()

    var body: some View {
        TabView {
            ScoresView(vm: vm)
                .tabItem { Label("Scores", systemImage: "heart.text.square") }

            HistoryChartView(vm: vm)
                .tabItem { Label("Trends", systemImage: "chart.xyaxis.line") }

            RecommendationView(vm: vm)
                .tabItem { Label("Actions", systemImage: "checkmark.circle") }
        }
        .task { await vm.load() }
    }
}
