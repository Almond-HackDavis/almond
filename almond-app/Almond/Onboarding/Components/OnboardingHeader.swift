import SwiftUI

struct OnboardingHeader: View {
    let onSkip: () -> Void

    var body: some View {
        HStack(alignment: .center) {
            Image("AlmondWordmark")
                .resizable()
                .scaledToFit()
                .frame(height: 40)
                .accessibilityLabel("Almond")
            Spacer()
            Button("Skip", action: onSkip)
                .font(Font.poppins(.regular, size: 14))
                .foregroundStyle(Color(red: 163/255, green: 150/255, blue: 144/255))
        }
        .padding(.horizontal, 24)
        .frame(height: 52)
    }
}
