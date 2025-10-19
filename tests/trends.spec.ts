import { describe, expect, it } from 'vitest';

import { computeChronicAcuteLoad, exponentialMovingAverage, rollingDelta } from '@/lib/calc/trends';

describe('Trend utilities', () => {
  it('computes exponential moving average', () => {
    const ema = exponentialMovingAverage([1, 2, 3, 4, 5], 3);
    expect(ema).toEqual([
      1,
      1.5,
      2.25,
      3.125,
      4.0625
    ]);
  });

  it('derives rolling delta over window', () => {
    const delta = rollingDelta([2, 4, 6, 9, 11], 2);
    expect(delta).toEqual([null, null, 4, 5, 5]);
  });

  it('computes simplified CTL/ATL/TSB', () => {
    const { ctl, atl, tsb } = computeChronicAcuteLoad([50, 60, 65, 70, 68, 72, 75, 74, 76]);
    expect(ctl).toBeGreaterThan(50);
    expect(atl).toBeGreaterThan(ctl - 15);
    expect(tsb).toBeCloseTo(ctl - atl, 6);
  });
});
