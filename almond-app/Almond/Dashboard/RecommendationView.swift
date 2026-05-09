import SwiftUI

struct RecommendationView: View {
    @ObservedObject var vm: DashboardViewModel

    var body: some View {
        NavigationStack {
            Group {
                if vm.isLoading {
                    ProgressView("Loading recommendations…")
                } else if let rec = vm.risk?.geminiRecommendation {
                    recommendationContent(rec)
                } else {
                    ContentUnavailableView(
                        "No recommendations yet",
                        systemImage: "sparkles",
                        description: Text("Sync your Apple Watch data to get personalized actions.")
                    )
                }
            }
            .navigationTitle("Actions")
        }
    }

    @ViewBuilder
    private func recommendationContent(_ rec: GeminiRecommendation) -> some View {
        List {
            Section {
                Text(rec.summary)
                    .font(.body)
                    .padding(.vertical, 4)
            }

            Section("Your action plan") {
                ForEach(rec.actions) { action in
                    ActionCard(action: action)
                }
            }

            Section {
                Text(rec.disclaimer)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
    }
}

private struct ActionCard: View {
    let action: RecommendationAction

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Label(action.finding, systemImage: "magnifyingglass")
                .font(.subheadline.bold())
                .foregroundStyle(.primary)

            Text(action.action)
                .font(.subheadline)

            Text(action.rationale)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .padding(.vertical, 4)
    }
}
