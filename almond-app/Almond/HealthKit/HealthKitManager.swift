import Foundation
import HealthKit

// MARK: - Display snapshot (no backend needed)

struct HealthSnapshot {
    struct DatedValue: Identifiable {
        let id = UUID()
        let date: Date
        let value: Double
    }

    struct SleepSummary: Identifiable {
        let id = UUID()
        let date: Date
        let durationHours: Double
        let efficiency: Double
        let deepMin: Int
        let remMin: Int
        let coreMin: Int
        let awakeMin: Int
    }

    var restingHR: [DatedValue] = []
    var hrv: [DatedValue] = []
    var vo2Max: (value: Double, date: Date)? = nil
    var stepsDaily: [DatedValue] = []
    var activeEnergy: [DatedValue] = []
    var exerciseMinutes: [DatedValue] = []
    var walkingHR: [DatedValue] = []
    var wristTemp: [DatedValue] = []
    var sleepSessions: [SleepSummary] = []

    // Convenience stats
    var latestRestingHR: Double? { restingHR.last?.value }

    func weekAvg(_ series: [DatedValue]) -> Double? {
        let cutoff = Date().addingTimeInterval(-7 * 86400)
        let recent = series.filter { $0.date >= cutoff }
        guard !recent.isEmpty else { return nil }
        return recent.map(\.value).reduce(0, +) / Double(recent.count)
    }
}

// MARK: - Manager

final class HealthKitManager {
    private let store = HKHealthStore()

