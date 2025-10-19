export function exponentialMovingAverage(values: Array<number | null | undefined>, span = 7) {
  if (!Array.isArray(values) || !values.length) return [];
  const alpha = 2 / (span + 1);
  const ema: number[] = [];

  for (let index = 0; index < values.length; index += 1) {
    const raw = values[index];
    const value = Number.isFinite(raw) ? Number(raw) : null;

    if (value === null) {
      ema.push(index === 0 ? 0 : ema[index - 1]);
      continue;
    }

    if (index === 0) {
      ema.push(value);
    } else {
      const previous = ema[index - 1];
      ema.push(alpha * value + (1 - alpha) * previous);
    }
  }

  return ema;
}

export function rollingDelta(values: Array<number | null | undefined>, window = 7) {
  if (!Array.isArray(values) || !values.length) return [];
  const deltas: Array<number | null> = [];
  for (let index = 0; index < values.length; index += 1) {
    const current = Number.isFinite(values[index]) ? Number(values[index]) : null;
    const lookbackIndex = index - window;
    if (lookbackIndex < 0 || current === null) {
      deltas.push(null);
      continue;
    }

    const prior = Number.isFinite(values[lookbackIndex]) ? Number(values[lookbackIndex]) : null;
    if (prior === null) {
      deltas.push(null);
      continue;
    }

    deltas.push(current - prior);
  }

  return deltas;
}

export interface LoadBalanceOptions {
  ctlSpan?: number;
  atlSpan?: number;
}

export function computeChronicAcuteLoad(loads: Array<number | null | undefined>, options: LoadBalanceOptions = {}) {
  const ctlSpan = options.ctlSpan ?? 42;
  const atlSpan = options.atlSpan ?? 7;

  const ctlSeries = exponentialMovingAverage(loads, ctlSpan);
  const atlSeries = exponentialMovingAverage(loads, atlSpan);
  const ctl = lastFinite(ctlSeries) ?? 0;
  const atl = lastFinite(atlSeries) ?? 0;
  const tsb = ctl - atl;

  return {
    ctl,
    atl,
    tsb,
    ctlSeries,
    atlSeries
  };
}

function lastFinite(values: number[]) {
  for (let index = values.length - 1; index >= 0; index -= 1) {
    if (Number.isFinite(values[index])) {
      return values[index];
    }
  }
  return null;
}
