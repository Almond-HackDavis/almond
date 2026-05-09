import Foundation

// MARK: - Auth

struct LoginRequest: Encodable {
    let appleIdentityToken: String

    enum CodingKeys: String, CodingKey {
        case appleIdentityToken = "apple_identity_token"
    }
}

struct LoginResponse: Decodable {
    let userId: String
    let sessionToken: String
    let isNewUser: Bool
    let needsOnboarding: Bool

    enum CodingKeys: String, CodingKey {
        case userId = "user_id"
        case sessionToken = "session_token"
        case isNewUser = "is_new_user"
        case needsOnboarding = "needs_onboarding"
    }
}

// MARK: - Onboarding

struct OnboardingRequest: Encodable {
    let age: Int
    let sex: String
    let heightCm: Double
    let weightKg: Double
    let smoking: Bool
    let diabetes: Bool
    let familyHistoryCvd: Bool
    let raceEthnicity: String?
    let systolicBp: Int?
    let totalCholesterol: Int?
    let hdlCholesterol: Int?
    let onBpMedication: Bool?

    enum CodingKeys: String, CodingKey {
        case age, sex, smoking, diabetes
        case heightCm = "height_cm"
        case weightKg = "weight_kg"
        case familyHistoryCvd = "family_history_cvd"
        case raceEthnicity = "race_ethnicity"
        case systolicBp = "systolic_bp"
        case totalCholesterol = "total_cholesterol"
        case hdlCholesterol = "hdl_cholesterol"
        case onBpMedication = "on_bp_medication"
    }
}

struct OnboardingResponse: Decodable {
    let onboardingId: String
    let completedAt: String

    enum CodingKeys: String, CodingKey {
        case onboardingId = "onboarding_id"
        case completedAt = "completed_at"
    }
}

// MARK: - HealthKit Upload

struct HealthKitUploadRequest: Encodable {
    let uploadedAt: String
    let windowStart: String
    let windowEnd: String
    let samples: HealthKitSamples

    enum CodingKeys: String, CodingKey {
        case uploadedAt = "uploaded_at"
        case windowStart = "window_start"
        case windowEnd = "window_end"
        case samples
    }
}

struct HealthKitSamples: Encodable {
    let restingHrDaily: [RestingHRSample]
    let hrvSdnn: [HRVSample]
    let vo2MaxLatest: VO2MaxSample?
    let stepsDaily: [StepsSample]
    let exerciseMinutesDaily: [ExerciseSample]
    let activeEnergyDailyKcal: [EnergySample]
    let sleepSessions: [SleepSession]
    let wristTempNightly: [WristTempSample]
    let walkingHrAvgDaily: [WalkingHRSample]
    let afibDetected: Bool
    let afibEpisodes: [String]

    enum CodingKeys: String, CodingKey {
        case restingHrDaily = "resting_hr_daily"
        case hrvSdnn = "hrv_sdnn"
        case vo2MaxLatest = "vo2_max_latest"
        case stepsDaily = "steps_daily"
        case exerciseMinutesDaily = "exercise_minutes_daily"
        case activeEnergyDailyKcal = "active_energy_daily_kcal"
        case sleepSessions = "sleep_sessions"
        case wristTempNightly = "wrist_temp_nightly"
        case walkingHrAvgDaily = "walking_hr_avg_daily"
        case afibDetected = "afib_detected"
        case afibEpisodes = "afib_episodes"
    }
}

struct RestingHRSample: Encodable {
    let date: String
    let bpm: Int
}

struct HRVSample: Encodable {
    let timestamp: String
    let ms: Double
}

struct VO2MaxSample: Encodable {
    let value: Double
    let measuredAt: String

    enum CodingKeys: String, CodingKey {
        case value
        case measuredAt = "measured_at"
    }
}

struct StepsSample: Encodable {
    let date: String
    let count: Int
}

struct ExerciseSample: Encodable {
    let date: String
    let minutes: Int
}

struct EnergySample: Encodable {
    let date: String
    let kcal: Int
}

struct SleepSession: Encodable {
    let start: String
    let end: String
    let durationMin: Int
    let efficiency: Double
    let stages: SleepStages

    enum CodingKeys: String, CodingKey {
        case start, end, efficiency, stages
        case durationMin = "duration_min"
    }
}

struct SleepStages: Encodable {
    let deepMin: Int
    let remMin: Int
    let coreMin: Int
    let awakeMin: Int

    enum CodingKeys: String, CodingKey {
        case deepMin = "deep_min"
        case remMin = "rem_min"
        case coreMin = "core_min"
        case awakeMin = "awake_min"
    }
}

struct WristTempSample: Encodable {
    let date: String
    let deltaC: Double

    enum CodingKeys: String, CodingKey {
        case date
        case deltaC = "delta_c"
    }
}

