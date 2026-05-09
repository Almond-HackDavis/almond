import Foundation
import Combine

@MainActor
final class AuthManager: NSObject, ObservableObject {
    enum AuthState: Equatable {
        case unauthenticated
        case needsOnboarding
        case authenticated
    }

    @Published private(set) var state: AuthState = .unauthenticated
    @Published private(set) var userId: String?

    private let tokenKey = "almond.session_token"
    private let userIdKey = "almond.user_id"
    private let onboardingKey = "almond.onboarding_complete"

    override init() {
        super.init()
        loadStoredSession()
    }

    private func loadStoredSession() {
        guard let token = KeychainHelper.load(key: tokenKey),
              !token.isEmpty,
              let uid = UserDefaults.standard.string(forKey: userIdKey) else {
            state = .unauthenticated
            return
        }
        userId = uid
        APIClient.shared.setSessionToken(token)
        let done = UserDefaults.standard.bool(forKey: onboardingKey)
        state = done ? .authenticated : .needsOnboarding
    }

    func signIn(identityToken: String) async throws {
        let response = try await APIClient.shared.login(appleIdentityToken: identityToken)
        KeychainHelper.save(key: tokenKey, value: response.sessionToken)
        UserDefaults.standard.set(response.userId, forKey: userIdKey)
        APIClient.shared.setSessionToken(response.sessionToken)
        userId = response.userId
        state = response.needsOnboarding ? .needsOnboarding : .authenticated
    }

    func markOnboardingComplete() {
        UserDefaults.standard.set(true, forKey: onboardingKey)
        state = .authenticated
        BackgroundSync.schedule()
    }

    func signOut() {
        KeychainHelper.delete(key: tokenKey)
        UserDefaults.standard.removeObject(forKey: userIdKey)
        UserDefaults.standard.removeObject(forKey: onboardingKey)
        APIClient.shared.clearSessionToken()
        userId = nil
        state = .unauthenticated
    }
}
