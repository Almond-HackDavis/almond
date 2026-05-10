import SwiftUI

struct RiskDashboardView: View {
    @ObservedObject var vm: APIRiskViewModel

    var body: some View {
        NavigationStack {
            Group {
                switch vm.phase {
                case .idle:
                    idleView
                case .uploading:
                    statusView(message: "Uploading health data…", icon: "arrow.up.circle")
                case .polling(let attempt):
                    statusView(message: "Analyzing… (\(attempt))", icon: "gearshape.2")
                case .done(let output):
                    resultScrollView(output: output)
                case .failed(let message):
                    failedView(message: message)
                }
            }
            .navigationTitle("Risk Report")
        }
    }

    // MARK: - States

    private var idleView: some View {
        VStack(spacing: 16) {
            Image(systemName: "heart.text.square")
                .font(.system(size: 48))
                .foregroundStyle(Color.brandPrimary)
            Text("Tap below to compute your risk report.")
                .font(.subheadline)
                .foregroundStyle(Color.labelSecondary)
                .multilineTextAlignment(.center)
            Button("Compute Now") { vm.retry() }
                .buttonStyle(.borderedProminent)
                .tint(Color.brandPrimary)
        }
        .padding()
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private func statusView(message: String, icon: String) -> some View {
        VStack(spacing: 20) {
            ProgressView()
                .scaleEffect(1.5)
                .tint(Color.brandPrimary)
            Image(systemName: icon)
                .font(.title2)
                .foregroundStyle(Color.labelSecondary)
            Text(message)
                .font(.subheadline)
                .foregroundStyle(Color.labelSecondary)
                .multilineTextAlignment(.center)
        }
        .padding()
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private func failedView(message: String) -> some View {
        VStack(spacing: 16) {
            Image(systemName: "exclamationmark.triangle")
                .font(.system(size: 44))
                .foregroundStyle(Color.riskElevated)
            Text(message)
                .font(.subheadline)
                .foregroundStyle(Color.labelSecondary)
                .multilineTextAlignment(.center)
            Button("Try Again", action: vm.retry)
                .buttonStyle(.borderedProminent)
                .tint(Color.brandPrimary)
        }
        .padding()
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    // MARK: - Result

    @ViewBuilder
    private func resultScrollView(output: BridgeOutput) -> some View {
        ScrollView {
            VStack(spacing: 16) {
                scoresGrid(scores: output.scores)

                if !output.topDrivers.isEmpty {
                    driversCard(drivers: output.topDrivers)
                }

                if let summary = output.gemmaSummary {
                    summaryCard(summary: summary, disclaimer: output.disclaimer)
                }
            }
            .padding()
        }
        .refreshable { vm.retry() }
    }

    // MARK: - Score cards

    @ViewBuilder
    private func scoresGrid(scores: BridgeScores) -> some View {
        LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 14) {
            if let vitality = scores.vitalityScore {
                ScoreCard(
                    title: "Vitality Score",
                    value: String(format: "%.0f", vitality.value),
                    subtitle: vitalityLabel(vitality.value),
                    icon: "heart.fill",
                    color: vitalityColor(vitality.value)
                )
            }
            if let nhanes = scores.nhanesMortality2yr {
                ScoreCard(
                    title: "2-yr Mortality Risk",
                    value: String(format: "%.2f%%", nhanes.value * 100),
                    subtitle: "NHANES model",
                    icon: "chart.bar.fill",
                    color: Color.almondSlate
                )
            }
            if let fa = scores.fitnessAge {
                let delta = fa.delta
                let subtitle = delta < 0
                    ? "\(Int(abs(delta.rounded()))) yrs younger"
                    : "\(Int(delta.rounded())) yrs older"
                ScoreCard(
                    title: "Fitness Age",
                    value: String(format: "%.0f", fa.value),
                    subtitle: subtitle,
                    icon: "figure.run",
                    color: delta < 0 ? Color.riskLow : Color.riskElevated
                )
            }
        }
    }

    private func vitalityLabel(_ score: Double) -> String {
        switch score {
        case 80...: return "Excellent"
        case 60..<80: return "Good"
        case 40..<60: return "Moderate"
        default: return "Low"
        }
    }

    private func vitalityColor(_ score: Double) -> Color {
        switch score {
        case 80...: return Color.riskLow
        case 60..<80: return Color.brandPrimary
        case 40..<60: return Color.almondHoney
        default: return Color.riskElevated
        }
    }

    // MARK: - Top drivers

    private func driversCard(drivers: [TopDriver]) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Label("What's driving your score", systemImage: "chart.bar.xaxis")
                .font(.headline)
                .foregroundStyle(Color.labelPrimary)

            ForEach(drivers) { driver in
                VStack(spacing: 8) {
                    HStack(spacing: 10) {
                        Image(systemName: driver.direction == "better" ? "arrow.up.circle.fill" : "arrow.down.circle.fill")
                            .foregroundStyle(driver.direction == "better" ? Color.riskLow : Color.riskElevated)
                            .font(.title3)
                        VStack(alignment: .leading, spacing: 2) {
                            Text(driver.humanLabel)
                                .font(.subheadline.weight(.medium))
                                .foregroundStyle(Color.labelPrimary)
                            Text(String(format: "%+.2f pts", driver.contributionPts))
                                .font(.caption)
                                .foregroundStyle(Color.labelSecondary)
                        }
                        Spacer()
                    }
                    if driver.id != drivers.last?.id { Divider() }
                }
            }
        }
        .padding()
        .background(Color.surfaceCard, in: RoundedRectangle(cornerRadius: 16))
        .overlay(RoundedRectangle(cornerRadius: 16).stroke(Color.separator, lineWidth: 0.5))
    }

    // MARK: - Gemma summary

    private func summaryCard(summary: String, disclaimer: String?) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            Label("Personalized Guidance", systemImage: "sparkles")
                .font(.headline)
                .foregroundStyle(Color.labelPrimary)

            Text(summary)
                .font(.subheadline)
                .foregroundStyle(Color.labelSecondary)

            if let disclaimer {
                Divider()
                Text(disclaimer)
                    .font(.caption2)
                    .foregroundStyle(Color.labelTertiary)
                    .italic()
            }
        }
        .padding()
        .background(Color.surfaceCard, in: RoundedRectangle(cornerRadius: 16))
        .overlay(RoundedRectangle(cornerRadius: 16).stroke(Color.separator, lineWidth: 0.5))
    }
}

// MARK: - Score card tile

private struct ScoreCard: View {
    let title: String
    let value: String
    let subtitle: String
    let icon: String
    let color: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Image(systemName: icon).foregroundStyle(color)
            Text(title).font(.caption).foregroundStyle(Color.labelSecondary)
            Text(value).font(.title2.bold()).foregroundStyle(Color.labelPrimary)
            Text(subtitle.capitalized).font(.caption2).foregroundStyle(Color.labelTertiary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding()
        .background(Color.surfaceCard, in: RoundedRectangle(cornerRadius: 16))
        .overlay(RoundedRectangle(cornerRadius: 16).stroke(Color.separator, lineWidth: 0.5))
    }
}
