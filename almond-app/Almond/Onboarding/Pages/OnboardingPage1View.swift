import SwiftUI

struct OnboardingPage1View: View {
    let onNext: () -> Void
    let onSkip: () -> Void

    var body: some View {
        ZStack {
            Color.backgroundPrimary.ignoresSafeArea()

            VStack(alignment: .leading, spacing: 0) {
                OnboardingHeader(onSkip: onSkip)
                    .padding(.top, 8)

                Spacer()

                heroText
                    .padding(.horizontal, 32)

                Spacer()

                subtitleText
                    .padding(.horizontal, 24)
                    .padding(.bottom, 24)

                bottomBar
                    .padding(.horizontal, 30)
                    .padding(.bottom, 40)
            }
        }
    }

    private var heroText: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text("\u{201C}An")
                .font(Font.poppins(.bold, size: 44))
                .foregroundStyle(Color.almondCocoa)
            Text("Almond")
                .font(Font.poppins(.bold, size: 44))
                .foregroundStyle(Color.almondInk)
            Text("a day.\u{201D}")
                .font(Font.poppins(.bold, size: 44))
                .foregroundStyle(Color.almondCocoa)
        }
        .lineSpacing(2)
    }

    private var subtitleText: some View {
        (
            Text("Your preventative ")
                .font(Font.poppins(.medium, size: 18))
                .foregroundStyle(Color.almondInk)
            + Text("cardiovascular health coach")
                .font(Font.poppins(.lightItalic, size: 18))
                .foregroundStyle(Color.almondInk)
            + Text(" powered by your Smart Wearable.")
                .font(Font.poppins(.medium, size: 18))
                .foregroundStyle(Color.almondInk)
        )
        .lineSpacing(4)
    }

    private var bottomBar: some View {
        HStack {
            OnboardingPageDots(total: 3, current: 0)
            Spacer()
            OnboardingNextButton(action: onNext)
        }
    }
}

#Preview {
    OnboardingPage1View(onNext: {}, onSkip: {})
}
