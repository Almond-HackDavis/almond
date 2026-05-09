import Foundation

actor APIClient {
    static let shared = APIClient()

    private let baseURL: URL
    private var sessionToken: String?

    private init() {
        // Replace with Railway/Fly.io deployment URL before shipping.
        self.baseURL = URL(string: "https://api.almond.app")!
    }

    func setSessionToken(_ token: String) {
        sessionToken = token
    }

    func clearSessionToken() {
        sessionToken = nil
    }

    // MARK: - Endpoints

    func login(appleIdentityToken: String) async throws -> LoginResponse {
        let body = LoginRequest(appleIdentityToken: appleIdentityToken)
        return try await post(path: "/auth/login", body: body, requiresAuth: false)
    }

    func submitOnboarding(_ request: OnboardingRequest) async throws -> OnboardingResponse {
        return try await post(path: "/onboarding", body: request)
    }

    func uploadHealthKit(_ request: HealthKitUploadRequest) async throws -> HealthKitUploadResponse {
        return try await post(path: "/healthkit", body: request)
    }

    /// GET /risk — optionally scoped to a specific upload_id for polling.
    func getRisk(uploadId: String? = nil) async throws -> RiskPollResponse {
        var path = "/risk"
        if let id = uploadId { path += "?upload_id=\(id)" }
        return try await get(path: path)
    }

    /// Polls GET /risk?upload_id=<id> every 5 s until status == "done" or 60 s elapses.
    func pollRisk(uploadId: String) async throws -> RiskResponseFull {
        let deadline = Date(timeIntervalSinceNow: 60)
        while Date() < deadline {
            let response = try await getRisk(uploadId: uploadId)
            switch response {
            case .done(let full):
                return full
            case .failed:
                throw AlmondError.api(code: "processing_failed",
                                      message: "Risk computation failed. Please try again.")
            case .pending:
                try await Task.sleep(nanoseconds: 5_000_000_000)
            }
        }
        throw AlmondError.pollTimeout
    }

    func getHistory(days: Int = 90) async throws -> HistoryResponse {
        return try await get(path: "/history?days=\(days)")
    }

    // MARK: - Private

    private func post<Body: Encodable, Response: Decodable>(
        path: String,
        body: Body,
        requiresAuth: Bool = true
    ) async throws -> Response {
        guard let url = URL(string: baseURL.absoluteString + path) else {
            throw URLError(.badURL)
        }
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if requiresAuth {
            guard let token = sessionToken else { throw AlmondError.notAuthenticated }
            req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        req.httpBody = try JSONEncoder().encode(body)
        return try await perform(req)
    }

    private func get<Response: Decodable>(path: String) async throws -> Response {
        guard let url = URL(string: baseURL.absoluteString + path) else {
            throw URLError(.badURL)
        }
        var req = URLRequest(url: url)
        req.httpMethod = "GET"
        guard let token = sessionToken else { throw AlmondError.notAuthenticated }
        req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        return try await perform(req)
    }

    private func perform<Response: Decodable>(_ request: URLRequest) async throws -> Response {
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw URLError(.badServerResponse)
        }

        if http.statusCode == 401 {
            let envelope = try? JSONDecoder().decode(APIErrorEnvelope.self, from: data)
            if envelope?.error.code == "session_expired" {
                throw AlmondError.sessionExpired
            }
            throw AlmondError.notAuthenticated
        }

        guard (200..<300).contains(http.statusCode) else {
            let envelope = try? JSONDecoder().decode(APIErrorEnvelope.self, from: data)
            throw AlmondError.api(
                code: envelope?.error.code ?? "http_\(http.statusCode)",
                message: envelope?.error.message ?? "HTTP \(http.statusCode)"
            )
        }
        return try JSONDecoder().decode(Response.self, from: data)
    }
}
