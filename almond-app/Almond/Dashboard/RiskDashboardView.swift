import SwiftUI
import Charts

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
                case .polling(let status):
                    statusView(message: statusLabel(status), icon: "gearshape.2")
                case .done(let result):
                    resultScrollView(result: result)
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
    private func resultScrollView(result: RiskResponseFull) -> some View {
        ScrollView {
            VStack(spacing: 16) {
                scoresGrid(scores: result.scores)

                if !result.topDrivers.isEmpty {
                    driversCard(drivers: result.topDrivers)
                }

                if let rec = result.geminiRecommendation {
                    recommendationCard(rec: rec)
                }

                if let history = vm.historyResponse {
                    historyCard(history: history)
                }
            }
            .padding()
        }
        .refreshable { vm.retry() }
    }

    // MARK: - Score cards

    @ViewBuilder
    private func scoresGrid(scores: RiskScores) -> some View {
        LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 14) {
            if let ascvd = scores.ascvd10yr {
                ScoreCard(title: "ASCVD 10-yr",
                          value: String(format: "%.1f%%", ascvd.value),
                          category: ascvd.category,
                          icon: "heart.fill", color: Color.riskElevated)
            }
            if let fram = scores.framingham10yrCvd {
                ScoreCard(title: "Framingham CVD",
                          value: String(format: "%.1f%%", fram.value),
                          category: fram.category,
                          icon: "waveform.path.ecg", color: Color.brandPrimary)
            }
            if let find = scores.findrisc10yrDiabetes {
                ScoreCard(title: "Diabetes Risk",
                          value: String(format: "%.0f / %.0f", find.value, find.max),
                          category: find.category,
                          icon: "drop.fill", color: Color.almondHoney)
            }
            if let le8 = scores.lifeEssential8 {
                ScoreCard(title: "Life's Essential 8",
                          value: String(format: "%.0f / %.0f", le8.value, le8.max),
                          category: le8.category,
                          icon: "8.circle.fill", color: Color.chartSeries2)
            }
            if let fa = scores.fitnessAge {
                ScoreCard(title: "Fitness Age",
                          value: "\(fa.value) yrs",
                          category: fa.delta > 0 ? "older" : "younger",
                          icon: "figure.run", color: fa.delta > 0 ? Color.riskElevated : Color.riskLow)
            }
            if let nhanes = scores.nhanesMortality2yr {
                ScoreCard(title: "2-yr Mortality",
                          value: String(format: "%.1f%%", nhanes.value),
                          category: "NHANES model",
                          icon: "chart.bar.fill", color: Color.almondSlate)
            }
        }
    }

    // MARK: - Drivers

    private func driversCard(drivers: [RiskDriver]) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Label("Top Risk Drivers", systemImage: "list.number")
                .font(.headline)
                .foregroundStyle(Color.labelPrimary)

            ForEach(drivers) { driver in
                HStack(spacing: 12) {
                    Image(systemName: driver.direction == "worse" ? "arrow.up.circle.fill" : "arrow.down.circle.fill")
                        .foregroundStyle(driver.direction == "worse" ? Color.riskElevated : Color.riskLow)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(driver.humanLabel)
                            .font(.subheadline.weight(.medium))
                            .foregroundStyle(Color.labelPrimary)
                        Text("Your \(String(format: "%.1f", driver.value)) vs norm \(String(format: "%.1f", driver.populationNorm))")
                            .font(.caption)
                            .foregroundStyle(Color.labelSecondary)
                    }
                    Spacer()
                    Text(String(format: "×%.2f", driver.weight))
                        .font(.caption.monospacedDigit())
                        .foregroundStyle(Color.labelTertiary)
                }
            }
        }
        .padding()
        .background(Color.surfaceCard, in: RoundedRectangle(cornerRadius: 16))
        .overlay(RoundedRectangle(cornerRadius: 16).stroke(Color.separator, lineWidth: 0.5))
    }

    // MARK: - Gemini recommendation

    private func recommendationCard(rec: GeminiRecommendation) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            Label("Personalized Guidance", systemImage: "sparkles")
                .font(.headline)
                .foregroundStyle(Color.labelPrimary)

            Text(rec.summary)
                .font(.subheadline)
                .foregroundStyle(Color.labelSecondary)

            Divider()

            ForEach(rec.actions) { action in
                VStack(alignment: .leading, spacing: 4) {
                    Label(action.finding, systemImage: "magnifyingglass")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(Color.labelSecondary)
                    Text(action.action)
                        .font(.subheadline.weight(.medium))
                        .foregroundStyle(Color.labelPrimary)
                    Text(action.rationale)
                        .font(.caption)
                        .foregroundStyle(Color.labelTertiary)
                }
                if action.id != rec.actions.last?.id {
                    Divider()
                }
            }

            Divider()

            Text(rec.disclaimer)
                .font(.caption2)
                .foregroundStyle(Color.labelTertiary)
                .italic()
        }
        .padding()
        .background(Color.surfaceCard, in: RoundedRectangle(cornerRadius: 16))
        .overlay(RoundedRectangle(cornerRadius: 16).stroke(Color.separator, lineWidth: 0.5))
    }

    // MARK: - History chart (API-sourced)

    @ViewBuilder
    private func historyCard(history: HistoryResponse) -> some View {
        if let series = history.series.ascvd10yr, !series.isEmpty {
            VStack(alignment: .leading, spacing: 10) {
                Label("ASCVD Risk Trend", systemImage: "chart.xyaxis.line")
                    .font(.headline)
                    .foregroundStyle(Color.labelPrimary)

                let points = series.compactMap { pt -> (Date, Double)? in
                    guard let date = isoDate(pt.date) else { return nil }
                    return (date, pt.value)
                }

                Chart {
                    ForEach(points, id: \.0) { (date, value) in
                        LineMark(x: .value("Date", date, unit: .day),
                                 y: .value("ASCVD %", value))
                            .foregroundStyle(Color.riskElevated)
                        AreaMark(x: .value("Date", date, unit: .day),
                                 y: .value("ASCVD %", value))
                            .foregroundStyle(Color.riskElevated.opacity(0.12))
                    }
                }
                .frame(height: 120)
                .chartXAxis {
                    AxisMarks(values: .stride(by: .day, count: 14)) { _ in
                        AxisGridLine().foregroundStyle(Color.divider)
                        AxisValueLabel(format: .dateTime.month(.abbreviated).day())
                            .foregroundStyle(Color.labelTertiary)
                    }
                }
            }
            .padding()
            .background(Color.surfaceCard, in: RoundedRectangle(cornerRadius: 16))
            .overlay(RoundedRectangle(cornerRadius: 16).stroke(Color.separator, lineWidth: 0.5))
        }
    }

    // MARK: - Helpers

    private func statusLabel(_ status: String) -> String {
        switch status {
        case "pending":      return "Waiting for processing to start…"
        case "scoring":      return "Running ML models…"
        case "recommending": return "Generating personalized guidance…"
        default:             return "Processing…"
        }
    }

    private func isoDate(_ string: String) -> Date? {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd"
        f.timeZone = TimeZone(identifier: "UTC")
        return f.date(from: string)
    }
}

// MARK: - Score card tile

private struct ScoreCard: View {
    let title: String
    let value: String
    let category: String
    let icon: String
    let color: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Image(systemName: icon)
                .foregroundStyle(color)

            Text(title)
                .font(.caption)
                .foregroundStyle(Color.labelSecondary)

            Text(value)
                .font(.title2.bold())
                .foregroundStyle(Color.labelPrimary)

            Text(category.capitalized)
                .font(.caption2)
                .foregroundStyle(Color.labelTertiary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding()
        .background(Color.surfaceCard, in: RoundedRectangle(cornerRadius: 16))
        .overlay(RoundedRectangle(cornerRadius: 16).stroke(Color.separator, lineWidth: 0.5))
    }
}
