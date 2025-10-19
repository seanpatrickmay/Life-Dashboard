export type Sex = 'male' | 'female' | 'other';
export type ActivityLevel = 'sedentary' | 'lightly_active' | 'moderately_active' | 'very_active' | 'athlete';

export interface TdeeInput {
  sex: Sex;
  weightKg: number;
  heightCm: number;
  ageYears: number;
  activityLevel?: ActivityLevel;
  activityMultiplier?: number;
}

const ACTIVITY_DEFAULTS: Record<ActivityLevel, number> = {
  sedentary: 1.2,
  lightly_active: 1.375,
  moderately_active: 1.55,
  very_active: 1.725,
  athlete: 1.9
};

export function mifflinStJeor({ sex, weightKg, heightCm, ageYears }: TdeeInput): number {
  const s = sex === 'male' ? 5 : -161;
  return 10 * weightKg + 6.25 * heightCm - 5 * ageYears + s;
}

export function resolveActivityMultiplier({
  activityLevel,
  activityMultiplier
}: Pick<TdeeInput, 'activityLevel' | 'activityMultiplier'>) {
  if (activityMultiplier && activityMultiplier > 0) {
    return activityMultiplier;
  }
  if (activityLevel) {
    return ACTIVITY_DEFAULTS[activityLevel];
  }
  return ACTIVITY_DEFAULTS.sedentary;
}

export function totalDailyEnergyExpenditure(input: TdeeInput) {
  const bmr = mifflinStJeor(input);
  const multiplier = resolveActivityMultiplier(input);
  const maintenance = bmr * multiplier;
  return {
    bmr,
    multiplier,
    maintenance,
    deficit10: maintenance * 0.9,
    surplus10: maintenance * 1.1
  };
}
