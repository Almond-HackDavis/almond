import Foundation

actor APIClient {
    static let shared = APIClient()

    private let baseURL: URL
    private var sessionToken: String?

    private static let iso8601: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return f
    }()

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

    func getRisk() async throws -> RiskResponse {
        return try await get(path: "/risk")
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
