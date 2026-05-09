import Foundation

@MainActor
final class OnboardingViewModel: ObservableObject {
    @Published var age: Int = 30
    @Published var sex: String = "M"
    @Published var heightCm: Double? = nil
    @Published var weightKg: Double? = nil
    @Published var smoking: Bool = false
    @Published var diabetes: Bool = false
    @Published var familyHistoryCvd: Bool = false
    @Published var onBpMedication: Bool = false
    @Published var systolicBp: Int? = nil
    @Published var totalCholesterol: Int? = nil
    @Published var hdlCholesterol: Int? = nil
    @Published var raceEthnicity: String? = nil

    @Published var isSubmitting = false
    @Published var errorMessage: String?

    var isValid: Bool {
        heightCm != nil && weightKg != nil
    }

    func submit() async throws -> OnboardingResponse {
        guard let height = heightCm, let weight = weightKg else {
            throw AlmondError.api(code: "validation", message: "Height and weight are required.")
        }
        isSubmitting = true
        defer { isSubmitting = false }
        errorMessage = nil

        do {
            let request = OnboardingRequest(
                age: age,
                sex: sex,
                heightCm: height,
                weightKg: weight,
                smoking: smoking,
                diabetes: diabetes,
                familyHistoryCvd: familyHistoryCvd,
                raceEthnicity: raceEthnicity,
                systolicBp: systolicBp,
                totalCholesterol: totalCholesterol,
                hdlCholesterol: hdlCholesterol,
                onBpMedication: onBpMedication
            )
            return try await APIClient.shared.submitOnboarding(request)
        } catch {
            errorMessage = error.localizedDescription
            throw error
        }
    }
}
