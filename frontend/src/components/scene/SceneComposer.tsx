import { useMemo, useRef, useState, useCallback, useLayoutEffect } from 'react';
import styled, { keyframes, css } from 'styled-components';
import { useTheme } from 'styled-components';
import { MonetTheme } from '../../theme/monetTheme';
import { useSceneForeground } from './SceneForegroundContext';
import { Z_LAYERS } from '../../styles/zLayers';

type ScatterPoint = {
  id: string;
  x: number;
  y: number;
  size: number;
  sprite: string;
  depth: number;
};

type OrbitMetrics = {
  cx: number;
  cy: number;
  rx: number;
  ry: number;
  size: number;
};

type ScatterConfig = {
  pads: number;
  blossoms: number;
  minDist: number;
};

const densityConfig: Record<string, ScatterConfig> = {
  sparse: { pads: 12, blossoms: 5, minDist: 7.5 },
  balanced: { pads: 18, blossoms: 7, minDist: 6 },
  lush: { pads: 24, blossoms: 9, minDist: 5 }
};

const MOMENT_HOURS: Record<string, number> = {
  morning: 8,
  noon: 12,
  twilight: 18,
  night: 0
};

const hourFromMoment = (moment?: string): number =>
  MOMENT_HOURS[moment ?? 'noon'] ?? 12;

const computeOrbitGeometry = (overlayEl: HTMLDivElement | null): OrbitMetrics | null => {
  if (typeof window === 'undefined' || !overlayEl) return null;
  const surfaceEl = overlayEl.parentElement as HTMLElement | null;
  if (!surfaceEl) return null;
  const surfaceStyles = getComputedStyle(surfaceEl);
  const docStyles = getComputedStyle(document.documentElement);
  const widthPx = surfaceEl.clientWidth || window.innerWidth || 0;
  if (widthPx <= 0) return null;
  const willowRaw = surfaceStyles.getPropertyValue('--willow-offset');
  const willowOffset = willowRaw ? parseFloat(willowRaw) || 0 : Math.max(32, widthPx * 0.06);
  const leftRootX = willowOffset;
  const rightRootX = widthPx - willowOffset;
  const arcWidth = Math.max(0, rightRootX - leftRootX);
  const bridgeTopRaw = surfaceStyles.getPropertyValue('--bridge-top');
  const bridgeTopPx = parseFloat(bridgeTopRaw || '0') || 0;
  const arRaw =
    overlayEl.style.getPropertyValue('--bridge-ar') ||
    docStyles.getPropertyValue('--bridge-ar') ||
    '6';
  const bridgeAR = Number.parseFloat(arRaw) || 6;
  const arcHeight = arcWidth / Math.max(bridgeAR, 0.1);
  const rx = (arcWidth / 2) * 0.85;
  const ellipseHeight = Math.max(arcHeight * 0.55, 140);
  const ry = ellipseHeight / 2;
  const cx = leftRootX + rx + arcWidth * 0.05;
  let cy = bridgeTopPx + ry;
  cy -= Math.min(ry * 0.15, 40);
  const size = Math.min(400, widthPx * 0.3);
  return { cx, cy, rx, ry, size };
};

const useOrbitMetrics = (overlayRef: React.RefObject<HTMLDivElement>) => {
  const [orbit, setOrbit] = useState<OrbitMetrics | null>(null);

  const recompute = useCallback(() => {
    if (typeof window === 'undefined') return;
    const metrics = computeOrbitGeometry(overlayRef.current);
    if (metrics) {
      setOrbit(metrics);
    }
  }, [overlayRef]);

  useLayoutEffect(() => {
    recompute();
    window.addEventListener('resize', recompute);
    return () => {
      window.removeEventListener('resize', recompute);
    };
  }, [recompute]);

  return { orbit, recompute };
};

const SceneRoot = styled.div`
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
  image-rendering: pixelated;
`;

