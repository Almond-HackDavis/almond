import SwiftUI

struct ScoresView: View {
    @ObservedObject var vm: DashboardViewModel
    @EnvironmentObject var authManager: AuthManager

    var body: some View {
        NavigationStack {
            Group {
                if vm.isLoading {
                    ProgressView("Loading scores…")
                } else if let risk = vm.risk {
                    scoresList(risk: risk)
                } else {
                    ContentUnavailableView(
                        "No scores yet",
                        systemImage: "heart.slash",
                        description: Text("Pull to sync your Apple Watch data.")
                    )
                }
            }
            .navigationTitle("Health Scores")
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button {
                        Task { await vm.syncAndRefresh() }
                    } label: {
                        if vm.isRefreshing {
                            ProgressView()
                        } else {
                            Image(systemName: "arrow.clockwise")
                        }
                    }
                    .disabled(vm.isRefreshing)
                }
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Sign Out") { authManager.signOut() }
                        .foregroundStyle(.secondary)
                }
            }
            .alert("Error", isPresented: .constant(vm.errorMessage != nil)) {
                Button("OK") { vm.errorMessage = nil }
            } message: {
                Text(vm.errorMessage ?? "")
            }
        }
    }

    @ViewBuilder
    private func scoresList(risk: RiskResponse) -> some View {
        List {
            Section("Cardiovascular") {
                ScoreRow(
                    title: "ASCVD 10-yr risk",
                    value: String(format: "%.1f%%", risk.scores.ascvd10yr.value),
                    category: risk.scores.ascvd10yr.category
                )
                ScoreRow(
                    title: "Framingham 10-yr CVD",
                    value: String(format: "%.1f%%", risk.scores.framingham10yrCvd.value),
                    category: risk.scores.framingham10yrCvd.category
                )
            }

            Section("Metabolic") {
                ScoreRow(
                    title: "Diabetes risk (FINDRISC)",
                    value: String(format: "%.0f / %.0f", risk.scores.findrisc10yrDiabetes.value, risk.scores.findrisc10yrDiabetes.max),
                    category: risk.scores.findrisc10yrDiabetes.category
                )
                ScoreRow(
                    title: "AHA Life's Essential 8",
                    value: String(format: "%.0f / %.0f", risk.scores.lifeEssential8.value, risk.scores.lifeEssential8.max),
                    category: risk.scores.lifeEssential8.category
                )
            }

            Section("Fitness") {
                ScoreRow(
                    title: "Fitness age",
                    value: "\(risk.scores.fitnessAge.value) yrs",
                    category: risk.scores.fitnessAge.delta > 0 ? "worse" : "better",
                    detail: "\(risk.scores.fitnessAge.delta > 0 ? "+" : "")\(risk.scores.fitnessAge.delta) vs chronological"
                )
            }

            Section("Mortality") {
                ScoreRow(
                    title: "NHANES 10-yr mortality",
                    value: String(format: "%.1f%%", risk.scores.nhanesMortality10yr.value),
                    category: "neutral",
                    detail: String(format: "95%% CI: %.1f–%.1f%%",
                                  risk.scores.nhanesMortality10yr.ciLow,
                                  risk.scores.nhanesMortality10yr.ciHigh)
                )
            }

            if !risk.topDrivers.isEmpty {
                Section("Top risk drivers") {
                    ForEach(risk.topDrivers) { driver in
                        DriverRow(driver: driver)
                    }
                }
            }
        }
        .refreshable { await vm.syncAndRefresh() }
    }
}

// MARK: - Sub-views

private struct ScoreRow: View {
    let title: String
    let value: String
    let category: String
    var detail: String? = nil

    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.subheadline)
                if let detail {
                    Text(detail)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
            Spacer()
            VStack(alignment: .trailing, spacing: 2) {
                Text(value)
                    .font(.headline)
                Text(category.capitalized)
                    .font(.caption2)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(categoryColor.opacity(0.15))
                    .foregroundStyle(categoryColor)
                    .clipShape(Capsule())
            }
        }
        .padding(.vertical, 2)
    }

    private var categoryColor: Color {
        switch category.lowercased() {
        case "low", "better", "optimal": return .green
        case "elevated", "moderate", "borderline": return .orange
        case "high", "worse": return .red
        default: return .secondary
        }
    }
}

private struct DriverRow: View {
    let driver: RiskDriver

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: driver.direction == "worse" ? "arrow.down.circle.fill" : "arrow.up.circle.fill")
                .foregroundStyle(driver.direction == "worse" ? .red : .green)

            VStack(alignment: .leading, spacing: 2) {
                Text(driver.humanLabel)
                    .font(.subheadline)
                Text(String(format: "Your value: %.1f  |  Norm: %.1f", driver.value, driver.populationNorm))
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
    }
}
