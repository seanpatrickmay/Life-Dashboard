const GUEST_MODE_KEY = 'ld_guest_mode';

export const isGuestMode = (): boolean => {
  if (!isGuestDemoEnabled()) return false;
  if (typeof window === 'undefined') return false;
  return window.localStorage.getItem(GUEST_MODE_KEY) === '1';
};

export const enterGuestMode = (): void => {
  if (!isGuestDemoEnabled()) return;
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(GUEST_MODE_KEY, '1');
};

export const exitGuestMode = (): void => {
  if (typeof window === 'undefined') return;
  window.localStorage.removeItem(GUEST_MODE_KEY);
};

export const isGuestDemoEnabled = (): boolean => {
  const flag = import.meta.env.VITE_GUEST_DEMO_ENABLED;
  if (!flag) return true;
  return flag !== 'false';
};
