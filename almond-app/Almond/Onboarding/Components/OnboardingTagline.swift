import SwiftUI

struct OnboardingTagline: View {
    var body: some View {
        let open = Text("\u{201C}An ")
            .font(Font.poppins(.bold, size: 20))
            .foregroundStyle(Color.almondCocoa)
        let name = Text("Almond ")
            .font(Font.poppins(.bold, size: 20))
            .foregroundStyle(Color.almondInk)
        let close = Text("a day.\u{201D}")
            .font(Font.poppins(.bold, size: 20))
            .foregroundStyle(Color.almondCocoa)
        return Text("\(open)\(name)\(close)")
    }
}
