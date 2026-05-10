import SwiftUI

struct OnboardingPage4View: View {
    let onNext: () -> Void

    @State private var agreed = false

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            OnboardingHeader()
                .padding(.top, 8)

            ScrollView(showsIndicators: false) {
                VStack(alignment: .leading, spacing: 20) {
                    Text("BEFORE YOU BEGIN")
                        .font(.system(size: 10, weight: .medium, design: .monospaced))
                        .foregroundStyle(Color.labelTertiary)
                        .kerning(2.0)
                        .padding(.top, 28)

                    VStack(alignment: .leading, spacing: 0) {
                        Text("Important")
                            .font(Font.poppins(.bold, size: 38))
                            .foregroundStyle(Color.almondInk)
                        Text("Information.")
                            .font(Font.poppins(.bold, size: 38))
                            .foregroundStyle(Color.almondCocoa)
                    }

                    VStack(alignment: .leading, spacing: 16) {
                        disclaimerRow(
                            "Almond provides wellness insights and preventative cardiovascular guidance based on wearable and health data."
                        )
                        disclaimerRow(
                            body: "Almond is ",
                            bold: "not a medical device",
                            tail: " and does not diagnose, treat, cure, or prevent any disease or medical condition."
                        )
                        disclaimerRow(
                            body: "Information from Almond is for ",
                            bold: "general wellness purposes only",
                            tail: " and should not replace professional medical advice. Always consult a qualified healthcare professional."
                        )
                        disclaimerRow(
                            body: "If you believe you are experiencing a medical emergency, ",
                            bold: "contact emergency services immediately."
                        )
                    }
                    .padding(20)
                    .background(Color.almondCreamTint, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
                    .overlay(
                        RoundedRectangle(cornerRadius: 16, style: .continuous)
                            .stroke(Color.almondEspresso.opacity(0.08), lineWidth: 1)
                    )
                }
                .padding(.horizontal, 24)
                .padding(.bottom, 24)
            }

            VStack(spacing: 0) {
                Divider()
                    .overlay(Color.almondEspresso.opacity(0.08))

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
                .padding(.horizontal, 24)
                .padding(.vertical, 16)
            }
        }
    }

    @ViewBuilder
    private func disclaimerRow(_ text: String) -> some View {
        HStack(alignment: .top, spacing: 12) {
            Text("·")
                .font(.system(size: 14, weight: .bold))
                .foregroundStyle(Color.almondCocoa)
                .frame(width: 8)
            Text(text)
                .font(.system(size: 13))
                .foregroundStyle(Color.labelSecondary)
                .lineSpacing(3)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    @ViewBuilder
    private func disclaimerRow(body: String, bold: String, tail: String = "") -> some View {
        HStack(alignment: .top, spacing: 12) {
            Text("·")
                .font(.system(size: 14, weight: .bold))
                .foregroundStyle(Color.almondCocoa)
                .frame(width: 8)
            let bodyText = Text(body)
                .font(.system(size: 13))
                .foregroundStyle(Color.labelSecondary)
            let boldText = Text(bold)
                .font(.system(size: 13, weight: .semibold))
                .foregroundStyle(Color.almondInk)
            let tailText = Text(tail)
                .font(.system(size: 13))
                .foregroundStyle(Color.labelSecondary)
            Text("\(bodyText)\(boldText)\(tailText)")
                .lineSpacing(3)
                .fixedSize(horizontal: false, vertical: true)
        }
    }
}

private struct CheckboxToggleStyle: ToggleStyle {
    func makeBody(configuration: Configuration) -> some View {
        Button {
            configuration.isOn.toggle()
        } label: {
            HStack(alignment: .center, spacing: 10) {
                ZStack {
                    RoundedRectangle(cornerRadius: 4, style: .continuous)
                        .stroke(Color.almondEspresso.opacity(0.35), lineWidth: 1.5)
                        .frame(width: 20, height: 20)
                    if configuration.isOn {
                        RoundedRectangle(cornerRadius: 4, style: .continuous)
                            .fill(Color.almondCocoa)
                            .frame(width: 20, height: 20)
                        Image(systemName: "checkmark")
                            .font(.system(size: 11, weight: .bold))
                            .foregroundStyle(.white)
                    }
                }
                configuration.label
            }
        }
        .buttonStyle(.plain)
    }
}

#Preview {
    OnboardingPage4View(onNext: {})
}
