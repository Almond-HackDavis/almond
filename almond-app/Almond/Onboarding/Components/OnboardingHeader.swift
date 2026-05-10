import SwiftUI

struct OnboardingHeader: View {
    var body: some View {
        HStack {
            Image("AlmondWordmark")
                .resizable()
                .scaledToFit()
                .frame(height: 40)
                .accessibilityLabel("Almond")
            Spacer()
        }
        .padding(.horizontal, 24)
        .frame(height: 52)
    }
}
