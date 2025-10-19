import { describe, expect, it } from 'vitest';

import {
  calculateSessionLoad,
  calculateTrimpFromStream,
  calculateTrimpFromSummary
} from '@/lib/calc/load';

describe('Training load calculations', () => {
  it('prefers provided TSS when available', () => {
    const result = calculateSessionLoad({
      trainingStressScore: 95
    });

    expect(result).toEqual({ load: 95, source: 'tss' });
  });

  it('computes TRIMP from summary data', () => {
    const trimp = calculateTrimpFromSummary({
      durationMinutes: 60,
      avgHr: 150,
      restingHr: 50,
      maxHr: 190
    });

    const expected = 60 * ((150 - 50) / (190 - 50)) * 0.64 * Math.exp(1.92 * ((150 - 50) / (190 - 50)));
    expect(trimp).toBeCloseTo(expected, 6);
  });

  it('aggregates TRIMP from HR stream when summary unavailable', () => {
    const trimp = calculateTrimpFromStream({
      samples: [120, 140, 155, 165],
      samplingIntervalSeconds: 60,
      restingHr: 50,
      maxHr: 190
    });

    const expected = [120, 140, 155, 165]
      .map((hr) => {
        const reserve = (hr - 50) / (190 - 50);
        return 1 * reserve * 0.64 * Math.exp(1.92 * reserve);
      })
      .reduce((sum, value) => sum + value, 0);

    expect(trimp).toBeCloseTo(expected, 6);
  });

  it('falls back to TRIMP when TSS not provided', () => {
    const result = calculateSessionLoad({
      summary: {
        durationMinutes: 45,
        avgHr: 142,
        restingHr: 48,
        maxHr: 185
      }
    });

    expect(result.source).toBe('trimp_summary');
    expect(result.load).toBeGreaterThan(0);
  });
});
