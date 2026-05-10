import SwiftUI

struct OnboardingPage1View: View {
    let onNext: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            OnboardingHeader()
                .padding(.top, 8)

            Spacer()

            VStack(alignment: .leading, spacing: 0) {
                Text("\u{201C}An")
                    .font(Font.poppins(.bold, size: 52))
                    .foregroundStyle(Color.almondCocoa)
                Text("Almond")
                    .font(Font.poppins(.bold, size: 52))
                    .foregroundStyle(Color.almondInk)
                Text("a day.\u{201D}")
                    .font(Font.poppins(.bold, size: 52))
                    .foregroundStyle(Color.almondCocoa)
            }
            .padding(.horizontal, 32)

            Spacer().frame(height: 28)

            VStack(alignment: .leading, spacing: 6) {
                Text("PREVENTATIVE HEALTH")
                    .font(.system(size: 10, weight: .medium, design: .monospaced))
                    .foregroundStyle(Color.labelTertiary)
                    .kerning(2.0)

                let preventative = Text("Your preventative ")
                    .font(Font.poppins(.medium, size: 17))
                    .foregroundStyle(Color.labelSecondary)
                let coach = Text("cardiovascular health coach")
                    .font(Font.poppins(.mediumItalic, size: 17))
                    .foregroundStyle(Color.almondInk)
                let powered = Text(" powered by your Apple Watch.")
                    .font(Font.poppins(.medium, size: 17))
                    .foregroundStyle(Color.labelSecondary)
                Text("\(preventative)\(coach)\(powered)")
                    .lineSpacing(4)
            }
            .padding(.horizontal, 32)

            Spacer()

            HStack {
                OnboardingPageDots(total: 3, current: 0)
                Spacer()
                OnboardingNextButton(action: onNext)
            }
            .padding(.horizontal, 30)
            .padding(.bottom, 44)
        }
    }
}

#Preview {
    OnboardingPage1View(onNext: {})
}
