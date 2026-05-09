import Foundation

@MainActor
final class DashboardViewModel: ObservableObject {
    @Published var risk: RiskResponse?
    @Published var history: HistoryResponse?
    @Published var isLoading = false
    @Published var isRefreshing = false
    @Published var errorMessage: String?

    func load() async {
        guard !isLoading else { return }
        isLoading = true
        defer { isLoading = false }
        errorMessage = nil

        do {
            async let riskTask = APIClient.shared.getRisk()
            async let historyTask = APIClient.shared.getHistory(days: 90)
            risk = try await riskTask
            history = try await historyTask
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func syncAndRefresh() async {
        isRefreshing = true
        defer { isRefreshing = false }
        errorMessage = nil

        do {
            let payload = try await HealthKitManager().buildUploadPayload()
            let response = try await APIClient.shared.uploadHealthKit(payload)
            if response.processed {
                async let riskTask = APIClient.shared.getRisk()
                async let historyTask = APIClient.shared.getHistory(days: 90)
                risk = try await riskTask
                history = try await historyTask
            }
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}
