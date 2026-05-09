import SwiftUI
import Charts

struct ScoresView: View {
    @ObservedObject var vm: DashboardViewModel

    var body: some View {
        NavigationStack {
            Group {
                if vm.isLoading && vm.snapshot == nil {
                    ProgressView("Reading health data…")
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                        .tint(Color.brandPrimary)
                } else if let snap = vm.snapshot {
                    metricsGrid(snap: snap)
                } else {
                    ContentUnavailableView(
                        "No health data",
                        systemImage: "heart.slash",
                        description: Text(vm.errorMessage ?? "Allow health access in Settings → Privacy → Health → Almond.")
                    )
                }
            }
            .navigationTitle("Health Metrics")
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button { Task { await vm.refresh() } } label: {
                        if vm.isLoading { ProgressView().tint(Color.brandPrimary) }
                        else { Image(systemName: "arrow.clockwise").foregroundStyle(Color.brandPrimary) }
                    }
                    .disabled(vm.isLoading)
                }
            }
        }
    }

    @ViewBuilder
    private func metricsGrid(snap: HealthSnapshot) -> some View {
        ScrollView {
            VStack(spacing: 14) {
                // ── Cardiovascular score — full width ──
                CardioScoreCard(snap: snap)

                // ── Individual metric cards — two-column grid ──
                LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 14) {
                    MetricCard(
                        icon: "heart.fill", color: Color.brandPrimary,
                        title: "Resting HR",
                        value: snap.latestRestingHR.map { String(format: "%.0f", $0) } ?? "—",
                        unit: "bpm",
                        subtitle: snap.weekAvg(snap.restingHR).map { String(format: "7d avg %.0f bpm", $0) }
                    )
                    MetricCard(
                        icon: "waveform.path.ecg", color: Color.riskElevated,
                        title: "HRV (SDNN)",
                        value: snap.weekAvg(snap.hrv).map { String(format: "%.0f", $0) } ?? "—",
                        unit: "ms",
                        subtitle: "7-day average"
                    )
                    MetricCard(
                        icon: "lungs.fill", color: Color.chartSeries2,
                        title: "VO₂ Max",
                        value: snap.vo2Max.map { String(format: "%.1f", $0.value) } ?? "—",
                        unit: "ml/kg/min",
                        subtitle: snap.vo2Max.map { "Measured \(relativeDate($0.date))" }
                    )
                    MetricCard(
                        icon: "figure.walk", color: Color.riskLow,
                        title: "Daily Steps",
                        value: snap.weekAvg(snap.stepsDaily).map { String(format: "%.0f", $0) } ?? "—",
                        unit: "steps",
                        subtitle: "7-day average"
                    )
                    MetricCard(
                        icon: "flame.fill", color: Color.almondHoney,
                        title: "Active Energy",
                        value: snap.weekAvg(snap.activeEnergy).map { String(format: "%.0f", $0) } ?? "—",
                        unit: "kcal",
                        subtitle: "7-day average"
                    )
                    MetricCard(
                        icon: "figure.run", color: Color.brandPrimaryStrong,
                        title: "Exercise",
                        value: snap.weekAvg(snap.exerciseMinutes).map { String(format: "%.0f", $0) } ?? "—",
                        unit: "min / day",
                        subtitle: "7-day average"
                    )
                    if !snap.walkingHR.isEmpty {
                        MetricCard(
                            icon: "heart.circle", color: Color.almondCoral,
                            title: "Walking HR",
                            value: snap.weekAvg(snap.walkingHR).map { String(format: "%.0f", $0) } ?? "—",
                            unit: "bpm",
                            subtitle: "7-day average"
                        )
                    }
                    if !snap.wristTemp.isEmpty {
                        MetricCard(
                            icon: "thermometer.medium", color: Color.almondSlate,
                            title: "Wrist Temp",
                            value: snap.weekAvg(snap.wristTemp).map { String(format: "%+.2f", $0) } ?? "—",
                            unit: "°C vs baseline",
                            subtitle: "7-day average"
                        )
                    }
                }
            }
            .padding()
        }
        .refreshable { await vm.refresh() }
    }

    private func relativeDate(_ date: Date) -> String {
        let formatter = RelativeDateTimeFormatter()
        formatter.unitsStyle = .short
        return formatter.localizedString(for: date, relativeTo: Date())
    }
}

// MARK: - Cardiovascular score card

private struct CardioScoreCard: View {
    let snap: HealthSnapshot

