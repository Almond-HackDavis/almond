import SwiftUI

struct ContentView: View {
    @AppStorage("onboarding_complete") private var onboardingComplete = false
    @AppStorage("has_seen_welcome") private var hasSeenWelcome = false

    var body: some View {
        Group {
            if onboardingComplete {
                DashboardView()
            } else if hasSeenWelcome {
                OnboardingView(onComplete: { onboardingComplete = true })
            } else {
                WelcomeView(onGetStarted: { hasSeenWelcome = true })
            }
        }
        .animation(.easeInOut(duration: 0.35), value: hasSeenWelcome)
        .animation(.easeInOut(duration: 0.35), value: onboardingComplete)
    }
}
