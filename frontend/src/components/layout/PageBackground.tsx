import React, { ReactNode, useLayoutEffect, useRef } from 'react';
import styled, { keyframes, css, useTheme } from 'styled-components';
import { getRippleLayer, MonetTheme } from '../../theme/monetTheme';
import { SceneComposer } from '../scene/SceneComposer';
import { SceneForegroundProvider } from '../scene/SceneForegroundContext';
import { DynamicCloudField } from './DynamicCloudField';
import { Z_LAYERS } from '../../styles/zLayers';

const drift = keyframes`
  0% { background-position: 0 0; }
  50% { background-position: 24px 10px; }
  100% { background-position: 0 0; }
`;

const Surface = styled.div.attrs({ 'data-scene-surface': 'true' })`
  position: relative;
  min-height: 100vh;
  width: 100%;
  padding: clamp(16px, 4vw, 40px);
  overflow-x: hidden;
  overflow-y: auto;
  background-color: ${({ theme }) => theme.colors.backgroundPage};
  background-image: ${({ theme }) => {
    const palette = theme.scene?.palette ?? {};
    const mode = theme.mode ?? 'light';
    const moment = theme.moment ?? 'noon';

    // Sky palette per mode/moment
    const SKY_COLORS: Record<string, { top: string; mid: string }> = {
      'light-morning': { top: '#bde1ff', mid: '#8fc2ff' },
      'light-noon': { top: '#a6d4ff', mid: '#78b4ff' },
      'light-twilight': { top: '#d6b8ff', mid: '#8ba2ff' },
      'light-night': { top: '#5f7fb8', mid: '#4a65a3' },
      'dark-morning': { top: '#9cc6ff', mid: '#6fa8ff' },
      'dark-noon': { top: '#85b7ff', mid: '#4f8aff' },
      'dark-twilight': { top: '#b48cff', mid: '#6a7be0' },
      'dark-night': { top: '#3d4f7d', mid: '#2c3c69' }
    };

    const skyKey = `${mode}-${moment}`;
    const skyChoice = SKY_COLORS[skyKey] ?? SKY_COLORS['light-noon'];

    const skyTop = palette.skyTop ?? skyChoice.top;
    const skyMid = palette.skyMid ?? skyChoice.mid;
    const horizon = palette.horizon ?? palette.waterLight ?? '#5E78C7';
    const waterMid = palette.waterMid ?? '#2E4F9A';
    const waterDeep = palette.waterDeep ?? '#10224B';
    const bandColor =
      mode === 'dark'
        ? moment === 'night'
          ? 'rgba(100,126,170,0.35)'
          : 'rgba(212,223,255,0.32)'
        : 'rgba(255,255,255,0.28)';

    const skyLayer = `linear-gradient(
      180deg,
      ${skyTop} 0px,
      ${skyMid} calc(var(--scene-horizon, 200px) - 120px),
      ${horizon} calc(var(--scene-horizon, 200px))
    )`;

    const waterLayer = `linear-gradient(
      180deg,
      ${horizon} calc(var(--scene-horizon, 200px) - 2px),
      ${waterMid} calc(var(--scene-horizon, 200px) + 12px),
      ${waterDeep} 100%
    )`;

    const horizonBand = `linear-gradient(
      180deg,
      transparent calc(var(--scene-horizon, 200px) - 20px),
      ${bandColor} calc(var(--scene-horizon, 200px) - 6px),
      ${bandColor} calc(var(--scene-horizon, 200px) + 6px),
      transparent calc(var(--scene-horizon, 200px) + 26px)
    )`;

    return `${horizonBand}, ${waterLayer}, ${skyLayer}`;
  }};
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
    z-index: ${Z_LAYERS.gradient};
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
    z-index: ${Z_LAYERS.waterRipple};
    animation: ${({ theme }) => (theme.motion ? css`${drift} 18s ease-in-out infinite alternate` : 'none')};
    mask-image: linear-gradient(
      180deg,
      transparent calc(var(--scene-horizon, 200px) - 14px),
      transparent calc(var(--scene-horizon, 200px) - 2px),
      white calc(var(--scene-horizon, 200px) + 2px),
      white 100%
    );
    mask-mode: alpha;
    -webkit-mask-image: linear-gradient(
      180deg,
      transparent calc(var(--scene-horizon, 200px) - 14px),
      transparent calc(var(--scene-horizon, 200px) - 2px),
      white calc(var(--scene-horizon, 200px) + 2px),
      white 100%
    );
    -webkit-mask-mode: alpha;
  }
`;

const ContentLayer = styled.div`
  position: relative;
  z-index: ${Z_LAYERS.uiCards};
  width: 100%;
  height: 100%;

  &::before {
    content: '';
    position: absolute;
    left: clamp(6%, 9vw, 16%);
    right: clamp(6%, 9vw, 16%);
    top: clamp(80px, 10vh, 160px);
    height: clamp(220px, 32vh, 420px);
    background: radial-gradient(
        ellipse at 50% 0%,
        rgba(214, 230, 255, 0.32) 0%,
        rgba(214, 230, 255, 0.14) 48%,
        transparent 72%
      ),
      linear-gradient(
        180deg,
        rgba(120, 150, 210, 0.24) 0%,
        transparent 70%
      );
    opacity: ${({ theme }) => (theme.mode === 'dark' ? 0.75 : 0.55)};
    filter: blur(2px);
    pointer-events: none;
    z-index: 0;
  }

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
  const surfaceRef = useRef<HTMLDivElement>(null);
  const theme = useTheme() as MonetTheme;
  const moment = theme.moment ?? 'morning';
  const NAV_OFFSET = 360; // px below nav for horizon baseline (just under cloud band)
  useLayoutEffect(() => {
    const update = () => {
      const root = surfaceRef.current;
      if (!root) return;
      const rootRect = root.getBoundingClientRect();
      const willowOffsetPx = Math.max(32, rootRect.width * 0.08);
      root.style.setProperty('--willow-offset', `${willowOffsetPx}px`);
      const horizon = NAV_OFFSET; // px below nav (static anchor)
      root.style.setProperty('--scene-horizon', `${horizon}px`);
      root.style.setProperty('--bridge-band-bottom', `${horizon}px`);
      root.style.setProperty('--bridge-top', `${Math.max(0, horizon - 220)}px`);
      root.style.setProperty('--hero-top', '0px');
      root.style.setProperty('--hero-right', '0px');
      root.style.setProperty('--hero-left', '0px');
      document.documentElement.style.setProperty('--scene-horizon', `${horizon}px`);
      document.documentElement.style.setProperty('--bridge-band-bottom', `${horizon}px`);
    };
    update();
    const obs = new ResizeObserver(update);
    if (surfaceRef.current) obs.observe(surfaceRef.current);
    const onResize = () => update();
    window.addEventListener('resize', onResize);
    return () => {
      window.removeEventListener('resize', onResize);
      obs.disconnect();
    };
  }, []);

  return (
    <Surface className={className} ref={surfaceRef}>
      <DynamicCloudField moment={moment} />
      <SceneForegroundProvider>
        <SceneComposer showStructure={false} />
        <ContentLayer>{children}</ContentLayer>
      </SceneForegroundProvider>
    </Surface>
  );
}
