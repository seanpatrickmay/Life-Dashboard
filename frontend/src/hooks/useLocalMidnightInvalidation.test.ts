// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';
import { DAY_SCOPED_KEYS } from './useLocalMidnightInvalidation';

describe('DAY_SCOPED_KEYS', () => {
  it('contains news curated key', () => {
    expect(DAY_SCOPED_KEYS).toContainEqual(['news', 'curated']);
  });

  it('contains news annotations key', () => {
    expect(DAY_SCOPED_KEYS).toContainEqual(['news', 'annotations']);
  });
});
