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
                        if vm.isLoading { ProgressView() }
                        else { Image(systemName: "arrow.clockwise") }
                    }
                    .disabled(vm.isLoading)
                }
            }
        }
    }

    @ViewBuilder
    private func metricsGrid(snap: HealthSnapshot) -> some View {
        ScrollView {
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 16) {
                // Resting HR
                MetricCard(
                    icon: "heart.fill", color: .red,
                    title: "Resting HR",
                    value: snap.latestRestingHR.map { String(format: "%.0f", $0) } ?? "—",
                    unit: "bpm",
                    subtitle: snap.weekAvg(snap.restingHR).map { String(format: "7d avg %.0f bpm", $0) }
                )

                // HRV
                MetricCard(
                    icon: "waveform.path.ecg", color: .pink,
                    title: "HRV (SDNN)",
                    value: snap.weekAvg(snap.hrv).map { String(format: "%.0f", $0) } ?? "—",
                    unit: "ms",
                    subtitle: "7-day average"
                )

                // VO2 Max
                MetricCard(
                    icon: "lungs.fill", color: .blue,
                    title: "VO₂ Max",
                    value: snap.vo2Max.map { String(format: "%.1f", $0.value) } ?? "—",
                    unit: "ml/kg/min",
                    subtitle: snap.vo2Max.map { "Measured \(relativeDate($0.date))" }
                )

                // Steps
                MetricCard(
                    icon: "figure.walk", color: .green,
                    title: "Daily Steps",
                    value: snap.weekAvg(snap.stepsDaily).map { String(format: "%.0f", $0) } ?? "—",
                    unit: "steps",
                    subtitle: "7-day average"
                )

                // Active Energy
                MetricCard(
                    icon: "flame.fill", color: .orange,
                    title: "Active Energy",
                    value: snap.weekAvg(snap.activeEnergy).map { String(format: "%.0f", $0) } ?? "—",
                    unit: "kcal",
                    subtitle: "7-day average"
                )

                // Exercise Minutes
                MetricCard(
                    icon: "figure.run", color: .purple,
                    title: "Exercise",
                    value: snap.weekAvg(snap.exerciseMinutes).map { String(format: "%.0f", $0) } ?? "—",
                    unit: "min / day",
                    subtitle: "7-day average"
                )

                // Walking HR
                if !snap.walkingHR.isEmpty {
                    MetricCard(
                        icon: "heart.circle", color: .teal,
                        title: "Walking HR",
                        value: snap.weekAvg(snap.walkingHR).map { String(format: "%.0f", $0) } ?? "—",
                        unit: "bpm",
                        subtitle: "7-day average"
                    )
                }

                // Wrist Temp
                if !snap.wristTemp.isEmpty {
                    MetricCard(
                        icon: "thermometer.medium", color: .indigo,
                        title: "Wrist Temp",
                        value: snap.weekAvg(snap.wristTemp).map { String(format: "%+.2f", $0) } ?? "—",
                        unit: "°C vs baseline",
                        subtitle: "7-day average"
                    )
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
            HStack {
                Image(systemName: icon)
                    .foregroundStyle(color)
                Spacer()
            }
            Text(title)
                .font(.caption)
                .foregroundStyle(.secondary)

            HStack(alignment: .lastTextBaseline, spacing: 4) {
                Text(value)
                    .font(.title2.bold())
                Text(unit)
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }

            if let sub = subtitle {
                Text(sub)
                    .font(.caption2)
                    .foregroundStyle(.tertiary)
            }
        }
        .padding()
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 16))
    }
}
