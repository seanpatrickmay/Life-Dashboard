/**
 * BottomNav — fixed mobile bottom tab bar.
 * Shown only on mobile (rendered conditionally by PageShell via useIsMobile).
 * Four items: Today · Read · Reflect · More (⋯)
 * - Today/Read/Reflect are real NavLinks (aria-current handled by NavLink)
 * - More opens the MoreSheet via onMore prop
 */
import styled from 'styled-components';
import { NavLink } from 'react-router-dom';
import { Z_LAYERS } from '../../styles/zLayers';
import { palette } from '../../theme/monetTheme';

const BOTTOM_NAV_HEIGHT = 56;

/** Exported so PageShell + MonetChatBubble can offset by this value on mobile */
export const BOTTOM_NAV_HEIGHT_PX = BOTTOM_NAV_HEIGHT;

const paletteAccent = (mode: 'light' | 'dark', theme?: { colors?: { accent?: string } }) =>
  theme?.colors?.accent ?? (mode === 'dark' ? palette.bloom['300'] : palette.bloom['200']);

const Bar = styled.nav`
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: ${Z_LAYERS.nav + 1};
  min-height: ${BOTTOM_NAV_HEIGHT}px;
  padding-bottom: env(safe-area-inset-bottom);
  background: ${({ theme }) => theme.colors.backgroundCard};
  border-top: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  box-shadow: 0 -2px 12px rgba(0, 0, 0, 0.2);
  display: flex;
  align-items: stretch;
`;

const TabItem = styled.div`
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;

  a, button {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 2px;
    min-height: 44px;
    min-width: 44px;
    width: 100%;
    height: 100%;
    padding: 6px 4px;
    background: none;
    border: none;
    cursor: pointer;
    color: ${({ theme }) => theme.colors.textPrimary};
    text-decoration: none;
    opacity: 0.55;
    transition: opacity 0.15s ease;

    &:hover {
      opacity: 0.85;
    }

    &:focus-visible {
      outline: 2px solid ${({ theme }) => theme.colors.focusRing};
      outline-offset: 2px;
      border-radius: 6px;
    }

    &.active {
      opacity: 1;
      color: ${({ theme }) => paletteAccent(theme.mode ?? 'dark', theme)};
    }
  }
`;

const TabIcon = styled.span`
  font-size: 1.1rem;
  line-height: 1;
`;

const TabLabel = styled.span`
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.6rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  line-height: 1;
`;

interface BottomNavProps {
  onMore: () => void;
  moreOpen?: boolean;
}

export function BottomNav({ onMore, moreOpen = false }: BottomNavProps) {
  return (
    <Bar aria-label="Primary">
      <TabItem>
        <NavLink
          to="/"
          end
          className={({ isActive }) => (isActive ? 'active' : '')}
          aria-label="Today"
        >
          <TabIcon aria-hidden="true">☀</TabIcon>
          <TabLabel>Today</TabLabel>
        </NavLink>
      </TabItem>

      <TabItem>
        <NavLink
          to="/read"
          className={({ isActive }) => (isActive ? 'active' : '')}
          aria-label="Read"
        >
          <TabIcon aria-hidden="true">📰</TabIcon>
          <TabLabel>Read</TabLabel>
        </NavLink>
      </TabItem>

      <TabItem>
        <NavLink
          to="/reflect"
          className={({ isActive }) => (isActive ? 'active' : '')}
          aria-label="Reflect"
        >
          <TabIcon aria-hidden="true">📓</TabIcon>
          <TabLabel>Reflect</TabLabel>
        </NavLink>
      </TabItem>

      <TabItem>
        <button
          type="button"
          onClick={onMore}
          aria-label="More"
          aria-haspopup="dialog"
          aria-expanded={moreOpen}
        >
          <TabIcon aria-hidden="true">⋯</TabIcon>
          <TabLabel>More</TabLabel>
        </button>
      </TabItem>
    </Bar>
  );
}