const ForegroundOverlay = styled.div`
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: ${Z_LAYERS.willows};
  image-rendering: pixelated;
`;

const MidgroundOverlay = styled.div`
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: ${Z_LAYERS.bridge};
`;

const BoatOverlay = styled.div`
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: ${Z_LAYERS.boat};
`;

const BoatReflectionOverlay = styled.div`
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: ${Z_LAYERS.boatReflection};
`;


const BlossomSprite = styled.div`
  position: absolute;
  transform: translate(-50%, -50%);
  background-repeat: no-repeat;
  background-size: contain;
  image-rendering: pixelated;
  filter: drop-shadow(0 6px 12px rgba(0, 0, 0, 0.16));
  z-index: ${Z_LAYERS.blossoms};
`;

const WillowOverhang = styled.div<{ $side: 'left' | 'right'; $sprite: string }>`
  position: absolute;
  top: -10vh;
  ${(p) => (p.$side === 'left' ? 'left: -6vw;' : 'right: -6vw;')}
  width: clamp(140px, 20vw, 320px);
  height: 135%;
  background-image: url(${(p) => p.$sprite});
  background-repeat: no-repeat;
  background-size: contain;
  opacity: 0.75;
  transition: opacity 0.3s ease;
  &[data-dimmed='true'] {
    opacity: 0.45;
  }
  z-index: 5;
`;

const FloatingBlossom = styled.div<{ $sprite: string; $glow: string }>`
  position: absolute;
  width: 54px;
  height: 54px;
  opacity: 0.75;
  background-repeat: no-repeat;
  background-size: contain;
  image-rendering: pixelated;
  z-index: 5;
  transition: opacity 0.3s ease;
  &[data-dimmed='true'] {
    opacity: 0.45;
  }
  &:before {
    content: '';
    position: absolute;
    inset: -12px;
    background-image: url(${(p) => p.$glow});
    background-repeat: no-repeat;
    background-size: contain;
    opacity: 0.6;
    filter: blur(1px);
  }
  &:after {
    content: '';
    position: absolute;
    inset: 0;
    background-image: url(${(p) => p.$sprite});
    background-repeat: no-repeat;
    background-size: contain;
  }
`;

const gentleDrift = keyframes`
  0% { background-position: 0 0; }
  50% { background-position: 60px 20px; }
  100% { background-position: 0 0; }
`;

const slowParallax = keyframes`
  0% { transform: translate3d(-50%, -50%, 0) scale(1); }
  50% { transform: translate3d(-48%, -49%, 0) scale(1.04); }
  100% { transform: translate3d(-50%, -50%, 0) scale(1); }
`;

const normalizeImageValue = (val?: string) => {
  if (!val) return 'none';
  const trimmed = val.trim();
  if (
    trimmed.startsWith('url(') ||
    trimmed.startsWith('linear-gradient(') ||
    trimmed.startsWith('radial-gradient(') ||
    trimmed.startsWith('conic-gradient(')
  ) {
    return trimmed;
  }
  return `url(${trimmed})`;
};

const BaseLayer = styled.div<{
  $image?: string;
  $blend?: string;
  $opacity?: number;
  $animation?: ReturnType<typeof css>;
  $z?: number;
  $repeat?: string;
  $size?: string;
}>`
  position: absolute;
  inset: 0;
  background-image: ${(p) => normalizeImageValue(p.$image)};
  background-repeat: ${(p) => p.$repeat ?? 'repeat'};
  background-size: ${(p) => p.$size ?? 'cover'};
  mix-blend-mode: ${(p) => p.$blend ?? 'normal'};
  opacity: ${(p) => p.$opacity ?? 1};
  pointer-events: none;
  z-index: ${(p) => p.$z ?? 0};
  ${(p) =>
    p.$animation &&
    css`
      animation: ${p.$animation};
    `}
`;

const PadsLayer = styled.div`
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: ${Z_LAYERS.lilyPadTextLayer};
`;

