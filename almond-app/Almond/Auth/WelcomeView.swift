import AuthenticationServices
import SwiftUI

struct WelcomeView: View {
    @EnvironmentObject var authManager: AuthManager

    var body: some View {
        ZStack {
            Color.backgroundPrimary.ignoresSafeArea()

            VStack(spacing: 0) {
                Spacer()

                Image("AlmondWordmark")
                    .resizable()
                    .scaledToFit()
                    .frame(width: 180)
                    .padding(.bottom, 12)

                Text("Your long-term health, simplified.")
                    .font(.subheadline)
                    .foregroundStyle(Color.labelSecondary)

                Spacer()

                VStack(alignment: .leading, spacing: 18) {
                    FeatureRow(icon: "applewatch",        color: Color.brandPrimary,  text: "Reads your Apple Watch automatically")
                    FeatureRow(icon: "waveform.path.ecg", color: Color.riskElevated,  text: "Tracks heart rate, HRV and VO₂ Max")
                    FeatureRow(icon: "chart.xyaxis.line",  color: Color.chartSeries2,  text: "Long-term risk from ML + clinical equations")
                    FeatureRow(icon: "moon.zzz",           color: Color.almondSlate,   text: "Deep, REM and core sleep analysis")
                }
                .padding(.horizontal, 40)

                Spacer()

                VStack(spacing: 12) {
                    SignInWithAppleButton(.signIn, onRequest: { request in
                        request.requestedScopes = [.fullName, .email]
                    }, onCompletion: { result in
                        authManager.handleAppleAuth(result)
                    })
                    .signInWithAppleButtonStyle(.black)
                    .frame(height: 50)
                    .padding(.horizontal, 32)
                    .disabled(authManager.isAuthenticating)

                    if authManager.isAuthenticating {
                        ProgressView()
                            .tint(Color.brandPrimary)
                    }

                    if let error = authManager.authError {
                        Text(error)
                            .font(.caption)
                            .foregroundStyle(Color.riskHigh)
                            .multilineTextAlignment(.center)
                            .padding(.horizontal, 32)
                    }

                    Text("Secure sign-in via Apple. No password required.")
                        .font(.caption2)
                        .foregroundStyle(Color.labelTertiary)
                        .multilineTextAlignment(.center)
                }
                .padding(.bottom, 52)
            }
        }
    }
}

private struct FeatureRow: View {
    let icon: String
    let color: Color
    let text: String

    var body: some View {
        HStack(spacing: 14) {
            Image(systemName: icon)
                .font(.title3)
                .foregroundStyle(color)
                .frame(width: 28)
            Text(text)
                .font(.subheadline)
                .foregroundStyle(Color.labelPrimary)
            Spacer()
        }
    }
}
