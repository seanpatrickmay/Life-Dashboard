// @vitest-environment jsdom
import { describe, expect, it, beforeEach } from 'vitest';
import {
  getBoostedTopics,
  saveBoostedTopics,
  getMutedTopics,
  saveMutedTopics,
} from './interestProfile';

beforeEach(() => { localStorage.clear(); });

describe('boost/mute topic persistence', () => {
  it('getBoostedTopics returns empty array when nothing stored', () => {
    expect(getBoostedTopics()).toEqual([]);
  });

  it('saveBoostedTopics → getBoostedTopics roundtrip', () => {
    saveBoostedTopics(['llm', 'rust']);
    expect(getBoostedTopics()).toEqual(['llm', 'rust']);
  });

  it('getMutedTopics returns empty array when nothing stored', () => {
    expect(getMutedTopics()).toEqual([]);
  });

  it('saveMutedTopics → getMutedTopics roundtrip', () => {
    saveMutedTopics(['celebrity', 'sports']);
    expect(getMutedTopics()).toEqual(['celebrity', 'sports']);
  });

  it('boosted and muted topics are stored independently', () => {
    saveBoostedTopics(['llm']);
    saveMutedTopics(['celebrity']);
    expect(getBoostedTopics()).toEqual(['llm']);
    expect(getMutedTopics()).toEqual(['celebrity']);
  });

  it('overwrites on second save', () => {
    saveBoostedTopics(['llm']);
    saveBoostedTopics(['rust', 'wasm']);
    expect(getBoostedTopics()).toEqual(['rust', 'wasm']);
  });

  it('handles corrupted localStorage gracefully for boosted', () => {
    localStorage.setItem('ld_boosted_topics', 'not json!!!');
    expect(getBoostedTopics()).toEqual([]);
  });

  it('handles corrupted localStorage gracefully for muted', () => {
    localStorage.setItem('ld_muted_topics', 'bad{{}');
    expect(getMutedTopics()).toEqual([]);
  });
});
