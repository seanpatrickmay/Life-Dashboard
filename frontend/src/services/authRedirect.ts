/**
 * Decides whether a failed response should bounce the user to /login.
 * Pure so the interceptor's side effect (window.location) stays testable.
 */
export function shouldRedirectOn401(
  status: number | undefined,
  pathname: string,
  guest: boolean
): boolean {
  return status === 401 && pathname !== '/login' && !guest;
}
