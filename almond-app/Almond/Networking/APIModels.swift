import Foundation

// MARK: - Bridge API  (POST /input → poll GET /output/{input_id})

struct BridgeInputRequest: Encodable {
    let userId: String
    let onboarding: OnboardingPayload
    let samples: HealthKitSamples
    enum CodingKeys: String, CodingKey {
        case userId = "user_id"; case onboarding, samples
    }
}

struct OnboardingPayload: Encodable {
    let age: Int
    let sex: String
    let heightCm: Double
    let weightKg: Double
    let smoking: Bool
    let diabetes: Bool
    let familyHistoryCvd: Bool
    let onBpMedication: Bool
    let raceEthnicity: String?
    let systolicBp: Int?
    let totalCholesterol: Int?
    let hdlCholesterol: Int?
    enum CodingKeys: String, CodingKey {
        case age, sex, smoking, diabetes
        case heightCm = "height_cm"
        case weightKg = "weight_kg"
        case familyHistoryCvd = "family_history_cvd"
        case onBpMedication = "on_bp_medication"
        case raceEthnicity = "race_ethnicity"
        case systolicBp = "systolic_bp"
        case totalCholesterol = "total_cholesterol"
        case hdlCholesterol = "hdl_cholesterol"
    }
}

/// Decodes either a plain number (42.3) or an object with a "value" key ({"value": 42.3, ...}).
struct BridgeScore: Decodable {
    let value: Double
    init(from decoder: Decoder) throws {
        if let single = try? decoder.singleValueContainer(),
           let v = try? single.decode(Double.self) {
            value = v
        } else {
            let c = try decoder.container(keyedBy: CodingKeys.self)
            value = try c.decode(Double.self, forKey: .value)
        }
    }
    private enum CodingKeys: String, CodingKey { case value }
}

struct BridgeScores: Decodable {
    let vitalityScore: BridgeScore?
    let nhanesMortality2yr: BridgeScore?
    enum CodingKeys: String, CodingKey {
        case vitalityScore = "vitality_score"
        case nhanesMortality2yr = "nhanes_mortality_2yr"
    }
}

struct BridgeOutput: Decodable {
    let scores: BridgeScores
    let gemmaSummary: String?
    let disclaimer: String?
    enum CodingKeys: String, CodingKey {
        case scores
        case gemmaSummary = "gemma_summary"
        case disclaimer
    }
}

// MARK: - HealthKit samples (sent as `samples` inside BridgeInputRequest)

struct HealthKitUploadRequest: Encodable {
    let uploadedAt: String
    let windowStart: String
    let windowEnd: String
    let samples: HealthKitSamples
    enum CodingKeys: String, CodingKey {
        case uploadedAt = "uploaded_at"; case windowStart = "window_start"
        case windowEnd = "window_end"; case samples
    }
}

struct TopDriver: Decodable, Identifiable {
    var id: String { feature }
    let feature: String
    let humanLabel: String
    let contributionPts: Double
    let direction: String
    enum CodingKeys: String, CodingKey {
        case feature; case humanLabel = "human_label"
        case contributionPts = "contribution_pts"; case direction
    }
}

struct BridgeOutput: Decodable {
    let scores: BridgeScores
    let topDrivers: [TopDriver]
    let gemmaSummary: String?
    let disclaimer: String?
    enum CodingKeys: String, CodingKey {
        case scores; case topDrivers = "top_drivers"
        case gemmaSummary = "gemma_summary"; case disclaimer
    }
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        scores = try c.decode(BridgeScores.self, forKey: .scores)
        topDrivers = (try? c.decode([TopDriver].self, forKey: .topDrivers)) ?? []
        gemmaSummary = try? c.decode(String.self, forKey: .gemmaSummary)
        disclaimer = try? c.decode(String.self, forKey: .disclaimer)
    }
}

// MARK: - HealthKit samples (sent as `samples` inside BridgeInputRequest)

struct HealthKitSamples: Encodable {
    let stepsDaily: [StepsSample]
    let activeEnergyDailyKcal: [EnergySample]
    let exerciseMinutesDaily: [ExerciseSample]
    let sleepSessions: [SleepSession]
    let restingHrDaily: [RestingHRSample]
    let hrvSdnn: [HRVSample]
    let vo2MaxLatest: VO2MaxSample?
    let walkingHrAvgDaily: [WalkingHRSample]
    let afibDetected: Bool
    let afibEpisodes: [String]
    enum CodingKeys: String, CodingKey {
        case restingHrDaily = "resting_hr_daily"; case hrvSdnn = "hrv_sdnn"
        case vo2MaxLatest = "vo2_max_latest"; case stepsDaily = "steps_daily"
        case exerciseMinutesDaily = "exercise_minutes_daily"
        case activeEnergyDailyKcal = "active_energy_daily_kcal"
        case sleepSessions = "sleep_sessions"; case wristTempNightly = "wrist_temp_nightly"
        case walkingHrAvgDaily = "walking_hr_avg_daily"
        case afibDetected = "afib_detected"; case afibEpisodes = "afib_episodes"
    }
}

struct RestingHRSample: Encodable { let date: String; let bpm: Int }
struct HRVSample: Encodable { let timestamp: String; let ms: Double }
struct VO2MaxSample: Encodable {
    let value: Double; let measuredAt: String
    enum CodingKeys: String, CodingKey { case value; case measuredAt = "measured_at" }
}
struct StepsSample: Encodable { let date: String; let count: Int }
struct ExerciseSample: Encodable { let date: String; let minutes: Int }
struct EnergySample: Encodable { let date: String; let kcal: Int }
struct SleepSession: Encodable {
    let start: String; let end: String; let durationMin: Int
    let efficiency: Double; let stages: SleepStages
    enum CodingKeys: String, CodingKey {
        case start, end, efficiency, stages; case durationMin = "duration_min"
    }
}
struct SleepStages: Encodable {
    let deepMin: Int; let remMin: Int; let coreMin: Int; let awakeMin: Int
    enum CodingKeys: String, CodingKey {
        case deepMin = "deep_min"; case remMin = "rem_min"
        case coreMin = "core_min"; case awakeMin = "awake_min"
    }
}
struct WristTempSample: Encodable {
    let date: String; let deltaC: Double
    enum CodingKeys: String, CodingKey { case date; case deltaC = "delta_c" }
}
struct WalkingHRSample: Encodable { let date: String; let bpm: Int }

// MARK: - Errors

struct APIErrorEnvelope: Decodable { let error: APIErrorDetail }
struct APIErrorDetail: Decodable { let code: String; let message: String }

enum AlmondError: LocalizedError {
    case api(code: String, message: String)
    case healthKitUnavailable
    case pollTimeout

    var errorDescription: String? {
        switch self {
        case .api(_, let message): return message
        case .healthKitUnavailable: return "HealthKit is not available on this device."
        case .pollTimeout: return "Still processing after 2 min — try again shortly."
        }
    }
}
