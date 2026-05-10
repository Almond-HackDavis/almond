import SwiftUI

struct ContentView: View {
    @AppStorage("onboarding_complete") private var onboardingComplete = false

    var body: some View {
        if onboardingComplete {
            DashboardView()
        } else {
            OnboardingView { onboardingComplete = true }
        }
    }
}
