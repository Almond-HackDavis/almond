import SwiftUI

struct OnboardingView: View {
    let onComplete: () -> Void

    @State private var page = 0
    @State private var showQuestionnaire = false

    var body: some View {
        if showQuestionnaire {
            HealthQuestionnaireView(onComplete: onComplete)
        } else {
            GeometryReader { geo in
                HStack(spacing: 0) {
                    OnboardingPage1View(onNext: advance, onSkip: skipToQuestionnaire)
                        .frame(width: geo.size.width)
                    OnboardingPage2View(onNext: advance, onSkip: skipToQuestionnaire)
                        .frame(width: geo.size.width)
                    OnboardingPage3View(onNext: advance, onSkip: skipToQuestionnaire)
                        .frame(width: geo.size.width)
                    OnboardingPage4View(onNext: goToQuestionnaire, onSkip: skipToQuestionnaire)
                        .frame(width: geo.size.width)
                }
                .offset(x: -CGFloat(page) * geo.size.width)
                .animation(.easeInOut(duration: 0.4), value: page)
            }
            .clipped()
        }
    }

    private func advance() {
        page += 1
    }

    private func goToQuestionnaire() {
        withAnimation(.easeInOut(duration: 0.35)) {
            showQuestionnaire = true
        }
    }

    private func skipToQuestionnaire() {
        withAnimation(.easeInOut(duration: 0.35)) {
            showQuestionnaire = true
        }
    }
}
