import { ReactNode } from 'react';
import styled, { keyframes, css } from 'styled-components';
import { getRippleLayer } from '../../theme/monetTheme';
import { SceneComposer } from '../scene/SceneComposer';

const drift = keyframes`
  0% { background-position: 0 0; }
  50% { background-position: 24px 10px; }
  100% { background-position: 0 0; }
`;

const Surface = styled.div`
  position: relative;
  min-height: 100vh;
  width: 100%;
  padding: clamp(16px, 4vw, 40px);
  overflow: hidden;
  background-color: ${({ theme }) => theme.colors.backgroundPage};
  background-image: ${({ theme }) =>
    `linear-gradient(180deg, ${theme.scene?.palette.waterLight ?? '#6E8FD1'} 0%, ${theme.scene?.palette.waterMid ?? '#2E4F9A'} 38%, ${theme.scene?.palette.waterDeep ?? '#10224B'} 100%)`};
  image-rendering: pixelated;

  &::before {
    content: '';
    position: absolute;
    inset: 0;
    ${({ theme }) => {
      const isDark = theme.mode === 'dark';
      const warm = `radial-gradient(circle at 55% 30%, rgba(255, 206, 173, 0.35), transparent 55%)`;
      const cool = `radial-gradient(circle at 40% 20%, rgba(160, 197, 255, 0.4), transparent 60%)`;
      return css`
        background-image: ${isDark ? `${cool}, ${warm}` : `${warm}, ${cool}`};
        opacity: ${isDark ? 0.55 : 0.45};
        mix-blend-mode: ${isDark ? 'screen' : 'multiply'};
      `;
    }}
    pointer-events: none;
    z-index: -2;
  }

  &::after {
    content: '';
    position: absolute;
    inset: 0;
    ${({ theme }) => {
      const ripple = getRippleLayer(theme.mode ?? 'light', theme.moment ?? 'morning', theme.intensity ?? 'rich');
      return css`
        background-image: url(${ripple.image});
        background-size: ${ripple.size};
        background-repeat: ${ripple.repeat};
        background-position: ${ripple.position ?? '0 0'};
        opacity: ${ripple.opacity};
      `;
    }}
    mix-blend-mode: soft-light;
    pointer-events: none;
    z-index: -1;
    animation: ${({ theme }) => (theme.motion ? css`${drift} 18s ease-in-out infinite alternate` : 'none')};
  }
`;

const ContentLayer = styled.div`
  position: relative;
  z-index: 4;
  width: 100%;
  height: 100%;

  & > * {
    position: relative;
    z-index: 1;
  }
`;

type Props = {
  children: ReactNode;
  className?: string;
};

export function PageBackground({ children, className }: Props) {
  return (
    <Surface className={className}>
      <SceneComposer />
      <ContentLayer>{children}</ContentLayer>
    </Surface>
  );
}
