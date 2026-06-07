/**
 * SettingsDrawer — slide-in settings panel opened from the gear icon in PageShell.
 * - A11y shell mirrors TuneDrawer: focus trap, Escape close, focus restore.
 * - Mobile = bottom sheet; desktop = right slide-in panel.
 * - Reuses <UserProfileScene/> wholesale for Garmin + biometrics + sign-out.
 */
import { useEffect, useRef, useCallback } from 'react';
import styled, { keyframes } from 'styled-components';
import { reducedMotion } from '../../styles/animations';
import { useNavigate } from 'react-router-dom';
import { useThemeMode } from '../../theme/ThemeProvider';
import { UserProfileScene } from '../user/UserProfileScene';

/* ─── Animations ──────────────────────────────────── */

const slideUp = keyframes`
  from { transform: translateY(100%); opacity: 0; }
  to   { transform: translateY(0);    opacity: 1; }
`;

const slideIn = keyframes`
  from { transform: translateX(100%); opacity: 0; }
  to   { transform: translateX(0);    opacity: 1; }
`;

/* ─── Styled ─────────────────────────────────────── */

const Backdrop = styled.div`
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  z-index: 200;
  display: flex;
  align-items: flex-end;
  justify-content: flex-end;

  @media (min-width: 700px) {
    align-items: stretch;
  }
`;

const Panel = styled.div`
  background: ${({ theme }) => theme.colors.backgroundCard};
  border-top-left-radius: 20px;
  border-top-right-radius: 20px;
  padding: 20px 20px 32px;
  width: 100%;
  max-height: 90vh;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
  animation: ${slideUp} 0.25s ease-out both;

  @media (min-width: 700px) {
    width: 420px;
    max-height: 100vh;
    border-radius: 0;
    border-left: 1px solid ${({ theme }) => theme.colors.borderSubtle};
    animation: ${slideIn} 0.25s ease-out both;
  }

  ${reducedMotion}

  scrollbar-width: thin;
  scrollbar-color: ${({ theme }) => theme.colors.scrollThumb} transparent;
  overscroll-behavior: contain;
`;

const Header = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
`;

const Title = styled.h2`
  margin: 0;
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: clamp(1rem, 1.8vw, 1.2rem);
  letter-spacing: 0.15em;
  text-transform: uppercase;
`;

const CloseBtn = styled.button`
  background: none;
  border: none;
  cursor: pointer;
  color: inherit;
  font-size: 1.2rem;
  opacity: 0.5;
  line-height: 1;
  padding: 4px;
  &:hover { opacity: 1; }
  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: 2px;
  }
`;

const SectionTitle = styled.div`
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.7rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  opacity: 0.5;
  margin-bottom: 10px;
`;

const ThemeRow = styled.div`
  display: flex;
  gap: 8px;
`;

const ThemeBtn = styled.button<{ $active: boolean }>`
  flex: 1;
  padding: 8px 0;
  border-radius: 8px;
  border: 1px solid ${({ theme, $active }) =>
    $active ? theme.colors.accent : theme.colors.borderSubtle};
  background: ${({ theme, $active }) =>
    $active ? theme.colors.overlay : 'transparent'};
  color: ${({ theme, $active }) =>
    $active ? theme.colors.accent : 'inherit'};
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.72rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  cursor: pointer;
  opacity: ${({ $active }) => ($active ? 1 : 0.55)};
  transition: all 0.15s ease;
  ${reducedMotion}
  &:hover { opacity: 1; }
  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: 2px;
  }
`;

const FoodDbBtn = styled.button`
  width: 100%;
  text-align: left;
  padding: 10px 14px;
  border-radius: 10px;
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  background: ${({ theme }) => theme.colors.overlay};
  color: inherit;
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.75rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: space-between;
  opacity: 0.85;
  transition: opacity 0.15s ease;
  ${reducedMotion}
  &:hover { opacity: 1; }
  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: 2px;
  }
`;

const Divider = styled.hr`
  border: none;
  border-top: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  margin: 0;
  opacity: 0.4;
`;

/* ─── Focusable selector (mirrors TuneDrawer) ─────── */

const FOCUSABLE = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(', ');

/* ─── Component ──────────────────────────────────── */

interface SettingsDrawerProps {
  onClose: () => void;
}

export function SettingsDrawer({ onClose }: SettingsDrawerProps) {
  const { mode, setMode } = useThemeMode();
  const navigate = useNavigate();
  const panelRef = useRef<HTMLDivElement>(null);
  const closeBtnRef = useRef<HTMLButtonElement>(null);
  const previousFocusRef = useRef<Element | null>(null);

  // Fix 2: lock body scroll while drawer is open; restore on unmount
  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = prev; };
  }, []);

  // Move focus into dialog on open; restore on close
  useEffect(() => {
    previousFocusRef.current = document.activeElement;
    const firstFocusable =
      closeBtnRef.current ??
      panelRef.current?.querySelector<HTMLElement>(FOCUSABLE) ??
      null;
    firstFocusable?.focus();

    return () => {
      (previousFocusRef.current as HTMLElement | null)?.focus?.();
    };
  }, []);

  // Close on Escape; trap Tab/Shift+Tab inside panel
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
        return;
      }
      if (e.key !== 'Tab' || !panelRef.current) return;

      const focusable = Array.from(
        panelRef.current.querySelectorAll<HTMLElement>(FOCUSABLE),
      ).filter(el => !el.closest('[disabled]'));

      if (focusable.length === 0) {
        e.preventDefault();
        return;
      }

      const first = focusable[0];
      const last = focusable[focusable.length - 1];

      if (e.shiftKey) {
        if (document.activeElement === first) {
          e.preventDefault();
          last.focus();
        }
      } else {
        if (document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [onClose]);

  const handleFoodDb = useCallback(() => {
    navigate('/settings/food-db');
    onClose();
  }, [navigate, onClose]);

  return (
    <Backdrop onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <Panel
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="settings-drawer-title"
      >
        <Header>
          <Title id="settings-drawer-title">Settings</Title>
          <CloseBtn ref={closeBtnRef} onClick={onClose} aria-label="Close">
            ✕
          </CloseBtn>
        </Header>

        {/* Theme control */}
        <section>
          <SectionTitle>Theme</SectionTitle>
          <ThemeRow>
            <ThemeBtn
              $active={mode === 'light'}
              onClick={() => setMode('light')}
              aria-pressed={mode === 'light'}
            >
              Light
            </ThemeBtn>
            <ThemeBtn
              $active={mode === 'dark'}
              onClick={() => setMode('dark')}
              aria-pressed={mode === 'dark'}
            >
              Dark
            </ThemeBtn>
            <ThemeBtn
              $active={mode === 'system'}
              onClick={() => setMode('system')}
              aria-pressed={mode === 'system'}
            >
              System
            </ThemeBtn>
          </ThemeRow>
        </section>

        {/* Food database link */}
        <section>
          <SectionTitle>Nutrition</SectionTitle>
          <FoodDbBtn onClick={handleFoodDb} aria-label="Manage food database">
            <span>Manage food database</span>
            <span aria-hidden="true">→</span>
          </FoodDbBtn>
        </section>

        <Divider />

        {/* Garmin + biometrics + sign-out (reused wholesale) */}
        <UserProfileScene />
      </Panel>
    </Backdrop>
  );
}
