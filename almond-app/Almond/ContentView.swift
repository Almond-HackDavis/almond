import SwiftUI

struct ContentView: View {
    @EnvironmentObject var authManager: AuthManager

    var body: some View {
        Group {
            switch authManager.state {
            case .unauthenticated:
                SignInWithAppleView()
            case .needsOnboarding:
                OnboardingView()
            case .authenticated:
                DashboardView()
            }
        }
        .animation(.easeInOut, value: authManager.state)
    }
}
