import SwiftUI

struct OnboardingPage2View: View {
    let onNext: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            OnboardingHeader()
                .padding(.top, 8)

            Spacer()

            VStack(alignment: .leading, spacing: 16) {
                Text("CARDIOVASCULAR INTELLIGENCE")
                    .font(.system(size: 10, weight: .medium, design: .monospaced))
                    .foregroundStyle(Color.labelTertiary)
                    .kerning(2.0)

                VStack(alignment: .leading, spacing: 0) {
                    Text("From your")
                        .font(Font.poppins(.bold, size: 38))
                        .foregroundStyle(Color.almondInk)
                    Text("wrist to your")
                        .font(Font.poppins(.bold, size: 38))
                        .foregroundStyle(Color.almondInk)
                    Text("physician.")
                        .font(Font.poppins(.bold, size: 38))
                        .foregroundStyle(Color.almondCocoa)
                }

                let transform = Text("Transform your ")
                    .font(Font.poppins(.medium, size: 16))
                    .foregroundStyle(Color.labelSecondary)
                let wearable = Text("wearable data ")
                    .font(Font.poppins(.mediumItalic, size: 16))
                    .foregroundStyle(Color.almondInk)
                let rest = Text("into cardiovascular insights you and your physician can act on.")
                    .font(Font.poppins(.medium, size: 16))
                    .foregroundStyle(Color.labelSecondary)
                Text("\(transform)\(wearable)\(rest)")
                    .lineSpacing(4)
            }
            .padding(.horizontal, 32)

            Spacer()

            Text("Your data is never shared without your permission.")
                .font(.system(size: 10, weight: .medium, design: .monospaced))
                .foregroundStyle(Color.labelTertiary)
                .kerning(1.0)
                .padding(.horizontal, 32)
                .padding(.bottom, 20)

            HStack {
                OnboardingPageDots(total: 3, current: 1)
                Spacer()
                OnboardingNextButton(action: onNext)
            }
            .padding(.horizontal, 30)
            .padding(.bottom, 44)
        }
    }
}

#Preview {
    OnboardingPage2View(onNext: {})
}
