import SwiftUI

struct OnboardingPageDots: View {
    let total: Int
    let current: Int

    var body: some View {
        HStack(spacing: 16) {
            ForEach(0..<total, id: \.self) { index in
                Capsule()
                    .fill(index == current ? Color.almondEspresso : Color.almondTan.opacity(0.3))
                    .frame(width: 13, height: 4)
            }
        }
    }
}
