import SwiftUI

struct OnboardingView: View {
    @EnvironmentObject var authManager: AuthManager
    @StateObject private var vm = OnboardingViewModel()

    var body: some View {
        NavigationStack {
            Form {
                Section("About you") {
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
                    Toggle("Current smoker", isOn: $vm.smoking)
                    Toggle("Type 2 diabetes", isOn: $vm.diabetes)
                    Toggle("Family history of heart disease", isOn: $vm.familyHistoryCvd)
                    Toggle("On blood pressure medication", isOn: $vm.onBpMedication)
                }

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

                if let error = vm.errorMessage {
                    Section {
                        Text(error)
                            .foregroundStyle(.red)
                            .font(.caption)
                    }
                }

                Section {
                    Button(action: submit) {
                        if vm.isSubmitting {
                            ProgressView()
                                .frame(maxWidth: .infinity)
                        } else {
                            Text("Get my health scores")
                                .frame(maxWidth: .infinity)
                                .fontWeight(.semibold)
                        }
                    }
                    .disabled(!vm.isValid || vm.isSubmitting)
                }
            }
            .navigationTitle("Quick health check")
            .navigationBarTitleDisplayMode(.large)
        }
    }

    private func submit() {
        Task {
            guard (try? await vm.submit()) != nil else { return }
            authManager.markOnboardingComplete()
        }
    }
}
