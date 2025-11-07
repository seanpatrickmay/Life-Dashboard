import { PropsWithChildren } from 'react';
import styled, { css } from 'styled-components';
import { Link, useLocation } from 'react-router-dom';
import { composeLayers, getCardLayers, palette } from '../../theme/monetTheme';

const paletteAccent = (mode: 'light' | 'dark') =>
  mode === 'dark' ? palette.bloom['300'] : palette.bloom['200'];

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
  display: inline-flex;
  gap: 16px;
  padding: 14px 18px;
  border-radius: ${({ theme }) => theme.radii?.shell ?? '18px'};
  border: 2px solid ${({ theme }) => theme.colors.borderSubtle};
  background-color: ${({ theme }) => theme.colors.backgroundCard};
  ${({ theme }) => {
    const layers = composeLayers(
      getCardLayers(theme.mode ?? 'light', theme.intensity ?? 'rich')
    );
    return css`
      background-image: ${layers.image};
      background-size: ${layers.size};
      background-repeat: ${layers.repeat};
      background-position: ${layers.position};
      ${layers.blend ? `background-blend-mode: ${layers.blend};` : ''}
    `;
  }};
  image-rendering: pixelated;
  box-shadow: ${({ theme }) => theme.shadows.pixel};

  a {
    font-family: ${({ theme }) => theme.fonts.heading};
    font-size: 0.75rem;
    text-transform: uppercase;
    text-decoration: none;
    color: ${({ theme }) => theme.colors.textSecondary};
    opacity: 0.7;
    transition: opacity 0.2s ease, color 0.2s ease;
    border-bottom: 2px solid transparent;
    padding-bottom: 2px;

    &.active {
      opacity: 1;
      color: ${({ theme }) => theme.colors.textPrimary};
      text-shadow: 0 0 6px rgba(215, 127, 179, 0.4);
      border-bottom: 2px solid ${({ theme }) => paletteAccent(theme.mode ?? 'light')};
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
      <Nav>
        <Link className={pathname === '/' ? 'active' : ''} to="/">
          Dashboard
        </Link>
        <Link className={pathname.startsWith('/insights') ? 'active' : ''} to="/insights">
          Insights
        </Link>
        <Link className={pathname.startsWith('/settings') ? 'active' : ''} to="/settings">
          Settings
        </Link>
      </Nav>
      <Surface>{children}</Surface>
    </Frame>
  );
}
