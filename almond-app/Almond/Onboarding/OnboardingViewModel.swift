import Foundation

@MainActor
final class OnboardingViewModel: ObservableObject {
    @Published var name: String = ""
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

    @Published var isSubmitting: Bool = false
    @Published var submitError: String?

    var isValid: Bool {
        heightCm != nil && weightKg != nil
    }

    /// Saves profile locally, then POSTs to backend. Returns true on success or 409 conflict.
    func submit() async -> Bool {
        guard let height = heightCm, let weight = weightKg else { return false }
        isSubmitting = true
        defer { isSubmitting = false }
        submitError = nil

        saveLocally(height: height, weight: weight)

        let req = OnboardingRequest(
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
        do {
            _ = try await APIClient.shared.submitOnboarding(req)
            return true
        } catch AlmondError.api(let code, _) where code == "http_409" {
            return true   // 409 = already completed; treat as done
        } catch {
            submitError = error.localizedDescription
            return false
        }
    }

    private func saveLocally(height: Double, weight: Double) {
        let d = UserDefaults.standard
        d.set(name,             forKey: "ob.name")
        d.set(age,              forKey: "ob.age")
        d.set(sex,              forKey: "ob.sex")
        d.set(height,           forKey: "ob.height_cm")
        d.set(weight,           forKey: "ob.weight_kg")
        d.set(smoking,          forKey: "ob.smoking")
        d.set(diabetes,         forKey: "ob.diabetes")
        d.set(familyHistoryCvd, forKey: "ob.family_history_cvd")
        d.set(onBpMedication,   forKey: "ob.on_bp_medication")
        if let bp  = systolicBp       { d.set(bp,  forKey: "ob.systolic_bp") }
        if let tc  = totalCholesterol { d.set(tc,  forKey: "ob.total_cholesterol") }
        if let hdl = hdlCholesterol   { d.set(hdl, forKey: "ob.hdl_cholesterol") }
        if let r   = raceEthnicity    { d.set(r,   forKey: "ob.race_ethnicity") }
    }
}
