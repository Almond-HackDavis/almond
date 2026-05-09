import AuthenticationServices
import Foundation

@MainActor
final class AuthManager: ObservableObject {
    @Published var isAuthenticated: Bool = false
    @Published var needsOnboarding: Bool = false
    @Published var isAuthenticating: Bool = false
    @Published var authError: String?

    init() {
        if let token = KeychainHelper.shared.readToken() {
            Task { await APIClient.shared.setSessionToken(token) }
            isAuthenticated = true
            needsOnboarding = UserDefaults.standard.bool(forKey: "needs_onboarding")
        }
    }

    // Called from WelcomeView's SignInWithAppleButton onCompletion handler.
    func handleAppleAuth(_ result: Result<ASAuthorization, Error>) {
        switch result {
        case .failure(let error):
            if (error as? ASAuthorizationError)?.code != .canceled {
                authError = error.localizedDescription
            }
        case .success(let auth):
            guard
                let cred = auth.credential as? ASAuthorizationAppleIDCredential,
                let tokenData = cred.identityToken,
                let identityToken = String(data: tokenData, encoding: .utf8)
            else {
                authError = "Could not read Apple identity token."
                return
            }
            isAuthenticating = true
            Task { await login(identityToken: identityToken) }
        }
    }

    private func login(identityToken: String) async {
        defer { isAuthenticating = false }
        do {
            let response = try await APIClient.shared.login(appleIdentityToken: identityToken)
            KeychainHelper.shared.saveToken(response.sessionToken)
            await APIClient.shared.setSessionToken(response.sessionToken)
            UserDefaults.standard.set(response.needsOnboarding, forKey: "needs_onboarding")
            needsOnboarding = response.needsOnboarding
            isAuthenticated = true
        } catch {
            authError = error.localizedDescription
        }
    }

    func markOnboardingComplete() {
        UserDefaults.standard.set(false, forKey: "needs_onboarding")
        needsOnboarding = false
    }

    func signOut() {
        KeychainHelper.shared.deleteToken()
        Task { await APIClient.shared.clearSessionToken() }
        isAuthenticated = false
        needsOnboarding = false
        UserDefaults.standard.set(false, forKey: "needs_onboarding")
    }
}
