export interface MacroTarget {
  calories: number;
  protein: number;
  carbs: number;
  fat: number;
  fiber?: number;
}

export interface MacroActual {
  calories?: number | null;
  protein?: number | null;
  carbs?: number | null;
  fat?: number | null;
  fiber?: number | null;
}

export function macroCompliance(actual: MacroActual, target: MacroTarget) {
  return {
    calories: ratio(actual.calories, target.calories),
    protein: ratio(actual.protein, target.protein),
    carbs: ratio(actual.carbs, target.carbs),
    fat: ratio(actual.fat, target.fat),
    fiber: ratio(actual.fiber, target.fiber ?? 25)
  };
}

export function micronutrientCoverage(actual: Record<string, number | null | undefined>, target: Record<string, number>) {
  return Object.fromEntries(
    Object.entries(target).map(([key, goal]) => [key, ratio(actual[key], goal)])
  );
}

function ratio(value: number | null | undefined, goal: number | null | undefined) {
  if (!value || !goal) return 0;
  return Math.min(1.5, value / goal);
}
