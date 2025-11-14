import { PropsWithChildren } from 'react';
import styled, { css } from 'styled-components';
import { Link, useLocation } from 'react-router-dom';
import { composeLayers, getCardLayers, palette } from '../../theme/monetTheme';
import { CloudNavShelf } from './CloudNavShelf';

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
    color: ${({ theme }) => theme.colors.textSecondary};
    opacity: 0.72;
    transition: opacity 0.2s ease, color 0.2s ease, transform 0.2s ease;
    border-bottom: 2px solid transparent;
    padding-bottom: 4px;
    &:hover {
      opacity: 0.9;
    }
    &.active {
      opacity: 1;
      color: ${({ theme }) => theme.colors.textPrimary};
      border-bottom: 2px solid ${({ theme }) => paletteAccent(theme.mode ?? 'light', theme)};
      text-shadow: 0 0 8px rgba(255, 255, 255, 0.4);
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

export function PageShell({ children }: PropsWithChildren) {
  const { pathname } = useLocation();
  return (
    <Frame>
      <CloudNavShelf>
        <Nav>
          <Link className={pathname === '/' ? 'active' : ''} to="/">
            Dashboard
          </Link>
          <Link className={pathname.startsWith('/insights') ? 'active' : ''} to="/insights">
            Insights
          </Link>
          <Link className={pathname.startsWith('/garden') ? 'active' : ''} to="/garden">
            Garden
          </Link>
          <Link className={pathname.startsWith('/nutrition') ? 'active' : ''} to="/nutrition">
            Nutrition
          </Link>
          <Link className={pathname.startsWith('/user') ? 'active' : ''} to="/user">
            User
          </Link>
          <Link className={pathname.startsWith('/settings') ? 'active' : ''} to="/settings">
            Settings
          </Link>
        </Nav>
      </CloudNavShelf>
      <Surface>{children}</Surface>
    </Frame>
  );
}
