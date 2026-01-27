import { describe, expect, it } from 'vitest';

import { resolveApiBaseUrl } from './api';

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
