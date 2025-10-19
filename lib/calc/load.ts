export interface TrimpSummaryInput {
  durationMinutes: number;
  avgHr: number;
  restingHr: number;
  maxHr: number;
  genderCoefficient?: number;
}

export interface TrimpStreamInput {
  samples: Array<number | HrSample>;
  samplingIntervalSeconds?: number;
  restingHr: number;
  maxHr: number;
  genderCoefficient?: number;
}

export interface HrSample {
  hr: number;
  timestamp?: string;
}

export interface SessionLoadInput {
  /** Already-computed Training Stress Score, wins if provided. */
  trainingStressScore?: number | null;
  /** Summary metrics to estimate TRIMP when HR stream is unavailable. */
  summary?: TrimpSummaryInput | null;
  /** Heart rate stream for higher fidelity TRIMP estimation. */
  stream?: TrimpStreamInput | null;
}

export interface SessionLoadResult {
  load: number;
  source: 'tss' | 'trimp_stream' | 'trimp_summary' | 'unknown';
}

const DEFAULT_GENDER_COEFFICIENT = 1.92;

export function calculateTrimpFromSummary(input: TrimpSummaryInput): number {
  const { durationMinutes, avgHr, restingHr, maxHr } = input;
  if (!Number.isFinite(durationMinutes) || durationMinutes <= 0) return 0;

  const hrReserve = maxHr - restingHr;
  if (!Number.isFinite(hrReserve) || hrReserve <= 0) return 0;

  const intensity = (avgHr - restingHr) / hrReserve;
  if (!Number.isFinite(intensity) || intensity <= 0) return 0;

  const coefficient = input.genderCoefficient ?? DEFAULT_GENDER_COEFFICIENT;
  return durationMinutes * intensity * 0.64 * Math.exp(coefficient * intensity);
}

export function calculateTrimpFromStream(input: TrimpStreamInput): number {
  const { samples, samplingIntervalSeconds = 5, restingHr, maxHr } = input;
  if (!Array.isArray(samples) || !samples.length) return 0;

  const intervalMinutes = samplingIntervalSeconds / 60;
  if (!Number.isFinite(intervalMinutes) || intervalMinutes <= 0) return 0;

  const coefficient = input.genderCoefficient ?? DEFAULT_GENDER_COEFFICIENT;
  const hrReserve = maxHr - restingHr;
  if (!Number.isFinite(hrReserve) || hrReserve <= 0) return 0;

  let load = 0;

  for (const sample of samples) {
    const hr = typeof sample === 'number' ? sample : sample?.hr;
    if (!Number.isFinite(hr)) continue;
    const intensity = (Number(hr) - restingHr) / hrReserve;
    if (intensity <= 0) continue;
    load += intervalMinutes * intensity * 0.64 * Math.exp(coefficient * intensity);
  }

  return load;
}

export function calculateSessionLoad(input: SessionLoadInput): SessionLoadResult {
  const tss = input.trainingStressScore;
  if (Number.isFinite(tss) && (tss ?? 0) > 0) {
    return { load: Number(tss), source: 'tss' };
  }

  if (input.stream) {
    const trimp = calculateTrimpFromStream(input.stream);
    if (trimp > 0) {
      return { load: trimp, source: 'trimp_stream' };
    }
  }

  if (input.summary) {
    const trimp = calculateTrimpFromSummary(input.summary);
    if (trimp > 0) {
      return { load: trimp, source: 'trimp_summary' };
    }
  }

  return { load: 0, source: 'unknown' };
}
