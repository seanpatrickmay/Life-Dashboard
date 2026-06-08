import { describe, it, expect } from 'vitest';
import { pixelPanel, pixelWell } from './surfaces';

describe('surfaces mixins', () => {
  it('pixelPanel is defined and is an array (styled-components css tag)', () => {
    expect(pixelPanel).toBeDefined();
    expect(Array.isArray(pixelPanel)).toBe(true);
  });

  it('pixelWell is defined and is an array (styled-components css tag)', () => {
    expect(pixelWell).toBeDefined();
    expect(Array.isArray(pixelWell)).toBe(true);
  });
});
