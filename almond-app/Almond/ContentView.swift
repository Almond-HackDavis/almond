import SwiftUI

struct ContentView: View {
    @AppStorage("onboarding_complete") private var onboardingComplete = false
    @State private var showingSplash = true

    var body: some View {
        ZStack {
            if showingSplash {
                SplashView(onComplete: { withAnimation(.easeOut(duration: 0.4)) { showingSplash = false } })
                    .transition(.opacity)
                    .zIndex(1)
            } else if onboardingComplete {
                DashboardView()
                    .transition(.opacity)
            } else {
                OnboardingView { onboardingComplete = true }
                    .transition(.opacity)
            }
        }
        .animation(.easeOut(duration: 0.4), value: showingSplash)
        .animation(.easeOut(duration: 0.4), value: onboardingComplete)
    }
}