const PadSprite = styled.div<{ $size: number; $depth: number; $sprite: string }>`
  position: absolute;
  width: ${(p) => p.$size}px;
  height: ${(p) => p.$size}px;
  transform: translate(-50%, -50%);
  background-image: url(${(p) => p.$sprite});
  background-repeat: no-repeat;
  background-size: contain;
  image-rendering: pixelated;
  z-index: ${Z_LAYERS.lilyPads};
  animation: ${slowParallax} 14s ease-in-out infinite;
`;

const FeatureSprite = styled.div`
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  background-repeat: no-repeat;
  background-size: contain;
  image-rendering: pixelated;
  pointer-events: none;
`;

const FullWidthSprite = styled.div`
  position: absolute;
  left: var(--willow-offset, 6vw);
  width: calc(100vw - (2 * var(--willow-offset, 6vw)));
  /* Use a sane default AR for reflection (e.g., 1200x200 => 6.0). */
  height: calc((100vw - (2 * var(--willow-offset, 6vw))) / var(--bridge-ar, 6));
  background-repeat: no-repeat;
  /* Fill width, preserve intrinsic aspect ratio (no vertical squashing). */
  background-size: 100% auto;
  background-position: center top;
  image-rendering: pixelated;
  pointer-events: none;
`;

const FullWidthImage = styled.img`
  position: absolute;
  left: var(--willow-offset, 6vw);
  top: var(--bridge-top, 22vh);
  width: calc(100vw - (2 * var(--willow-offset, 6vw)));
  height: auto;
  image-rendering: pixelated;
  pointer-events: none;
  z-index: ${Z_LAYERS.bridge};
`;

const BoatImage = styled.img`
  position: absolute;
  right: var(--willow-offset, 6vw);
  bottom: 16vh;
  width: min(36vw, 720px);
  height: auto;
  image-rendering: pixelated;
  pointer-events: none;
  opacity: 0.95;
`;

const BoatReflectionImage = styled.img`
  position: absolute;
  right: var(--willow-offset, 6vw);
  /* Bring reflection closer to the hull to avoid floating look */
  bottom: 13vh;
  width: min(36vw, 720px);
  height: auto;
  image-rendering: pixelated;
  pointer-events: none;
  opacity: 0.45;
  mix-blend-mode: soft-light;
`;

// Boat drift keyframes and wrappers
const boatDriftLeft = keyframes`
  0% { transform: translateX(110vw); }
  100% { transform: translateX(-30vw); }
`;

const boatDriftRight = keyframes`
  0% { transform: translateX(-30vw); }
  100% { transform: translateX(110vw); }
`;

const AnimatedTrack = styled.div<{ $dir: 'left' | 'right'; $duration: number; $bottomVh: number }>`
  position: absolute;
  left: 0;
  bottom: ${(p) => p.$bottomVh}vh;
  width: 100vw;
  height: 0;
  pointer-events: none;
  image-rendering: pixelated;
  will-change: transform;
  z-index: ${Z_LAYERS.boat};
  animation: ${(p) =>
    p.$dir === 'left'
      ? css`${boatDriftLeft} ${p.$duration}s ease-in-out 1`
      : css`${boatDriftRight} ${p.$duration}s ease-in-out 1`};
`;

const BoatSprite = styled.img<{ $scale?: number; $flip?: boolean }>`
  position: absolute;
  left: 0;
  bottom: 0;
  width: min(36vw, 720px);
  height: auto;
  image-rendering: pixelated;
  pointer-events: none;
  opacity: 0.95;
  transform-origin: center bottom;
  ${(p) => css`
    transform: ${p.$flip ? 'scaleX(-1) ' : ''}scale(${p.$scale ?? 1});
  `}
`;

