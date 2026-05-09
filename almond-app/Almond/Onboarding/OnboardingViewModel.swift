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

    var isValid: Bool {
        heightCm != nil && weightKg != nil
    }

    func save() {
        guard let height = heightCm, let weight = weightKg else { return }
        let d = UserDefaults.standard
        d.set(age,               forKey: "ob.age")
        d.set(sex,               forKey: "ob.sex")
        d.set(height,            forKey: "ob.height_cm")
        d.set(weight,            forKey: "ob.weight_kg")
        d.set(smoking,           forKey: "ob.smoking")
        d.set(diabetes,          forKey: "ob.diabetes")
        d.set(familyHistoryCvd,  forKey: "ob.family_history_cvd")
        d.set(onBpMedication,    forKey: "ob.on_bp_medication")
        if let bp   = systolicBp       { d.set(bp,   forKey: "ob.systolic_bp") }
        if let tc   = totalCholesterol { d.set(tc,   forKey: "ob.total_cholesterol") }
        if let hdl  = hdlCholesterol   { d.set(hdl,  forKey: "ob.hdl_cholesterol") }
        if let race = raceEthnicity    { d.set(race, forKey: "ob.race_ethnicity") }
    }
}
