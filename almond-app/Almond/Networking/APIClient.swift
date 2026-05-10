import Foundation

actor APIClient {
    static let shared = APIClient()

    // ── Bridge API base URL ────────────────────────────────────────────────
    private static let baseURL = "https://uncrippled-pisciculturally-leda.ngrok-free.dev"
    // ──────────────────────────────────────────────────────────────────────

    // MARK: - User identity (no auth — stable UUID per device)

    nonisolated static var userId: String {
        let key = "app.user_id"
        if let id = UserDefaults.standard.string(forKey: key) { return id }
        let id = UUID().uuidString.lowercased()
        UserDefaults.standard.set(id, forKey: key)
        return id
    }

    // MARK: - Endpoints

    /// POST /input — blocks ~3-5 s on the server and returns the finished OutputDocument directly.
    func submitInput(healthKit: HealthKitUploadRequest) async throws -> BridgeOutput {
        let body = BridgeInputRequest(userId: Self.userId, onboarding: buildOnboarding(), samples: healthKit.samples)
        return try await post(path: "/input", body: body)
    }

    /// GET /output — returns the most recent cached result, or nil if none exists yet.
    func fetchOutput() async throws -> BridgeOutput? {
        return try await getOutput(path: "/output")
    }

    // MARK: - Private

    private func buildOnboarding() -> OnboardingPayload {
        let d = UserDefaults.standard
        return OnboardingPayload(
            age: d.integer(forKey: "ob.age"),
            sex: d.string(forKey: "ob.sex") ?? "M",
            heightCm: d.double(forKey: "ob.height_cm"),
            weightKg: d.double(forKey: "ob.weight_kg"),
            smoking: d.bool(forKey: "ob.smoking"),
            diabetes: d.bool(forKey: "ob.diabetes"),
            familyHistoryCvd: d.bool(forKey: "ob.family_history_cvd"),
            onBpMedication: d.bool(forKey: "ob.on_bp_medication"),
            raceEthnicity: d.string(forKey: "ob.race_ethnicity"),
            systolicBp: d.integer(forKey: "ob.systolic_bp") > 0 ? d.integer(forKey: "ob.systolic_bp") : nil,
            totalCholesterol: d.integer(forKey: "ob.total_cholesterol") > 0 ? d.integer(forKey: "ob.total_cholesterol") : nil,
            hdlCholesterol: d.integer(forKey: "ob.hdl_cholesterol") > 0 ? d.integer(forKey: "ob.hdl_cholesterol") : nil
        )
    }

    private func url(_ path: String) throws -> URL {
        guard let url = URL(string: Self.baseURL + path) else { throw URLError(.badURL) }
        return url
    }

    private func post<Body: Encodable, Response: Decodable>(
        path: String, body: Body
    ) async throws -> Response {
        var req = URLRequest(url: try url(path))
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.setValue("true", forHTTPHeaderField: "ngrok-skip-browser-warning")
        req.httpBody = try JSONEncoder().encode(body)
        let (data, response) = try await URLSession.shared.data(for: req)
        guard let http = response as? HTTPURLResponse else { throw URLError(.badServerResponse) }
        guard (200..<300).contains(http.statusCode) else {
            let envelope = try? JSONDecoder().decode(APIErrorEnvelope.self, from: data)
            throw AlmondError.api(
                code: envelope?.error.code ?? "http_\(http.statusCode)",
                message: envelope?.error.message ?? "HTTP \(http.statusCode)"
            )
        }
        return try JSONDecoder().decode(Response.self, from: data)
    }

    /// Returns nil on 404 not_ready; throws on unexpected errors.
    private func getOutput(path: String) async throws -> BridgeOutput? {
        var req = URLRequest(url: try url(path))
        req.httpMethod = "GET"
        req.setValue("true", forHTTPHeaderField: "ngrok-skip-browser-warning")
        let (data, response) = try await URLSession.shared.data(for: req)
        guard let http = response as? HTTPURLResponse else { throw URLError(.badServerResponse) }
        if http.statusCode == 404 { return nil }
        guard (200..<300).contains(http.statusCode) else {
            throw AlmondError.api(code: "http_\(http.statusCode)", message: "HTTP \(http.statusCode)")
        }
        return try JSONDecoder().decode(BridgeOutput.self, from: data)
    }
}
