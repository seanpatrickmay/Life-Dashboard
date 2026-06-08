import { PropsWithChildren, useState, useEffect, useCallback } from 'react';
import styled from 'styled-components';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import { CloudNavShelf } from './CloudNavShelf';
import { MonetChatBubble } from '../dashboard/MonetChatPanel';
import { exitGuestMode, isGuestMode } from '../../demo/guest/guestMode';
import { clearGuestState } from '../../demo/guest/guestStore';
import { SettingsDrawer } from './SettingsDrawer';
import { MovedBanner } from './MovedBanner';
import { BottomNav, BOTTOM_NAV_HEIGHT_PX } from './BottomNav';
import { MoreSheet } from './MoreSheet';
import { useIsMobile } from '../../hooks/useMediaQuery';

const Frame = styled.div<{ $fullWidth?: boolean; $mobileBottomPad?: boolean }>`
  padding: clamp(20px, 3vw, 36px);
  max-width: ${({ $fullWidth }) => ($fullWidth ? '100%' : '1200px')};
  width: 100%;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 24px;
  color: ${({ theme }) => theme.colors.textPrimary};
  ${({ $mobileBottomPad }) =>
    $mobileBottomPad
      ? `padding-bottom: calc(${BOTTOM_NAV_HEIGHT_PX}px + env(safe-area-inset-bottom) + 16px);`
      : ''}
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
    color: ${({ theme }) => theme.colors.textSecondary};
    transition: color 0.15s ease;
    /* Pixel-shelf baseline indicator */
    border-bottom: 2px solid transparent;
    padding-bottom: 4px;
    &:hover {
      color: ${({ theme }) => theme.colors.textPrimary};
    }
    &.active {
      color: ${({ theme }) => theme.colors.accentStrong};
      border-bottom: 2px solid ${({ theme }) => theme.colors.accentStrong};
    }
    &:focus-visible {
      outline: 2px solid ${({ theme }) => theme.colors.focusRing};
      outline-offset: 2px;
      border-radius: 3px;
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
  const isMobile = useIsMobile();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);

  // Close drawers on route changes so they don't block the new page
  useEffect(() => {
    setSettingsOpen(false);
    setMoreOpen(false);
  }, [pathname]);

  // Stable callbacks — avoids re-registering keydown effects every render
  const handleSettingsClose = useCallback(() => setSettingsOpen(false), []);
  const handleMoreClose = useCallback(() => setMoreOpen(false), []);
  const handleOpenSettings = useCallback(() => {
    setMoreOpen(false);
    setSettingsOpen(true);
  }, []);

  return (
    <Frame $fullWidth={fullWidth} $mobileBottomPad={isMobile}>
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
      {!isMobile && (
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
      )}
      <main><Surface>{children}</Surface></main>
      <MonetChatBubble />
      {isMobile && (
        <BottomNav onMore={() => setMoreOpen(true)} moreOpen={moreOpen} />
      )}
      {moreOpen && (
        <MoreSheet onClose={handleMoreClose} onOpenSettings={handleOpenSettings} />
      )}
      {settingsOpen && (
        <SettingsDrawer onClose={handleSettingsClose} />
      )}
    </Frame>
  );
}
