import Foundation

@MainActor
final class APIRiskViewModel: ObservableObject {
    enum Phase: Equatable {
        case idle
        case uploading
        case polling(attempt: Int)
        case done(BridgeOutput)
        case failed(String)

        static func == (lhs: Phase, rhs: Phase) -> Bool {
            switch (lhs, rhs) {
            case (.idle, .idle), (.uploading, .uploading): return true
            case (.polling(let a), .polling(let b)): return a == b
            case (.failed(let a), .failed(let b)): return a == b
            case (.done, .done): return true
            default: return false
            }
        }
    }

    @Published var phase: Phase = .idle

    private let hk = HealthKitManager()

    func uploadAndPoll() async {
        guard case .idle = phase else { return }
        phase = .uploading

        do {
            let payload = try await hk.buildUploadPayload()
            let output = try await APIClient.shared.submitInput(healthKit: payload)
            phase = .done(output)
        } catch {
            phase = .failed(error.localizedDescription)
        }
    }

    /// Skip upload — fetch the most recent result from GET /output.
    func fetchLatestOnly() async {
        phase = .polling(attempt: 0)
        do {
            if let output = try await APIClient.shared.fetchOutput() {
                phase = .done(output)
            } else {
                phase = .idle  // nothing ready yet — show the Compute button
            }
        } catch {
            phase = .idle  // network error on load — don't block the user, just show idle
        }
    }

    func retry() {
        phase = .idle
        Task { await uploadAndPoll() }
    }

}
