import { describe, expect, it } from 'vitest';
import { formatTimeAgo, formatDate } from './dateFormat';

describe('formatTimeAgo', () => {

  it('returns empty string for null', () => {
    expect(formatTimeAgo(null)).toBe('');
  });

  it('returns "just now" for < 1 hour ago', () => {
    const thirtyMinAgo = new Date(Date.now() - 30 * 60 * 1000).toISOString();
    expect(formatTimeAgo(thirtyMinAgo)).toBe('just now');
  });

  it('returns Nh ago for N hours ago', () => {
    const threeHoursAgo = new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString();
    expect(formatTimeAgo(threeHoursAgo)).toBe('3h ago');
  });

  it('returns "yesterday" for exactly 1 day', () => {
    const yesterday = new Date(Date.now() - 25 * 60 * 60 * 1000).toISOString();
    expect(formatTimeAgo(yesterday)).toBe('yesterday');
  });

  it('returns Nd ago for multiple days', () => {
    const threeDaysAgo = new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString();
    expect(formatTimeAgo(threeDaysAgo)).toBe('3d ago');
  });
});

describe('formatDate', () => {
  it('returns a non-empty string for today', () => {
    const result = formatDate();
    expect(result.length).toBeGreaterThan(0);
  });

  it('formats the given date', () => {
    const date = new Date(2026, 0, 15); // Jan 15 2026
    const result = formatDate(date);
    expect(result).toContain('15');
    expect(result).toContain('January');
  });
});