const BoatReflectionSprite = styled.img<{ $scale?: number; $flip?: boolean }>`
  position: absolute;
  left: 0;
  bottom: 0;
  width: min(36vw, 720px);
  height: auto;
  image-rendering: pixelated;
  pointer-events: none;
  opacity: 0.45;
  mix-blend-mode: soft-light;
  transform-origin: center top;
  ${(p) => css`
    transform: ${p.$flip ? 'scaleX(-1) ' : ''}scale(${p.$scale ?? 1});
  `}
`;

// Gentle bob/yaw wrappers
const boatBob = keyframes`
  0% { transform: translateY(0px) rotate(0deg); }
  25% { transform: translateY(-12px) rotate(-2.2deg); }
  50% { transform: translateY(0px) rotate(1.8deg); }
  75% { transform: translateY(12px) rotate(0deg); }
  100% { transform: translateY(0px) rotate(-1.6deg); }
`;

const boatBobReflection = keyframes`
  0% { transform: translateY(0px) rotate(0deg); }
  25% { transform: translateY(-6px) rotate(-1.1deg); }
  50% { transform: translateY(0px) rotate(0.8deg); }
  75% { transform: translateY(6px) rotate(0deg); }
  100% { transform: translateY(0px) rotate(-0.7deg); }
`;

const BoatBob = styled.div`
  position: relative;
  will-change: transform;
  animation: ${boatBob} 33s ease-in-out infinite;
  transform-origin: center bottom;
`;

const BoatBobReflection = styled.div`
  position: relative;
  will-change: transform;
  animation: ${boatBobReflection} 30s ease-in-out infinite;
  transform-origin: center top;
`;

// Ripple shimmer under reflection
const shimmerFlow = keyframes`
  0% { background-position: 0 0; opacity: 0.2; }
  50% { background-position: -180px 0; opacity: 0.28; }
  100% { background-position: -360px 0; opacity: 0.2; }
`;

const RippleShimmer = styled.div<{ $img: string; $scale?: number; $flip?: boolean }>`
  position: absolute;
  left: 0;
  /* push further below the reflection base */
  bottom: -10px;
  width: min(36vw, 720px);
  height: 22px;
  background-image: url(${(p) => p.$img});
  background-repeat: repeat-x;
  background-size: 120px 22px;
  image-rendering: pixelated;
  mix-blend-mode: screen;
  filter: blur(0.4px);
  pointer-events: none;
  z-index: 0;
  animation: ${shimmerFlow} 12s linear infinite;
  transform-origin: center top;
  ${(p) => css`
    transform: ${p.$flip ? 'scaleX(-1) ' : ''}scale(${p.$scale ?? 1});
  `}
`;

function hashSeed(input: string) {
  let h = 1779033703 ^ input.length;
  for (let i = 0; i < input.length; i += 1) {
    h = Math.imul(h ^ input.charCodeAt(i), 3432918353);
    h = (h << 13) | (h >>> 19);
  }
  return () => {
    h = Math.imul(h ^ (h >>> 16), 2246822507);
    h = Math.imul(h ^ (h >>> 13), 3266489909);
    const t = (h ^= h >>> 16) >>> 0;
    return t / 4294967296;
  };
}

function scatterPoints(config: ScatterConfig, region: { x: number; y: number; width: number; height: number }, seed: string) {
  const rng = hashSeed(seed);
  const pts: ScatterPoint[] = [];
  const minDist = config.minDist;
  let attempts = 0;
  const maxAttempts = config.pads * 60;
  while (pts.length < config.pads && attempts < maxAttempts) {
    const x = region.x + rng() * region.width;
    const y = region.y + rng() * region.height;
    if (y > 100 || y < 45) {
      attempts += 1;
      continue;
    }
    const ok = pts.every((p) => {
      const dx = p.x - x;
      const dy = p.y - y;
      const dist = Math.sqrt(dx * dx + dy * dy);
      return dist >= minDist;
    });
    if (ok) {
      const size = 24 + rng() * 22;
      pts.push({
        id: `pad-${pts.length}`,
        x,
        y,
        size,
        sprite: '',
        depth: y
      });
    }
    attempts += 1;
  }
  return pts;
}

