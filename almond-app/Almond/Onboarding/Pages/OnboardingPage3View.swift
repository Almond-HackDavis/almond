import SwiftUI

struct OnboardingPage3View: View {
    let onNext: () -> Void
    let onSkip: () -> Void

    private let cocoaMuted = Color(red: 191/255, green: 137/255, blue: 105/255)

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

                headingText
                    .padding(.horizontal, 20)

                Spacer()

                Text(bodyAttributedString)
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

    private var headingText: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text("Healthier Habits,")
                .font(Font.poppins(.bold, size: 30))
                .foregroundStyle(Color.almondInk)
            Text("Built Around You.")
                .font(Font.poppins(.bold, size: 30))
                .foregroundStyle(Color.almondInk)
        }
    }

    private var bodyAttributedString: AttributedString {
        var result = AttributedString()
        let size: CGFloat = 22
        let medium = Font.poppins(.medium, size: size)
        let mediumItalic = Font.poppins(.mediumItalic, size: size)

        func segment(_ text: String, font: Font, color: Color) -> AttributedString {
            var s = AttributedString(text)
            s.font = font
            s.foregroundColor = color
            return s
        }

        result += segment("Receive ", font: medium, color: cocoaMuted)
        result += segment("personalized suggestions", font: mediumItalic, color: Color.almondInk)
        result += segment(" and ", font: medium, color: cocoaMuted)
        result += segment("preventative insights", font: mediumItalic, color: Color.almondInk)
        result += segment("\nbased on your daily cardiovascular data.", font: medium, color: cocoaMuted)
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
            OnboardingPageDots(total: 3, current: 2)
            Spacer()
            OnboardingNextButton(action: onNext)
        }
    }
}

#Preview {
    OnboardingPage3View(onNext: {}, onSkip: {})
}
