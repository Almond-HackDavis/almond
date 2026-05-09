import SwiftUI
import Charts

struct HistoryChartView: View {
    @ObservedObject var vm: DashboardViewModel

    enum SeriesKey: String, CaseIterable, Identifiable {
        var id: String { rawValue }
        case restingHR   = "Resting HR"
        case hrv         = "HRV"
        case steps       = "Steps"
        case activeEnergy = "Active Cal"
        case exerciseMin = "Exercise Min"
    }

    @State private var selected: SeriesKey = .restingHR

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(SeriesKey.allCases) { key in
                            Button(key.rawValue) { selected = key }
                                .buttonStyle(.bordered)
                                .tint(selected == key ? .pink : .secondary)
                        }
                    }
                    .padding(.horizontal)
                    .padding(.vertical, 8)
                }

                Group {
                    if vm.isLoading && vm.snapshot == nil {
                        ProgressView("Loading trends…")
                            .frame(maxWidth: .infinity, maxHeight: .infinity)
                    } else if let snap = vm.snapshot {
                        chartContent(snap: snap)
                    } else {
                        ContentUnavailableView("No data", systemImage: "chart.xyaxis.line")
                    }
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
            .navigationTitle("Trends")
        }
    }

    @ViewBuilder
    private func chartContent(snap: HealthSnapshot) -> some View {
        let points = series(for: selected, snap: snap)

        if points.isEmpty {
            ContentUnavailableView(
                "No \(selected.rawValue) data",
                systemImage: "chart.xyaxis.line",
                description: Text("Wear your Apple Watch to record this metric.")
            )
        } else {
            Chart {
                ForEach(points) { pt in
                    LineMark(x: .value("Date", pt.date, unit: .day),
                             y: .value(selected.rawValue, pt.value))
                        .foregroundStyle(.pink)
                    AreaMark(x: .value("Date", pt.date, unit: .day),
                             y: .value(selected.rawValue, pt.value))
                        .foregroundStyle(.pink.opacity(0.1))
                }
            }
            .chartXAxis {
                AxisMarks(values: .stride(by: .day, count: 7)) { _ in
                    AxisGridLine()
                    AxisValueLabel(format: .dateTime.month(.abbreviated).day())
                }
            }
            .padding()
        }
    }

    private func series(for key: SeriesKey, snap: HealthSnapshot) -> [HealthSnapshot.DatedValue] {
        switch key {
        case .restingHR:    return snap.restingHR
        case .hrv:          return snap.hrv
        case .steps:        return snap.stepsDaily
        case .activeEnergy: return snap.activeEnergy
        case .exerciseMin:  return snap.exerciseMinutes
        }
    }
}
