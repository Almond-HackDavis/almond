import SwiftUI

struct SleepView: View {
    @ObservedObject var vm: DashboardViewModel

    var body: some View {
        NavigationStack {
            Group {
                if vm.isLoading && vm.snapshot == nil {
                    ProgressView("Reading sleep data…")
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else if let snap = vm.snapshot, !snap.sleepSessions.isEmpty {
                    sleepList(sessions: snap.sleepSessions)
                } else {
                    ContentUnavailableView(
                        "No sleep data",
                        systemImage: "moon.zzz",
                        description: Text("Wear your Apple Watch while sleeping to see sessions here.")
                    )
                }
            }
            .navigationTitle("Sleep")
        }
    }

    @ViewBuilder
    private func sleepList(sessions: [HealthSnapshot.SleepSummary]) -> some View {
        List(sessions.reversed()) { session in
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Text(session.date, style: .date)
                        .font(.headline)
                    Spacer()
                    Text(String(format: "%.1fh", session.durationHours))
                        .font(.headline)
                        .foregroundStyle(.blue)
                }

                HStack(spacing: 4) {
                    Image(systemName: "gauge.medium")
                        .foregroundStyle(.secondary)
                    Text(String(format: "Efficiency %.0f%%", session.efficiency * 100))
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }

                if session.deepMin + session.remMin + session.coreMin > 0 {
                    SleepStageBar(deep: session.deepMin, rem: session.remMin,
                                  core: session.coreMin, awake: session.awakeMin)
                }

                HStack(spacing: 12) {
                    StageChip(label: "Deep", minutes: session.deepMin, color: .indigo)
                    StageChip(label: "REM",  minutes: session.remMin,  color: .purple)
                    StageChip(label: "Core", minutes: session.coreMin, color: .blue)
                    StageChip(label: "Awake", minutes: session.awakeMin, color: .orange)
                }
            }
            .padding(.vertical, 4)
        }
        .refreshable { await vm.refresh() }
    }
}

private struct SleepStageBar: View {
    let deep: Int
    let rem: Int
    let core: Int
    let awake: Int

    private var total: Int { max(deep + rem + core + awake, 1) }

    var body: some View {
        GeometryReader { geo in
            HStack(spacing: 2) {
                RoundedRectangle(cornerRadius: 3).fill(Color.indigo)
                    .frame(width: geo.size.width * CGFloat(deep) / CGFloat(total))
                RoundedRectangle(cornerRadius: 3).fill(Color.purple)
                    .frame(width: geo.size.width * CGFloat(rem) / CGFloat(total))
                RoundedRectangle(cornerRadius: 3).fill(Color.blue)
                    .frame(width: geo.size.width * CGFloat(core) / CGFloat(total))
                RoundedRectangle(cornerRadius: 3).fill(Color.orange.opacity(0.7))
                    .frame(width: geo.size.width * CGFloat(awake) / CGFloat(total))
            }
        }
        .frame(height: 10)
    }
}

private struct StageChip: View {
    let label: String
    let minutes: Int
    let color: Color

    var body: some View {
        VStack(spacing: 2) {
            Text(label).font(.caption2).foregroundStyle(color)
            Text("\(minutes)m").font(.caption2.bold())
        }
    }
}
