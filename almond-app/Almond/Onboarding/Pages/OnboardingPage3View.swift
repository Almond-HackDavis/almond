import SwiftUI

struct OnboardingPage3View: View {
    let onNext: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            OnboardingHeader()
                .padding(.top, 8)

            Spacer()

            VStack(alignment: .leading, spacing: 16) {
                Text("PERSONALISED INSIGHTS")
                    .font(.system(size: 10, weight: .medium, design: .monospaced))
                    .foregroundStyle(Color.labelTertiary)
                    .kerning(2.0)

                VStack(alignment: .leading, spacing: 0) {
                    Text("Healthier Habits,")
                        .font(Font.poppins(.bold, size: 38))
                        .foregroundStyle(Color.almondInk)
                    Text("Built Around")
                        .font(Font.poppins(.bold, size: 38))
                        .foregroundStyle(Color.almondInk)
                    Text("You.")
                        .font(Font.poppins(.bold, size: 38))
                        .foregroundStyle(Color.almondCocoa)
                }

                let receive = Text("Receive ")
                    .font(Font.poppins(.medium, size: 16))
                    .foregroundStyle(Color.labelSecondary)
                let suggestions = Text("personalised suggestions")
                    .font(Font.poppins(.mediumItalic, size: 16))
                    .foregroundStyle(Color.almondInk)
                let and = Text(" and ")
                    .font(Font.poppins(.medium, size: 16))
                    .foregroundStyle(Color.labelSecondary)
                let insights = Text("preventative insights")
                    .font(Font.poppins(.mediumItalic, size: 16))
                    .foregroundStyle(Color.almondInk)
                let based = Text(" based on your daily wearable data.")
                    .font(Font.poppins(.medium, size: 16))
                    .foregroundStyle(Color.labelSecondary)
                Text("\(receive)\(suggestions)\(and)\(insights)\(based)")
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
                OnboardingPageDots(total: 3, current: 2)
                Spacer()
                OnboardingNextButton(action: onNext)
            }
            .padding(.horizontal, 30)
            .padding(.bottom, 44)
        }
    }
}

#Preview {
    OnboardingPage3View(onNext: {})
}
