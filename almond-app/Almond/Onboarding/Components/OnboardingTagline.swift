import SwiftUI

struct OnboardingTagline: View {
    var body: some View {
        (
            Text("\u{201C}An ")
                .font(Font.poppins(.bold, size: 20))
                .foregroundStyle(Color.almondCocoa)
            + Text("Almond ")
                .font(Font.poppins(.bold, size: 20))
                .foregroundStyle(Color.almondInk)
            + Text("a day.\u{201D}")
                .font(Font.poppins(.bold, size: 20))
                .foregroundStyle(Color.almondCocoa)
        )
    }
}