    var body: some View {
        Group {
            if let score = snap.cardiovascularScore {
                HStack(alignment: .center, spacing: 16) {
                    CardioGauge(score: score)
                        .frame(maxWidth: .infinity)

                    Divider()

                    VStack(alignment: .leading, spacing: 6) {
                        Label("Cardiovascular\nHealth", systemImage: "gauge.with.needle")
                            .font(.caption.weight(.semibold))
                            .foregroundStyle(Color.labelSecondary)
                            .fixedSize(horizontal: false, vertical: true)

                        HStack(alignment: .lastTextBaseline, spacing: 3) {
                            Text("\(score)")
                                .font(.system(size: 42, weight: .bold, design: .rounded))
                                .foregroundStyle(Color.labelPrimary)
                                .contentTransition(.numericText())
                            Text("/ 100")
                                .font(.caption)
                                .foregroundStyle(Color.labelSecondary)
                        }

                        Text(CardioGauge.ratingLabel(for: score))
                            .font(.caption.weight(.medium))
                            .foregroundStyle(CardioGauge.arcColor(for: score))
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
            } else {
                HStack {
                    Label("Cardiovascular Health", systemImage: "gauge.with.needle")
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(Color.labelPrimary)
                    Spacer()
                    Text("Wear Apple Watch to generate score")
                        .font(.caption)
                        .foregroundStyle(Color.labelTertiary)
                        .multilineTextAlignment(.trailing)
                }
            }
        }
        .padding()
        .frame(maxWidth: .infinity)
        .background(Color.surfaceCard, in: RoundedRectangle(cornerRadius: 16))
        .overlay(RoundedRectangle(cornerRadius: 16).stroke(Color.separator, lineWidth: 0.5))
    }
}

// MARK: - Speedometer gauge

private struct CardioGauge: View {
    let score: Int

    private static let outerSize: CGFloat = 140
    private static let innerSize: CGFloat = 96
    private static let lineWidth: CGFloat = 12
    private static let labelR:    CGFloat = 60

    private var progress: Double { min(1, max(0, Double(score) / 100.0)) }

    static func arcColor(for score: Int) -> Color {
        switch score {
        case 80...: return Color.riskLow
        case 60..<80: return Color.almondHoney
        case 40..<60: return Color.riskElevated
        default: return Color.riskHigh
        }
    }

    static func ratingLabel(for score: Int) -> String {
        switch score {
        case 80...: return "Excellent"
        case 60..<80: return "Good"
        case 40..<60: return "Fair"
        default: return "Needs attention"
        }
    }

    var body: some View {
        ZStack {
            // 270° background track
            Circle()
                .trim(from: 0, to: 0.75)
                .stroke(Color.backgroundTertiary,
                        style: StrokeStyle(lineWidth: Self.lineWidth, lineCap: .round))
                .frame(width: Self.innerSize, height: Self.innerSize)
                .rotationEffect(.degrees(135))

            // Colored fill proportional to score
            Circle()
                .trim(from: 0, to: 0.75 * progress)
                .stroke(CardioGauge.arcColor(for: score),
                        style: StrokeStyle(lineWidth: Self.lineWidth, lineCap: .round))
                .frame(width: Self.innerSize, height: Self.innerSize)
                .rotationEffect(.degrees(135))
                .animation(.spring(duration: 1.0), value: score)

            // Arc interval labels: 0 at 7.5-o'clock, 50 at 12-o'clock, 100 at 4.5-o'clock
            Text("0")
                .font(.system(size: 9, weight: .medium, design: .rounded))
                .foregroundStyle(Color.labelTertiary)
                .offset(x: -Self.labelR * 0.707, y: Self.labelR * 0.707)
            Text("50")
                .font(.system(size: 9, weight: .medium, design: .rounded))
                .foregroundStyle(Color.labelTertiary)
                .offset(x: 0, y: -Self.labelR)
            Text("100")
                .font(.system(size: 9, weight: .medium, design: .rounded))
                .foregroundStyle(Color.labelTertiary)
                .offset(x: Self.labelR * 0.707, y: Self.labelR * 0.707)
        }
        .frame(width: Self.outerSize, height: Self.outerSize)
    }
}

// MARK: - Metric card

private struct MetricCard: View {
    let icon: String
    let color: Color
    let title: String
    let value: String
    let unit: String
    var subtitle: String? = nil

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Image(systemName: icon)
                .foregroundStyle(color)

            Text(title)
                .font(.caption)
                .foregroundStyle(Color.labelSecondary)

            HStack(alignment: .lastTextBaseline, spacing: 4) {
                Text(value)
                    .font(.title2.bold())
                    .foregroundStyle(Color.labelPrimary)
                Text(unit)
                    .font(.caption2)
                    .foregroundStyle(Color.labelTertiary)
            }

            if let sub = subtitle {
                Text(sub)
                    .font(.caption2)
                    .foregroundStyle(Color.labelTertiary)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding()
        .background(Color.surfaceCard, in: RoundedRectangle(cornerRadius: 16))
        .overlay(RoundedRectangle(cornerRadius: 16).stroke(Color.separator, lineWidth: 0.5))
    }
}
