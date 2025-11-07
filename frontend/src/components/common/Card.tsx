import styled, { css } from 'styled-components';
import { composeLayers, getCardLayers } from '../../theme/monetTheme';

export const Card = styled.div`
  position: relative;
  z-index: 1;
  background-color: transparent;
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
  border-radius: ${({ theme }) => theme.radii?.card ?? '16px'};
  border: none;
  box-shadow: 0 18px 38px rgba(4, 8, 14, 0.18);
  color: ${({ theme }) => theme.colors.textPrimary};
  *, *::before, *::after {
    text-shadow: ${({ theme }) =>
      theme.mode === 'dark'
        ? '0 0 2px rgba(0,0,0,0.9), 0 0 6px rgba(0,0,0,0.5)'
        : '0 0 2px rgba(255,255,255,0.9), 0 0 6px rgba(255,255,255,0.5)'};
  }
  padding: clamp(20px, 2.4vw, 28px);
  image-rendering: pixelated;
  backdrop-filter: blur(16px) saturate(120%);
  overflow: visible;
  transition: box-shadow 0.3s ease, transform 0.3s ease;

  &::before {
    content: '';
    position: absolute;
    left: 15%;
    right: 15%;
    bottom: -28px;
    height: 52px;
    background: radial-gradient(circle, rgba(0, 0, 0, 0.35) 0%, transparent 70%);
    opacity: 0.55;
    filter: blur(20px);
    z-index: -1;
  }

  &::after {
    display: none;
  }
`;
