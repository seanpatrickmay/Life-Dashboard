export interface ReadinessInput {
  hrvRmssd: number | null;
  hrvBaseline: number | null;
  hrvStdDev?: number | null;
  restingHr: number | null;
  restingHrBaseline: number | null;
  restingHrStdDev?: number | null;
  sleepMinutes: number | null;
  sleepMinutesBaseline?: number | null;
  sleepEfficiency: number | null;
  sleepEfficiencyBaseline?: number | null;
  previousDayLoad: number | null;
  loadBaseline?: number | null;
}

interface ComponentScore {
  weight: number;
  value: number;
}

const DEFAULT_SLEEP_BASELINE = 7 * 60; // minutes
const DEFAULT_SLEEP_EFFICIENCY_BASELINE = 85;
const MIN_STDDEV = 1;

export function calculateReadinessScore(input: ReadinessInput): number {
  const components: ComponentScore[] = [
    {
      weight: 0.3,
      value: zScoreComponent(
        input.hrvRmssd,
        input.hrvBaseline,
        input.hrvStdDev,
        { higherIsBetter: true }
      )
    },
    {
      weight: 0.25,
      value: zScoreComponent(
        input.restingHr,
        input.restingHrBaseline,
        input.restingHrStdDev,
        { higherIsBetter: false }
      )
    },
    {
      weight: 0.2,
      value: ratioComponent(
        input.sleepMinutes,
        input.sleepMinutesBaseline ?? DEFAULT_SLEEP_BASELINE,
        { sensitivity: 4 }
      )
    },
    {
      weight: 0.15,
      value: ratioComponent(
        input.sleepEfficiency,
        input.sleepEfficiencyBaseline ?? DEFAULT_SLEEP_EFFICIENCY_BASELINE,
        { sensitivity: 5 }
      )
    },
    {
      weight: 0.1,
      value: loadComponent(input.previousDayLoad, input.loadBaseline)
    }
  ];

  const totalWeight = components.reduce((sum, component) => sum + component.weight, 0);
  const readinessScore =
    totalWeight > 0
      ? components.reduce((sum, component) => sum += component.weight * component.value, 0) / totalWeight
      : 0;

  return Math.round(clamp(readinessScore, 0, 1) * 100);
}

function zScoreComponent(
  value: number | null,
  baseline: number | null,
  stdDev: number | null | undefined,
  options: { higherIsBetter: boolean }
) {
  if (!Number.isFinite(value) || !Number.isFinite(baseline)) {
    return 0.5;
  }

  const sd = normalizeStdDev(stdDev, baseline);
  const z = (Number(value) - Number(baseline)) / sd;
  const score = sigmoid(options.higherIsBetter ? z : -z);
  return clamp(score, 0, 1);
}

function ratioComponent(
  value: number | null,
  baseline: number | null,
  options: { sensitivity: number }
) {
  if (!Number.isFinite(value) || !Number.isFinite(baseline) || baseline! <= 0) {
    return 0.5;
  }

  const ratio = Number(value) / Number(baseline);
  const z = (ratio - 1) * options.sensitivity;
  return clamp(sigmoid(z), 0, 1);
}

function loadComponent(previousDayLoad: number | null, loadBaseline: number | null | undefined) {
  if (!Number.isFinite(previousDayLoad)) {
    return 0.5;
  }

  if (!Number.isFinite(loadBaseline) || loadBaseline! <= 0) {
    const score = sigmoid((Number(previousDayLoad) * -1) / 75);
    return clamp(score, 0, 1);
  }

  const diff = Number(previousDayLoad) - Number(loadBaseline);
  const normalized = diff / Math.max(Number(loadBaseline) * 0.25, 5);
  const score = sigmoid(-normalized);
  return clamp(score, 0, 1);
}

function sigmoid(x: number) {
  return 1 / (1 + Math.exp(-x));
}

function normalizeStdDev(stdDev: number | null | undefined, baseline: number | null) {
  if (Number.isFinite(stdDev) && stdDev! > 0) {
    return stdDev!;
  }

  if (Number.isFinite(baseline)) {
    return Math.max(Math.abs(Number(baseline)) * 0.1, MIN_STDDEV);
  }

  return MIN_STDDEV;
}

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}
