// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { resolveApiBaseUrl, fetchDigest, refreshDigest } from './api';

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
    expect(result.message).toContain('guest');
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
