import { describe, expect, it } from 'vitest';

import {
  computeMomentFromHour,
  getHourInTimeZone,
  DEFAULT_TIME_ZONE
} from './ThemeProvider';

describe('computeMomentFromHour', () => {
  const cases: Array<[number, string]> = [
    [0, 'night'],
    [5.9, 'night'],
    [6, 'morning'],
    [10.99, 'morning'],
    [11, 'noon'],
    [16.99, 'noon'],
    [17, 'twilight'],
    [20.99, 'twilight'],
    [21, 'night'],
    [23.5, 'night']
  ];

  it.each(cases)('returns %s for hour=%s', (hour, expected) => {
    expect(computeMomentFromHour(hour)).toBe(expected);
  });
});

describe('getHourInTimeZone', () => {
  it('uses the provided time zone offset with minute precision', () => {
    const date = new Date('2024-05-01T15:45:30Z');
    const hour = getHourInTimeZone(date, DEFAULT_TIME_ZONE);
    expect(hour).toBeGreaterThanOrEqual(0);
    expect(hour).toBeLessThan(24);
    expect(hour).toBeCloseTo(11.7583, 4); // 15:45:30Z == 11:45:30 EDT
  });

  it('falls back to UTC hours (including minutes) when Intl is not available', () => {
    const date = new Date('2024-05-01T22:30:00Z');
    const hour = getHourInTimeZone(date, 'Invalid/Timezone');
    expect(hour).toBeCloseTo(22.5, 4); // fallback uses UTC hour + minutes
  });
});
