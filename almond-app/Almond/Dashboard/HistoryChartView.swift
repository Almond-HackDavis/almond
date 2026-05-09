import SwiftUI
import Charts

struct HistoryChartView: View {
    @ObservedObject var vm: DashboardViewModel
    @State private var selectedSeries: SeriesKey = .ascvd

    enum SeriesKey: String, CaseIterable, Identifiable {
        var id: String { rawValue }
        case ascvd = "ASCVD Risk"
        case fitnessAge = "Fitness Age"
        case restingHR = "Resting HR"
        case vo2 = "VO₂ Max"
        case sleep = "Sleep Regularity"
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                Picker("Series", selection: $selectedSeries) {
                    ForEach(SeriesKey.allCases) { key in
                        Text(key.rawValue).tag(key)
                    }
                }
                .pickerStyle(.segmented)
                .padding()

                Group {
                    if vm.isLoading {
                        ProgressView("Loading trends…")
                            .frame(maxWidth: .infinity, maxHeight: .infinity)
                    } else if let history = vm.history {
                        chartView(history: history)
                    } else {
                        ContentUnavailableView(
                            "No trend data",
                            systemImage: "chart.xyaxis.line",
                            description: Text("Sync your Apple Watch data to see trends.")
                        )
                    }
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
            .navigationTitle("Trends")
        }
    }

    @ViewBuilder
    private func chartView(history: HistoryResponse) -> some View {
        let points = dataPoints(for: selectedSeries, history: history)

        Chart {
            ForEach(points) { point in
                LineMark(
                    x: .value("Date", point.date),
                    y: .value(selectedSeries.rawValue, point.value)
                )
                .foregroundStyle(Color.pink)

                AreaMark(
                    x: .value("Date", point.date),
                    y: .value(selectedSeries.rawValue, point.value)
                )
                .foregroundStyle(Color.pink.opacity(0.1))
            }
        }
        .chartXAxis {
            AxisMarks(values: .stride(by: .day, count: 14)) { _ in
                AxisGridLine()
                AxisValueLabel(format: .dateTime.month(.abbreviated).day())
            }
        }
        .padding()
    }

    private struct ChartPoint: Identifiable {
        let id = UUID()
        let date: Date
        let value: Double
    }

    private static let dayParser: DateFormatter = {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd"
        f.timeZone = TimeZone(identifier: "UTC")!
        return f
    }()

    private func dataPoints(for key: SeriesKey, history: HistoryResponse) -> [ChartPoint] {
        let fmt = Self.dayParser
        switch key {
        case .ascvd:
            return history.series.ascvd10yr.compactMap { (point: HistoryDataPoint) -> ChartPoint? in
                guard let d = fmt.date(from: point.date) else { return nil }
                return ChartPoint(date: d, value: point.value)
            }
        case .fitnessAge:
            return history.series.fitnessAge.compactMap { (point: HistoryDataPoint) -> ChartPoint? in
                guard let d = fmt.date(from: point.date) else { return nil }
                return ChartPoint(date: d, value: point.value)
            }
        case .restingHR:
            return history.series.restingHrDaily.compactMap { (point: BPMHistoryPoint) -> ChartPoint? in
                guard let d = fmt.date(from: point.date) else { return nil }
                return ChartPoint(date: d, value: point.bpm)
            }
        case .vo2:
            return history.series.vo2Max.compactMap { (point: HistoryDataPoint) -> ChartPoint? in
                guard let d = fmt.date(from: point.date) else { return nil }
                return ChartPoint(date: d, value: point.value)
            }
        case .sleep:
            return history.series.sleepRegularity.compactMap { (point: HistoryDataPoint) -> ChartPoint? in
                guard let d = fmt.date(from: point.date) else { return nil }
                return ChartPoint(date: d, value: point.value)
            }
        }
    }
}
