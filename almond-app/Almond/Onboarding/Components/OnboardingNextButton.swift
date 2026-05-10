import SwiftUI

struct OnboardingNextButton: View {
    let action: () -> Void
    var disabled: Bool = false

    var body: some View {
        Button(action: action) {
            ZStack {
                Circle()
                    .fill(Color.almondCocoa.opacity(disabled ? 0.4 : 1))
                    .frame(width: 56, height: 56)
                Image(systemName: "chevron.right")
                    .font(.system(size: 18, weight: .semibold))
                    .foregroundStyle(.white)
            }
        }
        .disabled(disabled)
        .accessibilityLabel("Next")
    }
}
