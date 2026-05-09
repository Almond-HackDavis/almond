import SwiftUI

struct DashboardView: View {
    @StateObject private var localVM = DashboardViewModel()
    @StateObject private var riskVM = APIRiskViewModel()

    var body: some View {
        TabView {
            RiskDashboardView(vm: riskVM)
                .tabItem { Label("Risk", systemImage: "gauge.with.needle") }

            ScoresView(vm: localVM)
                .tabItem { Label("Metrics", systemImage: "heart.text.square") }

            HistoryChartView(vm: localVM)
                .tabItem { Label("Trends", systemImage: "chart.xyaxis.line") }

            SleepView(vm: localVM)
                .tabItem { Label("Sleep", systemImage: "moon.zzz") }

            ProfileView()
                .tabItem { Label("Profile", systemImage: "person.circle") }
        }
        .task {
            async let local: () = localVM.load()
            async let risk: () = riskVM.uploadAndPoll()
            _ = await (local, risk)
        }
    }
}
