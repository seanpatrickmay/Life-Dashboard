import { describe, expect, it } from 'vitest';

import { mifflinStJeor, totalDailyEnergyExpenditure } from '@/lib/calc/tdee';

describe('TDEE calculations', () => {
  it('computes Mifflin-St Jeor BMR for male athlete', () => {
    const bmr = mifflinStJeor({
      sex: 'male',
      weightKg: 80,
      heightCm: 180,
      ageYears: 35
    });

    expect(bmr).toBeCloseTo(1755, 3);
  });

  it('applies activity multiplier presets', () => {
    const tdee = totalDailyEnergyExpenditure({
      sex: 'female',
      weightKg: 62,
      heightCm: 168,
      ageYears: 32,
      activityLevel: 'moderately_active'
    });

    expect(tdee.bmr).toBeCloseTo(1349, 1);
    expect(tdee.multiplier).toBeCloseTo(1.55, 5);
    expect(tdee.maintenance).toBeCloseTo(tdee.bmr * 1.55, 4);
  });

  it('uses custom activity multiplier when supplied', () => {
    const tdee = totalDailyEnergyExpenditure({
      sex: 'male',
      weightKg: 70,
      heightCm: 172,
      ageYears: 40,
      activityMultiplier: 1.42
    });

    expect(tdee.multiplier).toBeCloseTo(1.42, 5);
    expect(tdee.maintenance).toBeCloseTo(tdee.bmr * 1.42, 4);
  });
});