    private static let readTypes: Set<HKObjectType> = {
        var types: Set<HKObjectType> = [
            HKQuantityType(.restingHeartRate),
            HKQuantityType(.heartRateVariabilitySDNN),
            HKQuantityType(.vo2Max),
            HKQuantityType(.stepCount),
            HKQuantityType(.appleExerciseTime),
            HKQuantityType(.activeEnergyBurned),
            HKQuantityType(.walkingHeartRateAverage),
            HKCategoryType(.sleepAnalysis),
        ]
        if #available(iOS 17.0, *) {
            types.insert(HKQuantityType(.appleSleepingWristTemperature))
            types.insert(HKQuantityType(.atrialFibrillationBurden))
        }
        return types
    }()

    func requestAuthorization() async throws {
        guard HKHealthStore.isHealthDataAvailable() else {
            throw AlmondError.healthKitUnavailable
        }
        try await store.requestAuthorization(toShare: [], read: Self.readTypes)
    }

    // MARK: - Display snapshot

    func querySnapshot(days: Int = 30) async throws -> HealthSnapshot {
        try await requestAuthorization()

        let now = Date()
        let start = Calendar.current.date(byAdding: .day, value: -days, to: now)!

        async let rhr    = queryDailyQuantity(type: .restingHeartRate,       unit: .count().unitDivided(by: .minute()),   start: start, end: now)
        async let hrv    = queryTimestampedQuantity(type: .heartRateVariabilitySDNN, unit: .secondUnit(with: .milli),     start: start, end: now)
        async let vo2    = queryMostRecentQuantity(type: .vo2Max,            unit: HKUnit(from: "ml/kg·min"),             start: start, end: now)
        async let steps  = queryDailyQuantity(type: .stepCount,              unit: .count(),                              start: start, end: now)
        async let energy = queryDailyQuantity(type: .activeEnergyBurned,     unit: .kilocalorie(),                        start: start, end: now)
        async let exer   = queryDailyQuantity(type: .appleExerciseTime,      unit: .minute(),                             start: start, end: now)
        async let whr    = queryDailyQuantity(type: .walkingHeartRateAverage, unit: .count().unitDivided(by: .minute()),  start: start, end: now)
        async let temp   = queryWristTemp(start: start, end: now)
        async let sleep  = querySleepSummaries(start: start, end: now)

        let (rhrR, hrvR, vo2R, stepsR, energyR, exerR, whrR, tempR, sleepR) =
            await (rhr, hrv, vo2, steps, energy, exer, whr, temp, sleep)

        var snap = HealthSnapshot()
        snap.restingHR      = rhrR.map    { .init(date: $0.date, value: $0.value) }
        snap.hrv            = hrvR.map    { .init(date: $0.date, value: $0.value) }
        snap.vo2Max         = vo2R.map    { ($0.value, $0.date) }
        snap.stepsDaily     = stepsR.map  { .init(date: $0.date, value: $0.value) }
        snap.activeEnergy   = energyR.map { .init(date: $0.date, value: $0.value) }
        snap.exerciseMinutes = exerR.map  { .init(date: $0.date, value: $0.value) }
        snap.walkingHR      = whrR.map    { .init(date: $0.date, value: $0.value) }
        snap.wristTemp      = tempR.map   { .init(date: $0.date, value: $0.value) }
        snap.sleepSessions  = sleepR
        return snap
    }

    // MARK: - API upload payload (backend path, kept for future use)

    func buildUploadPayload() async throws -> HealthKitUploadRequest {
        try await requestAuthorization()

        let now = Date()
        let windowStart = Calendar.current.date(byAdding: .day, value: -90, to: now)!
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime]

        async let restingHR = queryDailyQuantity(type: .restingHeartRate, unit: .count().unitDivided(by: .minute()), start: windowStart, end: now)
        async let hrv = queryTimestampedQuantity(type: .heartRateVariabilitySDNN, unit: .secondUnit(with: .milli), start: windowStart, end: now)
        async let vo2 = queryMostRecentQuantity(type: .vo2Max, unit: HKUnit(from: "ml/kg·min"), start: windowStart, end: now)
        async let steps = queryDailyQuantity(type: .stepCount, unit: .count(), start: windowStart, end: now)
        async let exercise = queryDailyQuantity(type: .appleExerciseTime, unit: .minute(), start: windowStart, end: now)
        async let energy = queryDailyQuantity(type: .activeEnergyBurned, unit: .kilocalorie(), start: windowStart, end: now)
        async let walkingHR = queryDailyQuantity(type: .walkingHeartRateAverage, unit: .count().unitDivided(by: .minute()), start: windowStart, end: now)
        async let sleep = querySleepSessions(start: windowStart, end: now)
        async let wristTemp = queryWristTemp(start: windowStart, end: now)
        async let afib = queryAfibDetected(start: windowStart, end: now)

        let (rhr, hrvSamples, vo2Result, stepSamples, exerciseSamples,
             energySamples, whrSamples, sleepResult, tempResult, afibResult)
            = try await (restingHR, hrv, vo2, steps, exercise, energy,
                         walkingHR, sleep, wristTemp, afib)

        let dayFmt = DateFormatter()
        dayFmt.dateFormat = "yyyy-MM-dd"
        dayFmt.timeZone = TimeZone(identifier: "UTC")!

        let samples = HealthKitSamples(
            restingHrDaily: rhr.map { RestingHRSample(date: dayFmt.string(from: $0.date), bpm: Int($0.value.rounded())) },
            hrvSdnn: hrvSamples.map { HRVSample(timestamp: formatter.string(from: $0.date), ms: $0.value) },
            vo2MaxLatest: vo2Result.map { VO2MaxSample(value: $0.value, measuredAt: formatter.string(from: $0.date)) },
            stepsDaily: stepSamples.map { StepsSample(date: dayFmt.string(from: $0.date), count: Int($0.value.rounded())) },
            exerciseMinutesDaily: exerciseSamples.map { ExerciseSample(date: dayFmt.string(from: $0.date), minutes: Int($0.value.rounded())) },
            activeEnergyDailyKcal: energySamples.map { EnergySample(date: dayFmt.string(from: $0.date), kcal: Int($0.value.rounded())) },
            sleepSessions: sleepResult,
            wristTempNightly: tempResult.map { WristTempSample(date: dayFmt.string(from: $0.date), deltaC: $0.value) },
            walkingHrAvgDaily: whrSamples.map { WalkingHRSample(date: dayFmt.string(from: $0.date), bpm: Int($0.value.rounded())) },
            afibDetected: afibResult,
            afibEpisodes: []
        )

        return HealthKitUploadRequest(
            uploadedAt: formatter.string(from: now),
            windowStart: formatter.string(from: windowStart),
            windowEnd: formatter.string(from: now),
            samples: samples
        )
    }

    // MARK: - Private query helpers

    private struct DatedValue {
        let date: Date
        let value: Double
    }

    private func queryDailyQuantity(
        type identifier: HKQuantityTypeIdentifier,
        unit: HKUnit,
        start: Date, end: Date
    ) async -> [DatedValue] {
        let quantityType = HKQuantityType(identifier)
        let predicate = HKQuery.predicateForSamples(withStart: start, end: end)
        let interval = DateComponents(day: 1)
        var calendar = Calendar.current
        calendar.timeZone = TimeZone(identifier: "UTC")!
        let anchor = calendar.startOfDay(for: start)

        return await withCheckedContinuation { continuation in
            let query = HKStatisticsCollectionQuery(
                quantityType: quantityType,
                quantitySamplePredicate: predicate,
                options: .discreteAverage,
                anchorDate: anchor,
                intervalComponents: interval
            )
            query.initialResultsHandler = { _, results, _ in
                guard let results else { continuation.resume(returning: []); return }
                var out: [DatedValue] = []
                results.enumerateStatistics(from: start, to: end) { stat, _ in
                    if let q = stat.averageQuantity() {
                        out.append(DatedValue(date: stat.startDate, value: q.doubleValue(for: unit)))
                    }
                }
                continuation.resume(returning: out)
            }
            store.execute(query)
        }
    }

    private func queryTimestampedQuantity(
        type identifier: HKQuantityTypeIdentifier,
        unit: HKUnit,
        start: Date, end: Date
    ) async -> [DatedValue] {
        let quantityType = HKQuantityType(identifier)
        let predicate = HKQuery.predicateForSamples(withStart: start, end: end)
        let sort = NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: true)

        return await withCheckedContinuation { continuation in
            let query = HKSampleQuery(sampleType: quantityType, predicate: predicate,
                                      limit: HKObjectQueryNoLimit, sortDescriptors: [sort]) { _, samples, _ in
                let out = (samples as? [HKQuantitySample] ?? []).map {
                    DatedValue(date: $0.startDate, value: $0.quantity.doubleValue(for: unit))
                }
                continuation.resume(returning: out)
            }
            store.execute(query)
        }
    }

    private func queryMostRecentQuantity(
        type identifier: HKQuantityTypeIdentifier,
        unit: HKUnit,
        start: Date, end: Date
    ) async -> DatedValue? {
        let quantityType = HKQuantityType(identifier)
        let predicate = HKQuery.predicateForSamples(withStart: start, end: end)
        let sort = NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: false)

        return await withCheckedContinuation { continuation in
            let query = HKSampleQuery(sampleType: quantityType, predicate: predicate,
                                      limit: 1, sortDescriptors: [sort]) { _, samples, _ in
                guard let sample = (samples as? [HKQuantitySample])?.first else {
                    continuation.resume(returning: nil); return
                }
                continuation.resume(returning: DatedValue(
                    date: sample.startDate,
                    value: sample.quantity.doubleValue(for: unit)
                ))
            }
            store.execute(query)
        }
    }

    private func queryWristTemp(start: Date, end: Date) async -> [DatedValue] {
        guard #available(iOS 17.0, *) else { return [] }
        return await queryTimestampedQuantity(type: .appleSleepingWristTemperature,
                                              unit: .degreeCelsius(), start: start, end: end)
    }

    private func queryAfibDetected(start: Date, end: Date) async -> Bool {
        guard #available(iOS 17.0, *) else { return false }
        let samples = await queryTimestampedQuantity(type: .atrialFibrillationBurden,
                                                     unit: .percent(), start: start, end: end)
        return samples.contains { $0.value > 0 }
    }

    // MARK: - Sleep (API format)

    private func querySleepSessions(start: Date, end: Date) async -> [SleepSession] {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime]
        let samples = await fetchSleepSamples(start: start, end: end)
        return buildSleepBuckets(from: samples).compactMap { makeSleepSession(from: $0, formatter: formatter) }
    }

    private func makeSleepSession(from samples: [HKCategorySample], formatter: ISO8601DateFormatter) -> SleepSession? {
        guard let first = samples.first, let last = samples.last else { return nil }
        var deepMin = 0, remMin = 0, coreMin = 0, awakeMin = 0, inBedMin = 0
        for s in samples {
            let dur = Int(s.endDate.timeIntervalSince(s.startDate) / 60)
            switch HKCategoryValueSleepAnalysis(rawValue: s.value) {
            case .asleepDeep:                          deepMin += dur
            case .asleepREM:                           remMin  += dur
            case .asleepCore, .asleepUnspecified:      coreMin += dur
            case .awake:                               awakeMin += dur
            case .inBed:                               inBedMin += dur
            default: break
            }
        }
        let totalSleep = deepMin + remMin + coreMin
        let totalBed = max(inBedMin, totalSleep + awakeMin)
        let durationMin = Int(last.endDate.timeIntervalSince(first.startDate) / 60)
        let efficiency = totalBed > 0 ? Double(totalSleep) / Double(totalBed) : 0
        return SleepSession(start: formatter.string(from: first.startDate),
                            end: formatter.string(from: last.endDate),
                            durationMin: durationMin, efficiency: efficiency,
                            stages: SleepStages(deepMin: deepMin, remMin: remMin,
                                                coreMin: coreMin, awakeMin: awakeMin))
    }

    // MARK: - Sleep (display format)

    private func querySleepSummaries(start: Date, end: Date) async -> [HealthSnapshot.SleepSummary] {
        let samples = await fetchSleepSamples(start: start, end: end)
        return buildSleepBuckets(from: samples).compactMap { makeSleepSummary(from: $0) }
    }

    private func makeSleepSummary(from samples: [HKCategorySample]) -> HealthSnapshot.SleepSummary? {
        guard let first = samples.first, let last = samples.last else { return nil }
        var deepMin = 0, remMin = 0, coreMin = 0, awakeMin = 0, inBedMin = 0
        for s in samples {
            let dur = Int(s.endDate.timeIntervalSince(s.startDate) / 60)
            switch HKCategoryValueSleepAnalysis(rawValue: s.value) {
            case .asleepDeep:                          deepMin += dur
            case .asleepREM:                           remMin  += dur
            case .asleepCore, .asleepUnspecified:      coreMin += dur
            case .awake:                               awakeMin += dur
            case .inBed:                               inBedMin += dur
            default: break
            }
        }
        let totalSleep = deepMin + remMin + coreMin
        let totalBed = max(inBedMin, totalSleep + awakeMin)
        let durationHours = Double(last.endDate.timeIntervalSince(first.startDate)) / 3600
        let efficiency = totalBed > 0 ? Double(totalSleep) / Double(totalBed) : 0
        return HealthSnapshot.SleepSummary(date: first.startDate,
                                           durationHours: durationHours,
                                           efficiency: efficiency,
                                           deepMin: deepMin, remMin: remMin,
                                           coreMin: coreMin, awakeMin: awakeMin)
    }

    // MARK: - Shared sleep fetch + bucket logic

    private func fetchSleepSamples(start: Date, end: Date) async -> [HKCategorySample] {
        let sleepType = HKCategoryType(.sleepAnalysis)
        let predicate = HKQuery.predicateForSamples(withStart: start, end: end)
        let sort = NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: true)

        return await withCheckedContinuation { continuation in
            let query = HKSampleQuery(sampleType: sleepType, predicate: predicate,
                                      limit: HKObjectQueryNoLimit, sortDescriptors: [sort]) { _, samples, _ in
                continuation.resume(returning: (samples as? [HKCategorySample]) ?? [])
            }
            store.execute(query)
        }
    }

    private func buildSleepBuckets(from samples: [HKCategorySample]) -> [[HKCategorySample]] {
        guard !samples.isEmpty else { return [] }
        var buckets: [[HKCategorySample]] = [[samples[0]]]
        for sample in samples.dropFirst() {
            let gap = sample.startDate.timeIntervalSince(buckets.last!.last!.endDate)
            if gap > 4 * 3600 {
                buckets.append([sample])
            } else {
                buckets[buckets.count - 1].append(sample)
            }
        }
        return buckets
    }
}
