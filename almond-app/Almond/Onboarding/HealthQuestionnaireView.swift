import SwiftUI

struct HealthQuestionnaireView: View {
    let onComplete: () -> Void
    @StateObject private var vm = OnboardingViewModel()

    var body: some View {
        NavigationStack {
            Form {
                Section("About you") {
                    LabeledContent("Name") {
                        TextField("Your name", text: $vm.name)
                            .multilineTextAlignment(.trailing)
                    }
                    Stepper("Age: \(vm.age)", value: $vm.age, in: 18...100)
                    Picker("Sex", selection: $vm.sex) {
                        Text("Male").tag("M")
                        Text("Female").tag("F")
                    }
                }

                Section("Body measurements") {
                    LabeledContent("Height (cm)") {
                        TextField("e.g. 178", value: $vm.heightCm, format: .number)
                            .multilineTextAlignment(.trailing)
                            .keyboardType(.decimalPad)
                    }
                    LabeledContent("Weight (kg)") {
                        TextField("e.g. 75.5", value: $vm.weightKg, format: .number)
                            .multilineTextAlignment(.trailing)
                            .keyboardType(.decimalPad)
                    }
                }

                Section("Health history") {
                    Toggle("Current smoker",                  isOn: $vm.smoking)
                    Toggle("Type 2 diabetes",                 isOn: $vm.diabetes)
                    Toggle("Family history of heart disease",  isOn: $vm.familyHistoryCvd)
                    Toggle("On blood pressure medication",    isOn: $vm.onBpMedication)
                }
                .tint(Color.almondCocoa)

                Section {
                    Picker("Race / ethnicity (optional)", selection: $vm.raceEthnicity) {
                        Text("Prefer not to say").tag(String?.none)
                        Text("White").tag(String?.some("white"))
                        Text("Black").tag(String?.some("black"))
                        Text("Asian").tag(String?.some("asian"))
                        Text("Hispanic").tag(String?.some("hispanic"))
                        Text("Other").tag(String?.some("other"))
                    }
                }

                Section("Optional clinical values") {
                    LabeledContent("Systolic BP (mmHg)") {
                        TextField("Optional", value: $vm.systolicBp, format: .number)
                            .multilineTextAlignment(.trailing)
                            .keyboardType(.numberPad)
                    }
                    LabeledContent("Total cholesterol (mg/dL)") {
                        TextField("Optional", value: $vm.totalCholesterol, format: .number)
                            .multilineTextAlignment(.trailing)
                            .keyboardType(.numberPad)
                    }
                    LabeledContent("HDL cholesterol (mg/dL)") {
                        TextField("Optional", value: $vm.hdlCholesterol, format: .number)
                            .multilineTextAlignment(.trailing)
                            .keyboardType(.numberPad)
                    }
                }

                Section {
                    Button(action: submit) {
                        Text("Get my health scores")
                            .frame(maxWidth: .infinity)
                            .fontWeight(.semibold)
                            .foregroundStyle(Color.almondCreamBase)
                    }
                    .disabled(!vm.isValid)
                    .listRowBackground(vm.isValid ? Color.almondCocoa : Color.almondCocoa.opacity(0.4))
                }
            }
            .navigationTitle("Quick health check")
            .navigationBarTitleDisplayMode(.large)
            .tint(Color.almondCocoa)
            .scrollDismissesKeyboard(.interactively)
        }
    }

    private func submit() {
        vm.save()
        onComplete()
    }
}
