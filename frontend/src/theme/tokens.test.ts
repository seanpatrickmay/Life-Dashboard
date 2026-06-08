import { describe, it, expect } from 'vitest';
import { lightTheme, darkTheme } from './monetTheme';
import { contrastRatio } from './contrast';

const HEX = /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/;
const themes = [lightTheme, darkTheme] as const;

describe('solid semantic tokens', () => {
  for (const t of themes) {
    const c = t.colors as Record<string, string>;
    it(`${t.mode}: surfaces are opaque hex (no translucency)`, () => {
      for (const key of ['surface', 'surfaceRaised', 'surfaceInset', 'borderStrong', 'borderSoft', 'textPrimary', 'textSecondary', 'accent', 'accentText', 'accentStrong']) {
        expect(c[key], `${key} must exist`).toBeDefined();
        expect(c[key], `${key}=${c[key]} must be opaque hex`).toMatch(HEX);
      }
    });
    it(`${t.mode}: radii.pixel is squarer than the old 22px`, () => {
      expect(parseInt(t.radii.pixel, 10)).toBeLessThanOrEqual(8);
    });
    it(`${t.mode}: shadowPixel is a hard offset (0 blur)`, () => {
      expect(t.shadows.pixel).toMatch(/\b\d+px\s+\d+px\s+0\b/);
    });
  }
});

describe('WCAG AA contrast matrix', () => {
  const pairs: Array<[string, string, number]> = [
    ['textPrimary', 'surface', 4.5],
    ['textSecondary', 'surface', 4.5],
    ['textPrimary', 'surfaceRaised', 4.5],
    ['textPrimary', 'surfaceInset', 4.5],
    ['borderStrong', 'surface', 3.0],
    ['accentText', 'accent', 4.5],
    ['accentStrong', 'surface', 3.0],
  ];
  for (const t of themes) {
    const c = t.colors as Record<string, string>;
    for (const [fg, bg, min] of pairs) {
      it(`${t.mode}: ${fg} on ${bg} >= ${min}:1`, () => {
        expect(contrastRatio(c[fg], c[bg])).toBeGreaterThanOrEqual(min);
      });
    }
  }
});
