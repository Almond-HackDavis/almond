import SwiftUI
import AuthenticationServices

struct SignInWithAppleView: View {
    @EnvironmentObject var authManager: AuthManager
    @State private var errorMessage: String?
    @State private var isLoading = false

    var body: some View {
        VStack(spacing: 40) {
            Spacer()

            VStack(spacing: 16) {
                Image(systemName: "heart.fill")
                    .font(.system(size: 72))
                    .foregroundStyle(.pink)

                VStack(spacing: 6) {
                    Text("almond")
                        .font(.system(size: 40, weight: .bold, design: .rounded))
                    Text("Your long-term health, simplified.")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
            }

            Spacer()

            VStack(spacing: 16) {
                if let error = errorMessage {
                    Text(error)
                        .font(.caption)
                        .foregroundStyle(.red)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal)
                }

                if isLoading {
                    ProgressView()
                        .frame(height: 50)
                } else {
                    SignInWithAppleButton(.signIn) { request in
                        request.requestedScopes = [.fullName]
                    } onCompletion: { result in
                        handle(result)
                    }
                    .signInWithAppleButtonStyle(.black)
                    .frame(height: 50)
                    .padding(.horizontal, 40)
                }

                Text("By signing in you allow Almond to read Apple Watch health data to compute your risk scores.")
                    .font(.caption2)
                    .foregroundStyle(.tertiary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 32)
            }
            .padding(.bottom, 48)
        }
    }

    private func handle(_ result: Result<ASAuthorization, Error>) {
        switch result {
        case .success(let auth):
            guard let credential = auth.credential as? ASAuthorizationAppleIDCredential,
                  let tokenData = credential.identityToken,
                  let token = String(data: tokenData, encoding: .utf8) else {
                errorMessage = "Sign in failed: could not read identity token."
                return
            }
            isLoading = true
            errorMessage = nil
            Task {
                defer { isLoading = false }
                do {
                    try await authManager.signIn(identityToken: token)
                } catch {
                    errorMessage = error.localizedDescription
                }
            }
        case .failure(let error):
            if (error as NSError).code != ASAuthorizationError.canceled.rawValue {
                errorMessage = error.localizedDescription
            }
        }
    }
}
