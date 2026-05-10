import SwiftUI

struct OnboardingPage2View: View {
    let onNext: () -> Void
    let onSkip: () -> Void

    var body: some View {
        ZStack {
            Color.backgroundPrimary.ignoresSafeArea()

            VStack(alignment: .leading, spacing: 0) {
                OnboardingHeader(onSkip: onSkip)
                    .padding(.top, 8)

                OnboardingTagline()
                    .padding(.horizontal, 24)
                    .padding(.top, 4)

                Spacer()

                Text(mainAttributedString)
                    .lineSpacing(4)
                    .padding(.horizontal, 24)

                Spacer()

                footerText
                    .padding(.horizontal, 24)
                    .padding(.bottom, 20)

                bottomBar
                    .padding(.horizontal, 30)
                    .padding(.bottom, 40)
            }
        }
    }

    private var mainAttributedString: AttributedString {
        var result = AttributedString()
        let size: CGFloat = 26
        let medium = Font.poppins(.medium, size: size)

        func segment(_ text: String, color: Color) -> AttributedString {
            var s = AttributedString(text)
            s.font = medium
            s.foregroundColor = color
            return s
        }

        result += segment("Transform your ", color: Color.almondCocoa)
        result += segment("wearable data ", color: Color.almondInk)
        result += segment("into understandable cardiovascular insights for both ", color: Color.almondCocoa)
        result += segment("you", color: Color.almondInk)
        result += segment(" and ", color: Color.almondCocoa)
        result += segment("your physician.", color: Color.almondInk)
        return result
    }

    private var footerText: some View {
        Text("Your data is securely stored and never shared without your permission.")
            .font(Font.poppins(.regular, size: 14))
            .foregroundStyle(Color.almondInk)
            .multilineTextAlignment(.center)
            .frame(maxWidth: .infinity)
    }

    private var bottomBar: some View {
        HStack {
            OnboardingPageDots(total: 3, current: 1)
            Spacer()
            OnboardingNextButton(action: onNext)
        }
    }
}

#Preview {
    OnboardingPage2View(onNext: {}, onSkip: {})
}
