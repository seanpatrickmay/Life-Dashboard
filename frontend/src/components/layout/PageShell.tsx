import { PropsWithChildren, useState, useEffect, useCallback } from 'react';
import styled from 'styled-components';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import { palette } from '../../theme/monetTheme';
import { CloudNavShelf } from './CloudNavShelf';
import { MonetChatBubble } from '../dashboard/MonetChatPanel';
import { exitGuestMode, isGuestMode } from '../../demo/guest/guestMode';
import { clearGuestState } from '../../demo/guest/guestStore';
import { SettingsDrawer } from './SettingsDrawer';
import { MovedBanner } from './MovedBanner';

const paletteAccent = (mode: 'light' | 'dark', theme?: { colors?: { accent?: string } }) =>
  theme?.colors?.accent ?? (mode === 'dark' ? palette.bloom['300'] : palette.bloom['200']);

const Frame = styled.div<{ $fullWidth?: boolean }>`
  padding: clamp(20px, 3vw, 36px);
  max-width: ${({ $fullWidth }) => ($fullWidth ? '100%' : '1200px')};
  width: 100%;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 24px;
  color: ${({ theme }) => theme.colors.textPrimary};
`;

const Nav = styled.nav`
  display: flex;
  width: min(90vw, 560px);
  gap: clamp(20px, 4vw, 40px);
  justify-content: flex-start;
  padding: clamp(12px, 1.5vh, 20px) clamp(8px, 2vw, 24px);
  overflow-x: auto;
  scrollbar-width: none;
  -ms-overflow-style: none;
  &::-webkit-scrollbar { display: none; }
  a {
    flex: none;
    white-space: nowrap;
    text-align: center;
    font-family: ${({ theme }) => theme.fonts.heading};
    font-size: clamp(0.68rem, 0.9vw, 0.85rem);
    letter-spacing: 0.16em;
    text-transform: uppercase;
    text-decoration: none;
    color: ${({ theme }) => theme.colors.textPrimary};
    opacity: 0.86;
    text-shadow: 0 2px 10px rgba(10, 18, 40, 0.55);
    transition: opacity 0.2s ease, color 0.2s ease, transform 0.2s ease, text-shadow 0.2s ease;
    border-bottom: 2px solid transparent;
    padding-bottom: 4px;
    &:hover {
      opacity: 1;
      text-shadow: 0 2px 12px rgba(10, 18, 40, 0.7);
    }
    &.active {
      opacity: 1;
      color: ${({ theme }) => theme.colors.textPrimary};
      border-bottom: 2px solid ${({ theme }) => paletteAccent(theme.mode ?? 'light', theme)};
      text-shadow: 0 0 10px rgba(255, 255, 255, 0.5);
    }
  }
`;

const Surface = styled.div`
  border-radius: 32px;
  padding: clamp(16px, 2vw, 24px);
  background: transparent;
  border: none;
  box-shadow: none;
`;

const GuestBanner = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 16px;
  border-radius: 16px;
  background: ${({ theme }) => theme.colors.overlay};
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  font-size: 0.8rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
`;

const GuestBannerText = styled.span`
  opacity: 0.85;
`;

const GuestExitButton = styled.button`
  border-radius: 999px;
  padding: 6px 12px;
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  background: transparent;
  color: ${({ theme }) => theme.colors.textPrimary};
  font-family: ${({ theme }) => theme.fonts.heading};
  letter-spacing: 0.16em;
  text-transform: uppercase;
  font-size: 0.7rem;
  cursor: pointer;
  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: 2px;
  }
`;

const NavRow = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
`;

const GearButton = styled.button`
  background: none;
  border: none;
  cursor: pointer;
  color: ${({ theme }) => theme.colors.textPrimary};
  font-size: 1rem;
  opacity: 0.6;
  line-height: 1;
  padding: 10px 12px;
  min-width: 44px;
  min-height: 44px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: opacity 0.2s ease;
  &:hover { opacity: 1; }
  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: 2px;
    border-radius: 4px;
  }
`;

export function PageShell({ children }: PropsWithChildren) {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const guestMode = isGuestMode();
  const fullWidth = pathname.startsWith('/calendar') || pathname.startsWith('/projects') || pathname.startsWith('/read');
  const [settingsOpen, setSettingsOpen] = useState(false);

  // Fix 1: close drawer on route changes so it doesn't block the new page
  useEffect(() => {
    setSettingsOpen(false);
  }, [pathname]);

  // Fix 4: stable callback — avoids re-registering the keydown effect in SettingsDrawer every render
  const handleSettingsClose = useCallback(() => setSettingsOpen(false), []);

  return (
    <Frame $fullWidth={fullWidth}>
      {guestMode ? (
        <GuestBanner>
          <GuestBannerText>Guest mode - demo data only - sign in to save changes</GuestBannerText>
          <GuestExitButton
            type="button"
            onClick={() => {
              clearGuestState();
              exitGuestMode();
              navigate('/login', { replace: true });
            }}
          >
            Exit Guest
          </GuestExitButton>
        </GuestBanner>
      ) : null}
      <MovedBanner />
      <CloudNavShelf>
        <NavRow>
          <Nav aria-label="Main navigation">
            <NavLink className={({ isActive }) => isActive ? 'active' : ''} to="/" end>
              Today
            </NavLink>
            <NavLink className={({ isActive }) => isActive ? 'active' : ''} to="/read">
              Read
            </NavLink>
            <NavLink className={({ isActive }) => isActive ? 'active' : ''} to="/reflect">
              Reflect
            </NavLink>
          </Nav>
          <GearButton
            type="button"
            onClick={() => setSettingsOpen(true)}
            aria-label="Settings"
            aria-haspopup="dialog"
            aria-expanded={settingsOpen}
          >
            ⚙
          </GearButton>
        </NavRow>
      </CloudNavShelf>
      <main><Surface>{children}</Surface></main>
      <MonetChatBubble />
      {settingsOpen && (
        <SettingsDrawer onClose={handleSettingsClose} />
      )}
    </Frame>
  );
}
