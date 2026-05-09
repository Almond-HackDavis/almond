import SwiftUI

struct DashboardView: View {
    @StateObject private var vm = DashboardViewModel()

    var body: some View {
        TabView {
            ScoresView(vm: vm)
                .tabItem { Label("Metrics", systemImage: "heart.text.square") }

            ScoresView(vm: localVM)
                .tabItem { Label("Metrics", systemImage: "heart.text.square") }

            HistoryChartView(vm: localVM)
                .tabItem { Label("Trends", systemImage: "chart.xyaxis.line") }

            SleepView(vm: vm)
                .tabItem { Label("Sleep", systemImage: "moon.zzz") }
        }
    }
}
