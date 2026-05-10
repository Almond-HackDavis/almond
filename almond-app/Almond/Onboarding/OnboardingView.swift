import SwiftUI

struct OnboardingView: View {
    let onComplete: () -> Void

    @State private var page = 0
    @State private var showQuestionnaire = false

    var body: some View {
        ZStack {
            Color.backgroundPrimary.ignoresSafeArea()

            if showQuestionnaire {
                HealthQuestionnaireView(onComplete: onComplete)
                    .transition(.opacity)
            } else {
                GeometryReader { geo in
                    HStack(spacing: 0) {
                        OnboardingPage1View(onNext: advance)
                            .frame(width: geo.size.width, height: geo.size.height)
                        OnboardingPage2View(onNext: advance)
                            .frame(width: geo.size.width, height: geo.size.height)
                        OnboardingPage3View(onNext: advance)
                            .frame(width: geo.size.width, height: geo.size.height)
                        OnboardingPage4View(onNext: goToQuestionnaire)
                            .frame(width: geo.size.width, height: geo.size.height)
                    }
                    .offset(x: -CGFloat(page) * geo.size.width)
                    .animation(.easeInOut(duration: 0.4), value: page)
                }
                .clipped()
            }
        }
        .animation(.easeInOut(duration: 0.35), value: showQuestionnaire)
    }

    private func advance() { page += 1 }

    private func goToQuestionnaire() {
        showQuestionnaire = true
    }
}
