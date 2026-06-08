import { describe, it, expect } from 'vitest';
import { contrastRatio, relativeLuminance } from './contrast';

describe('contrastRatio', () => {
  it('black on white is 21:1', () => {
    expect(contrastRatio('#000000', '#FFFFFF')).toBeCloseTo(21, 0);
  });
  it('white on white is 1:1', () => {
    expect(contrastRatio('#FFFFFF', '#FFFFFF')).toBeCloseTo(1, 1);
  });
  it('is order-independent', () => {
    expect(contrastRatio('#1E1F2E', '#FCFAF4')).toBeCloseTo(contrastRatio('#FCFAF4', '#1E1F2E'), 5);
  });
  it('relativeLuminance of white is ~1', () => {
    expect(relativeLuminance('#FFFFFF')).toBeCloseTo(1, 2);
  });
});
