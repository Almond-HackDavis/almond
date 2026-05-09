import SwiftUI

struct DashboardView: View {
    @StateObject private var vm = DashboardViewModel()

    var body: some View {
        TabView {
            ScoresView(vm: vm)
                .tabItem { Label("Metrics", systemImage: "heart.text.square") }

            HistoryChartView(vm: vm)
                .tabItem { Label("Trends", systemImage: "chart.xyaxis.line") }

            SleepView(vm: vm)
                .tabItem { Label("Sleep", systemImage: "moon.zzz") }

            ProfileView()
                .tabItem { Label("Profile", systemImage: "person.circle") }
        }
        .task { await vm.load() }
    }
}
