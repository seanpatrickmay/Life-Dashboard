/** Shared colour helpers. */

/**
 * Convert a 6-digit hex colour to an rgba() string with the given alpha (0–1).
 * e.g. hexToRgba('#FFC075', 0.15) → 'rgba(255,192,117,0.15)'
 */
export function hexToRgba(hex: string, alpha: number): string {
  const clean = hex.replace('#', '');
  const r = parseInt(clean.slice(0, 2), 16);
  const g = parseInt(clean.slice(2, 4), 16);
  const b = parseInt(clean.slice(4, 6), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}
