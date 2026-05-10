import SwiftUI

struct SplashView: View {
    let onComplete: () -> Void

    var body: some View {
        ZStack {
            Color.backgroundPrimary
                .ignoresSafeArea()

            VStack(spacing: 12) {
                Spacer()
                Image("AlmondMark")
                    .resizable()
                    .scaledToFit()
                    .frame(width: 160, height: 160)
                Image("AlmondWordmark")
                    .resizable()
                    .scaledToFit()
                    .frame(height: 32)
                Spacer()
            }
        }
        .task {
            try? await Task.sleep(for: .seconds(1.8))
            onComplete()
        }
    }
}
