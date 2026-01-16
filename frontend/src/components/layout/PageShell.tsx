import { PropsWithChildren } from 'react';
import styled, { css } from 'styled-components';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { composeLayers, getCardLayers, palette } from '../../theme/monetTheme';
import { CloudNavShelf } from './CloudNavShelf';
import { exitGuestMode, isGuestMode } from '../../demo/guest/guestMode';
import { clearGuestState } from '../../demo/guest/guestStore';

const paletteAccent = (mode: 'light' | 'dark', theme?: any) =>
  theme?.colors?.accent ?? (mode === 'dark' ? palette.bloom['300'] : palette.bloom['200']);

const Frame = styled.div`
  padding: clamp(20px, 3vw, 36px);
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 24px;
  color: ${({ theme }) => theme.colors.textPrimary};
`;

const Nav = styled.nav`
  display: flex;
  width: min(90vw, 840px);
  gap: clamp(12px, 3vw, 28px);
  justify-content: space-between;
  padding: clamp(12px, 1.5vh, 20px) clamp(8px, 2vw, 24px);
  a {
    flex: 1;
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
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.18);
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
  border: 1px solid rgba(255, 255, 255, 0.3);
  background: transparent;
  color: ${({ theme }) => theme.colors.textPrimary};
  font-family: ${({ theme }) => theme.fonts.heading};
  letter-spacing: 0.16em;
  text-transform: uppercase;
  font-size: 0.7rem;
  cursor: pointer;
`;

export function PageShell({ children }: PropsWithChildren) {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const guestMode = isGuestMode();
  return (
    <Frame>
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
      <CloudNavShelf>
        <Nav>
          <Link className={pathname === '/' ? 'active' : ''} to="/">
            Dashboard
          </Link>
          <Link className={pathname.startsWith('/insights') ? 'active' : ''} to="/insights">
            Insights
          </Link>
          <Link className={pathname.startsWith('/journal') ? 'active' : ''} to="/journal">
            Journal
          </Link>
          <Link className={pathname.startsWith('/nutrition') ? 'active' : ''} to="/nutrition">
            Nutrition
          </Link>
          <Link className={pathname.startsWith('/user') ? 'active' : ''} to="/user">
            User
          </Link>
        </Nav>
      </CloudNavShelf>
      <Surface>{children}</Surface>
    </Frame>
  );
}
