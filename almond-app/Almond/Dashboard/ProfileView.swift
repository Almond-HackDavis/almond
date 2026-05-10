import SwiftUI

private enum ProfileField: Hashable {
    case heightCm, weightKg, systolicBp, totalCholesterol, hdlCholesterol
}

struct ProfileView: View {
    @AppStorage("ob.name")               private var name              = ""
    @AppStorage("ob.age")                private var age               = 30
    @AppStorage("ob.sex")                private var sex               = "M"
    @AppStorage("ob.height_cm")          private var heightCm          = 0.0
    @AppStorage("ob.weight_kg")          private var weightKg          = 0.0
    @AppStorage("ob.smoking")            private var smoking           = false
    @AppStorage("ob.diabetes")           private var diabetes          = false
    @AppStorage("ob.family_history_cvd") private var familyHistoryCvd = false
    @AppStorage("ob.on_bp_medication")   private var onBpMedication    = false
    @AppStorage("ob.systolic_bp")        private var systolicBp        = 0
    @AppStorage("ob.total_cholesterol")  private var totalCholesterol  = 0
    @AppStorage("ob.hdl_cholesterol")    private var hdlCholesterol    = 0
    @AppStorage("ob.race_ethnicity")     private var raceEthnicity     = ""

    @FocusState private var focusedField: ProfileField?

    #if DEBUG
    @AppStorage("onboarding_complete") private var onboardingComplete = false
    #endif

    private var bmi: Double? {
        guard heightCm > 0, weightKg > 0 else { return nil }
        let h = heightCm / 100
        return weightKg / (h * h)
    }

    private var bmiCategory: String {
        guard let b = bmi else { return "" }
        switch b {
        case ..<18.5: return "Underweight"
        case 18.5..<25: return "Normal"
        case 25..<30: return "Overweight"
        default: return "Obese"
        }
    }

    var body: some View {
        NavigationStack {
            Form {
                // MARK: Identity
                Section {
                    HStack {
                        Spacer()
                        VStack(spacing: 10) {
                            Image("AlmondMark")
                                .resizable()
                                .scaledToFit()
                                .frame(width: 56, height: 56)
                            if !name.isEmpty {
                                Text(name)
                                    .font(.title3.bold())
                                    .foregroundStyle(Color.labelPrimary)
                            }
                        }
                        Spacer()
                    }
                    .padding(.vertical, 8)
                    .listRowBackground(Color.clear)
                }

                // MARK: Personal
                Section("Personal") {
                    LabeledContent("Name") {
                        TextField("Your name", text: $name)
                            .multilineTextAlignment(.trailing)
                    }
                    Stepper("Age: \(age)", value: $age, in: 18...100)
                    Picker("Sex", selection: $sex) {
                        Text("Male").tag("M")
                        Text("Female").tag("F")
                    }
                    Picker("Race / ethnicity", selection: $raceEthnicity) {
                        Text("Prefer not to say").tag("")
                        Text("White").tag("white")
                        Text("Black").tag("black")
                        Text("Asian").tag("asian")
                        Text("Hispanic").tag("hispanic")
                        Text("Other").tag("other")
                    }
                }

                // MARK: Body
                Section("Body measurements") {
                    LabeledContent("Height") {
                        HStack {
                            TextField("cm", value: $heightCm, format: .number)
                                .multilineTextAlignment(.trailing)
                                .keyboardType(.decimalPad)
                                .focused($focusedField, equals: .heightCm)
                            Text("cm").foregroundStyle(Color.labelTertiary)
                        }
                    }
                    LabeledContent("Weight") {
                        HStack {
                            TextField("kg", value: $weightKg, format: .number)
                                .multilineTextAlignment(.trailing)
                                .keyboardType(.decimalPad)
                                .focused($focusedField, equals: .weightKg)
                            Text("kg").foregroundStyle(Color.labelTertiary)
                        }
                    }
                    if let b = bmi {
                        LabeledContent("BMI") {
                            HStack(spacing: 6) {
                                Text(String(format: "%.1f", b))
                                    .fontWeight(.semibold)
                                    .foregroundStyle(Color.labelPrimary)
                                Text("· \(bmiCategory)")
                                    .foregroundStyle(Color.labelSecondary)
                                    .font(.caption)
                            }
                        }
                    }
                }

                // MARK: Health history
                Section("Health history") {
                    Toggle("Current smoker",                 isOn: $smoking)
                    Toggle("Type 2 diabetes",                isOn: $diabetes)
                    Toggle("Family history of heart disease", isOn: $familyHistoryCvd)
                    Toggle("On blood pressure medication",   isOn: $onBpMedication)
                }
                .tint(Color.brandPrimary)

                // MARK: Clinical values
                Section {
                    OptionalIntRow(label: "Systolic BP",       unit: "mmHg",  value: $systolicBp,        focus: $focusedField, field: .systolicBp)
                    OptionalIntRow(label: "Total cholesterol", unit: "mg/dL", value: $totalCholesterol,  focus: $focusedField, field: .totalCholesterol)
                    OptionalIntRow(label: "HDL cholesterol",   unit: "mg/dL", value: $hdlCholesterol,    focus: $focusedField, field: .hdlCholesterol)
                } header: {
                    Text("Clinical values (optional)")
                } footer: {
                    Text("Leave at 0 if unknown. Used for cardiovascular risk equations.")
                        .font(.caption)
                        .foregroundStyle(Color.labelTertiary)
                }

                #if DEBUG
                Section("Developer") {
                    Button("Reset onboarding", role: .destructive) {
                        onboardingComplete = false
                    }
                }
                #endif
            }
            .navigationTitle("Profile")
            .tint(Color.almondCocoa)
            .scrollDismissesKeyboard(.interactively)
            .toolbar {
                if focusedField != nil {
                    ToolbarItem(placement: .topBarTrailing) {
                        Button("Done") {
                            UIApplication.shared.sendAction(
                                #selector(UIResponder.resignFirstResponder),
                                to: nil, from: nil, for: nil
                            )
                            focusedField = nil
                        }
                    }
                }
            }
        }
    }
}

// MARK: - Helpers

private struct OptionalIntRow: View {
    let label: String
    let unit: String
    @Binding var value: Int
    var focus: FocusState<ProfileField?>.Binding
    let field: ProfileField

    var body: some View {
        LabeledContent(label) {
            HStack {
                TextField("—", value: $value, format: .number)
                    .multilineTextAlignment(.trailing)
                    .keyboardType(.numberPad)
                    .focused(focus, equals: field)
                Text(unit).foregroundStyle(Color.labelTertiary)
            }
        }
    }
}
