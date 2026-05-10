import SwiftUI

struct OnboardingPage4View: View {
    let onNext: () -> Void
    let onSkip: () -> Void

    @State private var agreed = false

    var body: some View {
        ZStack {
            Color.backgroundPrimary.ignoresSafeArea()

            VStack(alignment: .leading, spacing: 0) {
                OnboardingHeader(onSkip: onSkip)
                    .padding(.top, 8)

                OnboardingTagline()
                    .padding(.horizontal, 24)
                    .padding(.top, 4)

                ScrollView(showsIndicators: false) {
                    VStack(alignment: .leading, spacing: 0) {
                        Text("Important\nInformation")
                            .font(Font.poppins(.bold, size: 34))
                            .foregroundStyle(Color.almondInk)
                            .multilineTextAlignment(.center)
                            .frame(maxWidth: .infinity)
                            .padding(.top, 24)
                            .padding(.horizontal, 24)

                        Text(disclaimerAttributedString)
                            .multilineTextAlignment(.center)
                            .frame(maxWidth: .infinity)
                            .lineSpacing(3)
                            .padding(.horizontal, 24)
                            .padding(.top, 20)
                    }
                }

                bottomBar
                    .padding(.horizontal, 24)
                    .padding(.vertical, 16)
            }
        }
    }

    private var bottomBar: some View {
        HStack(spacing: 12) {
            Toggle(isOn: $agreed) {
                Text("I understand and agree.")
                    .font(Font.poppins(.bold, size: 14))
                    .foregroundStyle(Color.almondInk)
            }
            .toggleStyle(CheckboxToggleStyle())

            Spacer()

            OnboardingNextButton(action: onNext, disabled: !agreed)
        }
    }

    private var disclaimerAttributedString: AttributedString {
        let size: CGFloat = 14
        let regular = Font.poppins(.regular, size: size)
        let semiBold = Font.poppins(.semiBold, size: size)
        let extraBold = Font.poppins(.extraBold, size: size)
        let ink = Color.almondInk

        func r(_ text: String) -> AttributedString {
            var s = AttributedString(text)
            s.font = regular
            s.foregroundColor = ink
            return s
        }

        func b(_ text: String) -> AttributedString {
            var s = AttributedString(text)
            s.font = semiBold
            s.foregroundColor = ink
            return s
        }

        func bullet() -> AttributedString {
            var s = AttributedString("\n*\n")
            s.font = extraBold
            s.foregroundColor = ink
            return s
        }

        var result = AttributedString()
        result += r("Almond provides wellness insights and preventative cardiovascular guidance based on wearable and health data.")
        result += bullet()
        result += r("Almond is ")
        result += b("not a medical device")
        result += r(" and ")
        result += b("does not diagnose, treat, cure, or prevent")
        result += r(" any disease or medical condition.")
        result += bullet()
        result += r("The information provided by Almond is intended for ")
        result += b("general wellness purposes only")
        result += r(" and ")
        result += b("should not replace")
        result += r(" professional medical advice, diagnosis, or treatment. ")
        result += b("Always consult a qualified healthcare professional")
        result += r(" regarding any questions or concerns about your health.")
        result += bullet()
        result += r("If you believe you may be experiencing a medical emergency, ")
        result += b("contact emergency services or seek immediate medical attention.")
        return result
    }
}

private struct CheckboxToggleStyle: ToggleStyle {
    func makeBody(configuration: Configuration) -> some View {
        Button {
            configuration.isOn.toggle()
        } label: {
            HStack(alignment: .center, spacing: 10) {
                ZStack {
                    RoundedRectangle(cornerRadius: 3)
                        .stroke(Color.almondInk, lineWidth: 1.5)
                        .frame(width: 18, height: 18)
                    if configuration.isOn {
                        Image(systemName: "checkmark")
                            .font(.system(size: 11, weight: .bold))
                            .foregroundStyle(Color.almondInk)
                    }
                }
                configuration.label
            }
        }
        .buttonStyle(.plain)
    }
}

#Preview {
    OnboardingPage4View(onNext: {}, onSkip: {})
}
