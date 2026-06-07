/**
 * MoreSheet — bottom sheet opened from the "More" tab in BottomNav.
 * A11y shell mirrors TuneDrawer/SettingsDrawer:
 *   - Backdrop click closes, panel click does not propagate
 *   - focus-into on open, focus restore on close
 *   - Escape closes, Tab focus-trap
 *   - role="dialog" aria-modal="true"
 *
 * Items: Body · Calendar · Projects → navigate + onClose
 *        Settings → onOpenSettings (opens existing SettingsDrawer from PageShell)
 */
import { useEffect, useRef } from 'react';
import styled, { keyframes } from 'styled-components';
import { Link } from 'react-router-dom';

/* ─── Animations ──────────────────────────────────────────────── */

const slideUp = keyframes`
  from { transform: translateY(100%); opacity: 0; }
  to   { transform: translateY(0);    opacity: 1; }
`;

/* ─── Styled ─────────────────────────────────────────────────── */

const Backdrop = styled.div`
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  z-index: 250;
  display: flex;
  align-items: flex-end;
`;

const Panel = styled.div`
  background: ${({ theme }) => theme.colors.backgroundCard};
  border-top-left-radius: 20px;
  border-top-right-radius: 20px;
  padding: 20px 20px calc(env(safe-area-inset-bottom) + 24px);
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 4px;
  animation: ${slideUp} 0.25s ease-out both;

  scrollbar-width: thin;
  scrollbar-color: ${({ theme }) => theme.colors.scrollThumb} transparent;
  overscroll-behavior: contain;
`;

const Header = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
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
  min-width: 44px;
  min-height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  &:hover { opacity: 1; }
  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: 2px;
    border-radius: 4px;
  }
`;

const SheetItem = styled.div`
  a, button {
    display: flex;
    align-items: center;
    gap: 12px;
    width: 100%;
    padding: 14px 12px;
    border-radius: 12px;
    text-decoration: none;
    color: ${({ theme }) => theme.colors.textPrimary};
    background: none;
    border: none;
    cursor: pointer;
    font-family: ${({ theme }) => theme.fonts.heading};
    font-size: 0.9rem;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    text-align: left;
    opacity: 0.85;
    transition: opacity 0.15s ease, background 0.15s ease;

    &:hover {
      opacity: 1;
      background: ${({ theme }) => theme.colors.overlayHover ?? 'rgba(255,255,255,0.05)'};
    }

    &:focus-visible {
      outline: 2px solid ${({ theme }) => theme.colors.focusRing};
      outline-offset: 2px;
    }
  }
`;

const ItemIcon = styled.span`
  font-size: 1.1rem;
  line-height: 1;
  min-width: 24px;
  text-align: center;
`;

const Divider = styled.hr`
  border: none;
  border-top: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  margin: 8px 0;
  opacity: 0.4;
`;

/* ─── Focusable selector ──────────────────────────────────────── */

const FOCUSABLE = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(', ');

/* ─── Component ──────────────────────────────────────────────── */

interface MoreSheetProps {
  onClose: () => void;
  onOpenSettings: () => void;
}

export function MoreSheet({ onClose, onOpenSettings }: MoreSheetProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const closeBtnRef = useRef<HTMLButtonElement>(null);
  const previousFocusRef = useRef<Element | null>(null);

  // Lock body scroll while sheet is open
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

  return (
    <Backdrop
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}
      data-testid="more-sheet-backdrop"
    >
      <Panel
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label="More"
        onClick={e => e.stopPropagation()}
      >
        <Header>
          <Title>More</Title>
          <CloseBtn ref={closeBtnRef} onClick={onClose} aria-label="Close">
            ✕
          </CloseBtn>
        </Header>

        <SheetItem>
          <Link to="/body" onClick={onClose}>
            <ItemIcon aria-hidden="true">🏃</ItemIcon>
            Body
          </Link>
        </SheetItem>

        <SheetItem>
          <Link to="/calendar" onClick={onClose}>
            <ItemIcon aria-hidden="true">📅</ItemIcon>
            Calendar
          </Link>
        </SheetItem>

        <SheetItem>
          <Link to="/projects" onClick={onClose}>
            <ItemIcon aria-hidden="true">📋</ItemIcon>
            Projects
          </Link>
        </SheetItem>

        <Divider />

        <SheetItem>
          <button type="button" onClick={onOpenSettings}>
            <ItemIcon aria-hidden="true">⚙</ItemIcon>
            Settings
          </button>
        </SheetItem>
      </Panel>
    </Backdrop>
  );
}
