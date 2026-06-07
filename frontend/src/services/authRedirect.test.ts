import { describe, expect, it } from 'vitest';

import { shouldRedirectOn401 } from './authRedirect';

describe('shouldRedirectOn401', () => {
  it('redirects on a 401 from a protected page for a normal user', () => {
    expect(shouldRedirectOn401(401, '/dashboard', false)).toBe(true);
  });

  it('does NOT redirect when in guest mode', () => {
    expect(shouldRedirectOn401(401, '/dashboard', true)).toBe(false);
  });

  it('does NOT redirect when already on /login', () => {
    expect(shouldRedirectOn401(401, '/login', false)).toBe(false);
  });

  it('does NOT redirect for non-401 statuses', () => {
    expect(shouldRedirectOn401(500, '/dashboard', false)).toBe(false);
  });

  it('does NOT redirect when status is undefined', () => {
    expect(shouldRedirectOn401(undefined, '/dashboard', false)).toBe(false);
  });
});