struct WalkingHRSample: Encodable {
    let date: String
    let bpm: Int
}

struct HealthKitUploadResponse: Decodable {
    let uploadId: String
    let receivedAt: String
    let processed: Bool

    enum CodingKeys: String, CodingKey {
        case uploadId = "upload_id"
        case receivedAt = "received_at"
        case processed
    }
}

// MARK: - Risk

struct RiskResponse: Decodable {
    let computedAt: String
    let scores: RiskScores
    let topDrivers: [RiskDriver]
    let geminiRecommendation: GeminiRecommendation

    enum CodingKeys: String, CodingKey {
        case computedAt = "computed_at"
        case scores
        case topDrivers = "top_drivers"
        case geminiRecommendation = "gemini_recommendation"
    }
}

struct RiskScores: Decodable {
    let ascvd10yr: RiskScoreAugmented
    let framingham10yrCvd: RiskScoreSimple
    let findrisc10yrDiabetes: RiskScoreWithMax
    let lifeEssential8: RiskScoreWithMax
    let fitnessAge: FitnessAgeScore
    let nhanesMortality10yr: NHANESScore

    enum CodingKeys: String, CodingKey {
        case ascvd10yr = "ascvd_10yr"
        case framingham10yrCvd = "framingham_10yr_cvd"
        case findrisc10yrDiabetes = "findrisc_10yr_diabetes"
        case lifeEssential8 = "life_essential_8"
        case fitnessAge = "fitness_age"
        case nhanesMortality10yr = "nhanes_mortality_10yr"
    }
}

struct RiskScoreAugmented: Decodable {
    let value: Double
    let rawValue: Double?
    let augmentedValue: Double?
    let category: String

    enum CodingKeys: String, CodingKey {
        case value, category
        case rawValue = "raw_value"
        case augmentedValue = "augmented_value"
    }
}

struct RiskScoreSimple: Decodable {
    let value: Double
    let category: String
}

struct RiskScoreWithMax: Decodable {
    let value: Double
    let max: Double
    let category: String
}

struct FitnessAgeScore: Decodable {
    let value: Int
    let chronologicalAge: Int
    let delta: Int

    enum CodingKeys: String, CodingKey {
        case value, delta
        case chronologicalAge = "chronological_age"
    }
}

struct NHANESScore: Decodable {
    let value: Double
    let ciLow: Double
    let ciHigh: Double

    enum CodingKeys: String, CodingKey {
        case value
        case ciLow = "ci_low"
        case ciHigh = "ci_high"
    }
}

struct RiskDriver: Decodable, Identifiable {
    var id: String { feature }
    let feature: String
    let value: Double
    let populationNorm: Double
    let direction: String
    let weight: Double
    let humanLabel: String

    enum CodingKeys: String, CodingKey {
        case feature, value, direction, weight
        case populationNorm = "population_norm"
        case humanLabel = "human_label"
    }
}

struct GeminiRecommendation: Decodable {
    let summary: String
    let actions: [RecommendationAction]
    let disclaimer: String
}

struct RecommendationAction: Decodable, Identifiable {
    var id: String { finding }
    let finding: String
    let action: String
    let rationale: String
}

// MARK: - History

struct HistoryResponse: Decodable {
    let userId: String
    let days: Int
    let series: HistorySeries

    enum CodingKeys: String, CodingKey {
        case userId = "user_id"
        case days, series
    }
}

struct HistorySeries: Decodable {
    let ascvd10yr: [HistoryDataPoint]
    let fitnessAge: [HistoryDataPoint]
    let restingHrDaily: [BPMHistoryPoint]
    let vo2Max: [HistoryDataPoint]
    let sleepRegularity: [HistoryDataPoint]

    enum CodingKeys: String, CodingKey {
        case ascvd10yr = "ascvd_10yr"
        case fitnessAge = "fitness_age"
        case restingHrDaily = "resting_hr_daily"
        case vo2Max = "vo2_max"
        case sleepRegularity = "sleep_regularity"
    }
}

struct HistoryDataPoint: Decodable, Identifiable {
    var id: String { date }
    let date: String
    let value: Double
}

struct BPMHistoryPoint: Decodable, Identifiable {
    var id: String { date }
    let date: String
    let bpm: Double
}

// MARK: - API Error

struct APIErrorEnvelope: Decodable {
    let error: APIErrorDetail
}

struct APIErrorDetail: Decodable {
    let code: String
    let message: String
}

// MARK: - App errors

enum AlmondError: LocalizedError {
    case api(code: String, message: String)
    case notAuthenticated
    case healthKitUnavailable

    var errorDescription: String? {
        switch self {
        case .api(_, let message): return message
        case .notAuthenticated: return "Session expired — please sign in again."
        case .healthKitUnavailable: return "HealthKit is not available on this device."
        }
    }
}
