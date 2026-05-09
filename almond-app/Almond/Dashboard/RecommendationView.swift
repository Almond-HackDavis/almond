import SwiftUI

struct SleepView: View {
    @ObservedObject var vm: DashboardViewModel

    var body: some View {
        NavigationStack {
            Group {
                if vm.isLoading && vm.snapshot == nil {
                    ProgressView("Reading sleep data…")
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                        .tint(Color.brandPrimary)
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
                        .foregroundStyle(Color.labelPrimary)
                    Spacer()
                    Text(String(format: "%.1fh", session.durationHours))
                        .font(.headline)
                        .foregroundStyle(Color.brandPrimary)
                }

                HStack(spacing: 4) {
                    Image(systemName: "gauge.medium")
                        .foregroundStyle(Color.labelSecondary)
                    Text(String(format: "Efficiency %.0f%%", session.efficiency * 100))
                        .font(.subheadline)
                        .foregroundStyle(Color.labelSecondary)
                }

                if session.deepMin + session.remMin + session.coreMin > 0 {
                    SleepStageBar(deep: session.deepMin, rem: session.remMin,
                                  core: session.coreMin, awake: session.awakeMin)
                }

                HStack(spacing: 12) {
                    StageChip(label: "Deep",  minutes: session.deepMin,  color: Color.brandPrimaryStrong)
                    StageChip(label: "REM",   minutes: session.remMin,   color: Color.brandPrimary)
                    StageChip(label: "Core",  minutes: session.coreMin,  color: Color.almondTan)
                    StageChip(label: "Awake", minutes: session.awakeMin, color: Color.almondHoney)
                }
            }
            .padding(.vertical, 4)
            .listRowBackground(Color.surfaceCard)
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
                RoundedRectangle(cornerRadius: 3).fill(Color.brandPrimaryStrong)
                    .frame(width: geo.size.width * CGFloat(deep) / CGFloat(total))
                RoundedRectangle(cornerRadius: 3).fill(Color.brandPrimary)
                    .frame(width: geo.size.width * CGFloat(rem) / CGFloat(total))
                RoundedRectangle(cornerRadius: 3).fill(Color.almondTan)
                    .frame(width: geo.size.width * CGFloat(core) / CGFloat(total))
                RoundedRectangle(cornerRadius: 3).fill(Color.almondHoney.opacity(0.8))
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
            Text("\(minutes)m").font(.caption2.bold()).foregroundStyle(Color.labelPrimary)
        }
    }
}
