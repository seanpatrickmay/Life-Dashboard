import { describe, expect, it } from 'vitest';

import { calculateReadinessScore } from '@/lib/calc/readiness';

const WELL_RESTED = {
  hrvRmssd: 92,
  hrvBaseline: 75,
  hrvStdDev: 6,
  restingHr: 50,
  restingHrBaseline: 58,
  restingHrStdDev: 3,
  sleepMinutes: 470,
  sleepMinutesBaseline: 430,
  sleepEfficiency: 93,
  sleepEfficiencyBaseline: 88,
  previousDayLoad: 65,
  loadBaseline: 80
} as const;

const FATIGUED = {
  hrvRmssd: 60,
  hrvBaseline: 75,
  hrvStdDev: 6,
  restingHr: 66,
  restingHrBaseline: 58,
  restingHrStdDev: 3,
  sleepMinutes: 300,
  sleepMinutesBaseline: 430,
  sleepEfficiency: 74,
  sleepEfficiencyBaseline: 88,
  previousDayLoad: 120,
  loadBaseline: 80
} as const;

describe('Readiness scoring', () => {
  it('elevates score when recovery markers are strong', () => {
    const score = calculateReadinessScore({ ...WELL_RESTED });
    expect(score).toBeGreaterThan(75);
    expect(score).toBeLessThanOrEqual(100);
  });

  it('reduces score when fatigue markers dominate', () => {
    const score = calculateReadinessScore({ ...FATIGUED });
    expect(score).toBeGreaterThanOrEqual(0);
    expect(score).toBeLessThan(35);
  });

  it('handles partial data gracefully', () => {
    const score = calculateReadinessScore({
      hrvRmssd: null,
      hrvBaseline: null,
      restingHr: 55,
      restingHrBaseline: 56,
      sleepMinutes: null,
      sleepEfficiency: 90,
      previousDayLoad: null
    });

    expect(score).toBeGreaterThan(30);
    expect(score).toBeLessThan(70);
  });
});