export function SceneComposer() {
  const theme = useTheme() as MonetTheme;
  const overlayRef = useRef<HTMLDivElement>(null);
  const { orbit, recompute: recomputeOrbit } = useOrbitMetrics(overlayRef);
  const foreground = useSceneForeground();
  const registerSprite = useCallback(
    (id: string) => (el: HTMLElement | null) => {
      foreground?.registerSprite(id, el);
    },
    [foreground]
  );
  const mode = (theme.mode ?? 'light') as 'light' | 'dark';
  const moment = theme.moment ?? 'morning';
  const density = theme.sceneDensity ?? (theme.intensity === 'rich' ? 'balanced' : theme.intensity === 'minimal' ? 'sparse' : 'lush');
  const config = densityConfig[density] ?? densityConfig.sparse;
  const horizon = theme.sceneHorizon ?? theme.scene?.horizonByMoment?.[moment] ?? 0.7;
  const waterPalette = theme.scene?.palette ?? (mode === 'dark' ? { waterDeep: '#10224B', waterMid: '#2E4F9A', waterLight: '#5E78C7', warmGlow: '#FFA66E', bloomHighlight: '#E7A2D4', willowLight: '#3F7D62', willowShadow: '#20533E' } : { waterDeep: '#4A69B5', waterMid: '#6E8FD1', waterLight: '#A5BEEB', warmGlow: '#FFBE8C', bloomHighlight: '#F9C7E1', willowLight: '#4A8C6E', willowShadow: '#2E6F57' });

  // Boat drift state
  const [boatDir, setBoatDir] = useState<'left' | 'right'>('left');
  const [boatKey, setBoatKey] = useState(0);

  const padSprites = theme.pixels.padSmall[mode];
  const padRing = theme.pixels.padRing[mode];
  const blossomSprites = theme.pixels.blossomSmall[mode];
  const blossomGlow = theme.pixels.blossomGlow[mode];

  const scatterRegion = {
    x: 6,
    width: 88,
    y: Math.max(55, horizon * 100 - 4),
    height: Math.max(18, 100 - horizon * 100 + 12)
  };

  const pads = useMemo(() => {
    const raw = scatterPoints(config, scatterRegion, `${mode}-${moment}-${density}`);
    const rng = hashSeed(`pads-${mode}-${moment}-${density}`);
    return raw.map((pad, index) => {
      const sprite = index % 5 === 0 ? padRing : padSprites[index % padSprites.length];
      const sizeJitter = pad.size * (0.85 + rng() * 0.3);
      return { ...pad, sprite, size: sizeJitter };
    });
  }, [config, scatterRegion.height, scatterRegion.width, scatterRegion.x, scatterRegion.y, density, mode, moment, padRing, padSprites]);

  const blossoms = useMemo(() => {
    if (!pads.length) return [];
    const rng = hashSeed(`blossoms-${mode}-${moment}-${density}`);
    const picks = [...pads];
    picks.sort(() => rng() - 0.5);
    const selected = picks.slice(0, Math.min(config.blossoms, pads.length));
    return selected.map((pad, index) => ({
      id: `blossom-${pad.id}-${index}`,
      x: pad.x + (rng() - 0.5) * 2,
      y: pad.y - 1.5,
      sprite: blossomSprites[index % blossomSprites.length],
      size: 20 + rng() * 12
    }));
  }, [pads, config.blossoms, mode, moment, density, blossomSprites]);

  const showFeature = theme.intensity !== 'flat';
  const willowSprites = theme.pixels.willowStrands[mode];

  const buildBoatTracks = () => {
    const maxBottomVh = Math.max(6, (100 - horizon * 100) - 8);
    const low = 12;
    const ceiling = Math.max(0, maxBottomVh - 2);
    const high = Math.min(ceiling, low + 30);
    const bottomVh = boatDir === 'left' ? low : high;
    const scale = boatDir === 'left' ? 1.0 : 0.6;
    const flip = boatDir === 'left';
    const duration = 30;
    if (typeof window !== 'undefined') {
      const vhPx = window.innerHeight / 100;
      const laneBottomPx = bottomVh * vhPx;
      const spriteHeightPx = 140 * scale;
      const laneTopPx = Math.max(0, window.innerHeight - laneBottomPx - spriteHeightPx);
      document.documentElement.style.setProperty('--boat-lane-top', `${laneTopPx}`);
      document.documentElement.style.setProperty('--boat-lane-bottom', `${laneTopPx + spriteHeightPx}`);
    }
    const handleEnd = () => {
      const nextDir = boatDir === 'left' ? 'right' : 'left';
      setBoatDir(nextDir);
      setBoatKey((k) => k + 1);
    };
    const boatTrack = (
      <AnimatedTrack
        key={`boat-${boatKey}`}
        $dir={boatDir}
        $duration={duration}
        $bottomVh={bottomVh}
        onAnimationEnd={handleEnd}
      >
        <BoatBob>
          <BoatSprite src={theme.pixels.boatFull[mode]} alt="Boat" $scale={scale} $flip={flip} />
        </BoatBob>
      </AnimatedTrack>
    );
    const reflectionTrack = (
      <AnimatedTrack
        key={`boat-ref-${boatKey}`}
        $dir={boatDir}
        $duration={duration}
        $bottomVh={Math.max(0, bottomVh - 8)}
      >
        <BoatBobReflection>
          <BoatReflectionSprite src={theme.pixels.boatReflection[mode]} alt="Boat Reflection" $scale={scale} $flip={flip} />
          <RippleShimmer $img={theme.pixels.causticRipple[mode]} $scale={scale} $flip={flip} />
        </BoatBobReflection>
      </AnimatedTrack>
    );
    return { boatTrack, reflectionTrack };
  };

  const { boatTrack, reflectionTrack } = buildBoatTracks();

  return (
    <>
      <SceneRoot aria-hidden>
        <BaseLayer
          $image={`linear-gradient(180deg, ${waterPalette.waterLight} 0%, ${waterPalette.waterMid} 55%, ${waterPalette.waterDeep} 100%)`}
          $opacity={1}
          $z={-3}
        />
        <BaseLayer
          $image={theme.pixels.waterBase[mode]}
          $opacity={0.45}
          $size="16px 16px"
          $repeat="repeat"
          $z={-2}
        />
        <BaseLayer
          $image={theme.pixels.waterReflection[mode]}
          $blend="soft-light"
          $opacity={mode === 'dark' ? 0.4 : 0.3}
          $z={-1}
        />
        <BaseLayer
          $image={theme.pixels.waterStrokes[mode].large}
          $blend="screen"
          $opacity={0.25}
          style={{ backgroundSize: '320px 160px' }}
          $animation={css`${gentleDrift} 28s linear infinite`}
        />
        <BaseLayer
          $image={theme.pixels.waterStrokes[mode].medium}
          $blend="screen"
          $opacity={0.25}
          style={{ backgroundSize: '220px 120px' }}
          $animation={css`${gentleDrift} 20s linear infinite reverse`}
        />
        <BaseLayer
          $image={theme.pixels.waterStrokes[mode].small}
          $blend="soft-light"
          $opacity={0.25}
          style={{ backgroundSize: '160px 80px' }}
          $animation={css`${gentleDrift} 16s linear infinite`}
        />
        {(() => {
          // Subtle sky reflection varies by moment
          let opacity = 0.28;
          let blend: string = 'screen';
          switch (moment) {
            case 'morning':
              opacity = 0.32; blend = 'screen'; break;
            case 'noon':
              opacity = 0.22; blend = 'overlay'; break;
            case 'twilight':
              opacity = 0.36; blend = 'screen'; break;
            case 'night':
              opacity = 0.26; blend = 'screen'; break;
          }
          return (
            <BaseLayer
              $image={theme.pixels.cloudReflection[mode]}
              $blend={blend}
              $opacity={opacity}
            />
          );
        })()}
        <BaseLayer
          $image={theme.pixels.causticRipple[mode]}
          $blend="screen"
          $opacity={mode === 'dark' ? 0.25 : 0.3}
          style={{ backgroundSize: '200px 200px' }}
          $animation={css`${gentleDrift} 32s linear infinite`}
        />
        {/* Sun moved to foreground (behind bridge) below */}
        <PadsLayer>
          {pads.map((pad) => (
            <PadSprite
              key={pad.id}
              $sprite={pad.sprite}
              $size={pad.size}
              $depth={pad.depth}
              style={{ left: `${pad.x}%`, top: `${pad.y}%` }}
            />
          ))}
          {blossoms.map((blossom) => (
            <BlossomSprite
              key={blossom.id}
              style={{
                left: `${blossom.x}%`,
                top: `${blossom.y}%`,
                width: `${blossom.size}px`,
                height: `${blossom.size}px`,
                backgroundImage: `url(${blossom.sprite})`
              }}
            />
          ))}
        </PadsLayer>
        <div
          style={{
            position: 'absolute',
            left: 0,
            right: 0,
            bottom: '-5%',
            height: '32%',
            backgroundImage: `url(${theme.pixels.reedsEdge[mode]})`,
            backgroundRepeat: 'repeat-x',
            backgroundSize: 'contain',
            opacity: 0.45
          }}
        />
        {/* Feature sprites (koi/boat) removed per design: bridge + boat always on midground overlay */}
        <BaseLayer
          $image={mode === 'dark' ? theme.pixels.speckles.dark : theme.pixels.speckles.light}
          $blend={mode === 'dark' ? 'screen' : 'soft-light'}
          $opacity={mode === 'dark' ? 0.35 : 0.2}
          style={{ backgroundSize: '160px 160px' }}
        />
        <BaseLayer
          $image={theme.pixels.vignetteHaze[mode]}
          $blend="multiply"
          $opacity={mode === 'dark' ? 0.8 : 0.5}
          style={{ backgroundRepeat: 'no-repeat', backgroundSize: 'cover' }}
        />
      </SceneRoot>
      <MidgroundOverlay aria-hidden ref={overlayRef}>
        {/* Sun/Moon orbital path behind the bridge */}
        {orbit && (() => {
          const hour = theme.sceneHour ?? hourFromMoment(theme.moment ?? 'noon');
          const sunAngle = (18 - hour) * (Math.PI / 12);
          const moonAngle = (18 - (hour + 12)) * (Math.PI / 12);
          const sunX = orbit.cx + orbit.rx * Math.cos(sunAngle);
          const sunY = orbit.cy - orbit.ry * Math.sin(sunAngle);
          const moonX = orbit.cx + orbit.rx * Math.cos(moonAngle);
          const moonY = orbit.cy - orbit.ry * Math.sin(moonAngle);

          const showSun = !(hour >= 19 || hour < 5);
          const showMoon = !(hour >= 7 && hour < 17);
          const isSunAbove = Math.sin(sunAngle) > -0.2;
          const isMoonAbove = Math.sin(moonAngle) > -0.2;
          const sunOpacity = showSun ? 1 : 0;
          const moonOpacity = showMoon ? 1 : 0;
          const variant: 'light' | 'dark' = 'light';

          return (
            <>
              {showSun && (
                <div
                  style={{
                    position: 'absolute',
                    left: `${sunX - orbit.size / 2}px`,
                    top: `${sunY - orbit.size / 2}px`,
                    width: `${orbit.size}px`,
                    height: `${orbit.size}px`,
                    backgroundImage: `url(${theme.pixels.sunGlow[variant]})`,
                    backgroundRepeat: 'no-repeat',
                    backgroundPosition: 'center',
                    backgroundSize: 'contain',
                    opacity: sunOpacity,
                    mixBlendMode: 'screen',
                    zIndex: 2
                  }}
                />
              )}
              {showMoon && (
                <div
                  style={{
                    position: 'absolute',
                    left: `${moonX - orbit.size / 2}px`,
                    top: `${moonY - orbit.size / 2}px`,
                    width: `${orbit.size * 0.86}px`,
                    height: `${orbit.size * 0.86}px`,
                    backgroundImage: `url(${theme.pixels.moonGlow[variant]})`,
                    backgroundRepeat: 'no-repeat',
                    backgroundPosition: 'center',
                    backgroundSize: 'contain',
                    opacity: moonOpacity,
                    mixBlendMode: 'screen',
                    zIndex: 2
                  }}
                />
              )}
            </>
          );
        })()}

        {/* Bridge always present spanning between willows */}
            <FullWidthImage
              src={theme.pixels.bridgeArc[mode]}
              alt="Bridge"
              onLoad={(e) => {
                const img = e.currentTarget;
                const ar = img.naturalWidth / Math.max(1, img.naturalHeight);
                overlayRef.current?.style.setProperty('--bridge-ar', `${ar}`);
                document.documentElement.style.setProperty('--bridge-ar', `${ar}`);
                recomputeOrbit();
              }}
            />
            <FullWidthImage
              src={theme.pixels.bridgeArcReflection[mode]}
              alt="Bridge Reflection"
          style={{
            top: `calc(var(--bridge-top, 22vh) + (calc(100vw - (2 * var(--willow-offset, 6vw))) / var(--bridge-ar, 6)))`,
            opacity: 0.45,
            zIndex: Z_LAYERS.bridgeReflection
          }}
              onLoad={(e) => {
                const img = e.currentTarget;
                const ar = img.naturalWidth / Math.max(1, img.naturalHeight);
                overlayRef.current?.style.setProperty('--bridge-ref-ar', `${ar}`);
                document.documentElement.style.setProperty('--bridge-ref-ar', `${ar}`);
                recomputeOrbit();
              }}
            />
      </MidgroundOverlay>
      <BoatReflectionOverlay aria-hidden>{reflectionTrack}</BoatReflectionOverlay>
      <BoatOverlay aria-hidden>{boatTrack}</BoatOverlay>
      <ForegroundOverlay aria-hidden>
        {theme.willowEnabled !== false && (
          <>
            <WillowOverhang ref={registerSprite('willow-left')} $side="left" $sprite={willowSprites.left} />
            <WillowOverhang ref={registerSprite('willow-right')} $side="right" $sprite={willowSprites.right} />
          </>
        )}
        {/* Restore corner blossoms */}
        <FloatingBlossom
          ref={registerSprite('corner-blossom-1')}
          $sprite={blossomSprites[0]}
          $glow={blossomGlow}
          style={{ left: '6%', top: '18%' }}
        />
        <FloatingBlossom
          ref={registerSprite('corner-blossom-2')}
          $sprite={blossomSprites[1]}
          $glow={blossomGlow}
          style={{ right: '6%', top: '24%' }}
        />
        <FloatingBlossom
          ref={registerSprite('corner-blossom-3')}
          $sprite={blossomSprites[2]}
          $glow={blossomGlow}
          style={{ left: '8%', bottom: '14%' }}
        />
        <FloatingBlossom
          ref={registerSprite('corner-blossom-4')}
          $sprite={blossomSprites[0]}
          $glow={blossomGlow}
          style={{ right: '8%', bottom: '12%' }}
        />
      </ForegroundOverlay>
    </>
  );
}
