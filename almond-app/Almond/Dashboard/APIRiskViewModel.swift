import Foundation

@MainActor
final class APIRiskViewModel: ObservableObject {
    enum Phase: Equatable {
        case idle
        case uploading
        case polling(status: String)
        case done(RiskResponseFull)
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
    @Published var historyResponse: HistoryResponse?

    private let hk = HealthKitManager()

    var riskResult: RiskResponseFull? {
        if case .done(let r) = phase { return r }
        return nil
    }

    func uploadAndPoll() async {
        guard case .idle = phase else { return }
        phase = .uploading

        do {
            let payload = try await hk.buildUploadPayload()
            let uploadResp = try await APIClient.shared.uploadHealthKit(payload)

            if uploadResp.status == "failed" {
                phase = .failed("Upload was rejected by the server. Please try again.")
                return
            }

            phase = .polling(status: uploadResp.status)

            let deadline = Date(timeIntervalSinceNow: 60)
            while Date() < deadline {
                let poll = try await APIClient.shared.getRisk(uploadId: uploadResp.uploadId)
                switch poll {
                case .done(let full):
                    phase = .done(full)
                    await loadHistory()
                    return
                case .failed:
                    phase = .failed("Risk computation failed. Please try again.")
                    return
                case .pending(_, let status):
                    phase = .polling(status: status)
                    try await Task.sleep(nanoseconds: 5_000_000_000)
                }
            }
            phase = .failed(AlmondError.pollTimeout.localizedDescription ?? "Timed out.")
        } catch AlmondError.sessionExpired {
            phase = .failed("Session expired. Please sign in again.")
        } catch {
            phase = .failed(error.localizedDescription)
        }
    }

    func retry() {
        phase = .idle
        Task { await uploadAndPoll() }
    }

    private func loadHistory() async {
        historyResponse = try? await APIClient.shared.getHistory(days: 90)
    }
}
