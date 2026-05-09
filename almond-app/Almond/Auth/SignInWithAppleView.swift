import SwiftUI

struct WelcomeView: View {
    let onGetStarted: () -> Void

    var body: some View {
        VStack(spacing: 0) {
            Spacer()

            // Logo + wordmark
            VStack(spacing: 16) {
                Image(systemName: "heart.fill")
                    .font(.system(size: 72))
                    .foregroundStyle(.pink)

                VStack(spacing: 6) {
                    Text("almond")
                        .font(.system(size: 42, weight: .bold, design: .rounded))
                    Text("Your long-term health, simplified.")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
            }

            Spacer()

            // Feature highlights
            VStack(alignment: .leading, spacing: 18) {
                FeatureRow(icon: "applewatch",       color: .pink,   text: "Reads your Apple Watch automatically")
                FeatureRow(icon: "waveform.path.ecg", color: .red,   text: "Tracks heart rate, HRV and VO₂ Max")
                FeatureRow(icon: "chart.xyaxis.line", color: .blue,  text: "30-day trends for every metric")
                FeatureRow(icon: "moon.zzz",          color: .indigo, text: "Deep, REM and core sleep analysis")
            }
            .padding(.horizontal, 40)

            Spacer()

            // CTA
            VStack(spacing: 12) {
                Button(action: onGetStarted) {
                    Text("Get Started")
                        .font(.headline)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 16)
                        .background(.pink)
                        .foregroundStyle(.white)
                        .clipShape(RoundedRectangle(cornerRadius: 14))
                }
                .padding(.horizontal, 32)

                Text("No account required. Your data stays on device.")
                    .font(.caption2)
                    .foregroundStyle(.tertiary)
                    .multilineTextAlignment(.center)
            }
            .padding(.bottom, 52)
        }
    }
}

private struct FeatureRow: View {
    let icon: String
    let color: Color
    let text: String

    var body: some View {
        HStack(spacing: 14) {
            Image(systemName: icon)
                .font(.title3)
                .foregroundStyle(color)
                .frame(width: 28)
            Text(text)
                .font(.subheadline)
                .foregroundStyle(.primary.opacity(0.85))
            Spacer()
        }
    }
}
