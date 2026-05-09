import Foundation

@MainActor
final class DashboardViewModel: ObservableObject {
    @Published var snapshot: HealthSnapshot?
    @Published var isLoading = false
    @Published var errorMessage: String?

    private let hk = HealthKitManager()

    func load() async {
        guard !isLoading else { return }
        isLoading = true
        defer { isLoading = false }
        errorMessage = nil
        do {
            snapshot = try await hk.querySnapshot(days: 30)
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func refresh() async {
        isLoading = true
        defer { isLoading = false }
        errorMessage = nil
        do {
            snapshot = try await hk.querySnapshot(days: 30)
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}
