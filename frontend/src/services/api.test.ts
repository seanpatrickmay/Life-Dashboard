// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  api,
  fetchAllActivities,
  fetchDigest,
  fetchNutritionIngredients,
  fetchNutritionNutrients,
  fetchNutritionRecipe,
  fetchNutritionRecipes,
  fetchProjectActivities,
  refreshDigest,
  resolveApiBaseUrl
} from './api';
import { enterGuestMode, exitGuestMode } from '../demo/guest/guestMode';

// Guest mode flag key (must match guestMode.ts)
const GUEST_MODE_KEY = 'ld_guest_mode';

const httpsLocation = {
  protocol: 'https:',
  origin: 'https://lifedashboard.tech',
  hostname: 'lifedashboard.tech'
};

const localLocation = {
  protocol: 'http:',
  origin: 'http://localhost:4173',
  hostname: 'localhost'
};

describe('fetchDigest / refreshDigest — guest guards', () => {
  beforeEach(() => {
    localStorage.clear();
    // Enable guest demo + set guest mode
    localStorage.setItem(GUEST_MODE_KEY, '1');
    vi.stubEnv('VITE_GUEST_DEMO_ENABLED', 'true');
  });

  afterEach(() => {
    localStorage.clear();
    vi.unstubAllEnvs();
  });

  it('fetchDigest returns empty digest in guest mode without calling network', async () => {
    const result = await fetchDigest();
    expect(result.items).toEqual([]);
    expect(result.item_count).toBe(0);
    expect(result.narrative).toBeNull();
    expect(result.is_stale).toBe(false);
  });

  it('refreshDigest returns disabled message in guest mode without calling network', async () => {
    const result = await refreshDigest();
    expect(result.started).toBe(false);
    expect(result.message).toContain('demo');
  });
});

describe('resolveApiBaseUrl', () => {
  it('upgrades http env base on https pages', () => {
    const resolved = resolveApiBaseUrl({
      envBase: 'http://lifedashboard.tech',
      location: httpsLocation
    });
    expect(resolved).toBe('https://lifedashboard.tech');
  });

  it('falls back to origin when http env base points at localhost on https pages', () => {
    const resolved = resolveApiBaseUrl({
      envBase: 'http://localhost:8000',
      location: httpsLocation
    });
    expect(resolved).toBe('https://lifedashboard.tech');
  });

  it('returns env base when already https', () => {
    const resolved = resolveApiBaseUrl({
      envBase: 'https://api.example.com',
      location: httpsLocation
    });
    expect(resolved).toBe('https://api.example.com');
  });

  it('uses origin when no env base on https host', () => {
    const resolved = resolveApiBaseUrl({ location: httpsLocation });
    expect(resolved).toBe('https://lifedashboard.tech');
  });

  it('uses localhost for local dev hosts', () => {
    const resolved = resolveApiBaseUrl({ location: localLocation });
    expect(resolved).toBe('http://localhost:8000');
  });

  it('uses localhost when no location is available', () => {
    const resolved = resolveApiBaseUrl();
    expect(resolved).toBe('http://localhost:8000');
  });
});

describe('guest mode API short-circuits', () => {
  beforeEach(() => {
    enterGuestMode();
  });

  afterEach(() => {
    exitGuestMode();
    vi.restoreAllMocks();
  });

  it('fetchDigest returns an empty digest without calling the network', async () => {
    const getSpy = vi
      .spyOn(api, 'get')
      .mockRejectedValue(new Error('network must not be called in guest mode'));
    const result = await fetchDigest();
    expect(result).toEqual({
      items: [],
      last_refreshed: null,
      item_count: 0,
      is_stale: false,
      narrative: null
    });
    expect(getSpy).not.toHaveBeenCalled();
  });

  it('refreshDigest reports disabled without calling the network', async () => {
    const postSpy = vi
      .spyOn(api, 'post')
      .mockRejectedValue(new Error('network must not be called in guest mode'));
    const result = await refreshDigest();
    expect(result).toEqual({
      started: false,
      message: 'Refreshing the digest is disabled in demo mode.'
    });
    expect(postSpy).not.toHaveBeenCalled();
  });

  it('fetchProjectActivities returns [] without calling the network', async () => {
    const getSpy = vi
      .spyOn(api, 'get')
      .mockRejectedValue(new Error('network must not be called in guest mode'));
    const result = await fetchProjectActivities(1);
    expect(result).toEqual([]);
    expect(getSpy).not.toHaveBeenCalled();
  });

  it('fetchAllActivities returns [] without calling the network', async () => {
    const getSpy = vi
      .spyOn(api, 'get')
      .mockRejectedValue(new Error('network must not be called in guest mode'));
    const result = await fetchAllActivities();
    expect(result).toEqual([]);
    expect(getSpy).not.toHaveBeenCalled();
  });

  it('fetchNutritionNutrients returns [] without calling the network', async () => {
    const getSpy = vi
      .spyOn(api, 'get')
      .mockRejectedValue(new Error('network must not be called in guest mode'));
    const result = await fetchNutritionNutrients();
    expect(result).toEqual([]);
    expect(getSpy).not.toHaveBeenCalled();
  });

  it('fetchNutritionIngredients returns [] without calling the network', async () => {
    const getSpy = vi
      .spyOn(api, 'get')
      .mockRejectedValue(new Error('network must not be called in guest mode'));
    const result = await fetchNutritionIngredients();
    expect(result).toEqual([]);
    expect(getSpy).not.toHaveBeenCalled();
  });

  it('fetchNutritionRecipes returns [] without calling the network', async () => {
    const getSpy = vi
      .spyOn(api, 'get')
      .mockRejectedValue(new Error('network must not be called in guest mode'));
    const result = await fetchNutritionRecipes();
    expect(result).toEqual([]);
    expect(getSpy).not.toHaveBeenCalled();
  });

  it('fetchNutritionRecipe throws a friendly demo error without calling the network', async () => {
    const getSpy = vi
      .spyOn(api, 'get')
      .mockRejectedValue(new Error('network must not be called in guest mode'));
    await expect(fetchNutritionRecipe(1)).rejects.toThrow(
      'Recipe details are not available in demo mode.'
    );
    expect(getSpy).not.toHaveBeenCalled();
  });
});
