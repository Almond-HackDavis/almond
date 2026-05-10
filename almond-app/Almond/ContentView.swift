import SwiftUI

struct ContentView: View {
    @AppStorage("onboarding_complete") private var onboardingComplete = false

    var body: some View {
        if onboardingComplete {
            DashboardView()
                .transition(.opacity)
        } else {
            OnboardingView { onboardingComplete = true }
                .transition(.opacity)
        }
    }
}
