import { useMemo } from 'react';
import styled, { keyframes, css } from 'styled-components';
import { useTheme } from 'styled-components';
import { MonetTheme, resolveFeatureScene } from '../../theme/monetTheme';

type ScatterPoint = {
  id: string;
  x: number;
  y: number;
  size: number;
  sprite: string;
  depth: number;
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

const SceneRoot = styled.div`
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
  z-index: 0;
  image-rendering: pixelated;
`;

const ForegroundOverlay = styled.div`
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 6;
  image-rendering: pixelated;
`;

const BlossomSprite = styled.div`
  position: absolute;
  transform: translate(-50%, -50%);
  background-repeat: no-repeat;
  background-size: contain;
  image-rendering: pixelated;
  filter: drop-shadow(0 6px 12px rgba(0, 0, 0, 0.4));
  z-index: 2;
`;

const WillowOverhang = styled.div<{ side: 'left' | 'right'; sprite: string }>`
  position: absolute;
  top: -10vh;
  ${(p) => (p.side === 'left' ? 'left: -6vw;' : 'right: -6vw;')}
  width: clamp(140px, 20vw, 320px);
  height: 135%;
  background-image: url(${(p) => p.sprite});
  background-repeat: no-repeat;
  background-size: contain;
  opacity: 0.75;
  z-index: 5;
`;

const FloatingBlossom = styled.div<{ sprite: string; glow: string }>`
  position: absolute;
  width: 54px;
  height: 54px;
  opacity: 0.75;
  background-repeat: no-repeat;
  background-size: contain;
  image-rendering: pixelated;
  z-index: 5;
  &:before {
    content: '';
    position: absolute;
    inset: -12px;
    background-image: url(${(p) => p.glow});
    background-repeat: no-repeat;
    background-size: contain;
    opacity: 0.6;
    filter: blur(1px);
  }
  &:after {
    content: '';
    position: absolute;
    inset: 0;
    background-image: url(${(p) => p.sprite});
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
  image?: string;
  blend?: string;
  opacity?: number;
  $animation?: ReturnType<typeof css>;
  $z?: number;
  $repeat?: string;
  $size?: string;
}>`
  position: absolute;
  inset: 0;
  background-image: ${(p) => normalizeImageValue(p.image)};
  background-repeat: ${(p) => p.$repeat ?? 'repeat'};
  background-size: ${(p) => p.$size ?? 'cover'};
  mix-blend-mode: ${(p) => p.blend ?? 'normal'};
  opacity: ${(p) => p.opacity ?? 1};
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
  z-index: 0;
`;

const PadSprite = styled.div<{ size: number; depth: number; sprite: string }>`
  position: absolute;
  width: ${(p) => p.size}px;
  height: ${(p) => p.size}px;
  transform: translate(-50%, -50%);
  background-image: url(${(p) => p.sprite});
  background-repeat: no-repeat;
  background-size: contain;
  image-rendering: pixelated;
  z-index: ${(p) => Math.round(p.depth)};
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
  const mode = (theme.mode ?? 'light') as 'light' | 'dark';
  const moment = theme.moment ?? 'morning';
  const density = theme.sceneDensity ?? (theme.intensity === 'rich' ? 'balanced' : theme.intensity === 'minimal' ? 'sparse' : 'lush');
  const config = densityConfig[density] ?? densityConfig.sparse;
  const horizon = theme.sceneHorizon ?? theme.scene?.horizonByMoment?.[moment] ?? 0.7;
  const waterPalette = theme.scene?.palette ?? (mode === 'dark' ? { waterDeep: '#10224B', waterMid: '#2E4F9A', waterLight: '#5E78C7', warmGlow: '#FFA66E', bloomHighlight: '#E7A2D4', willowLight: '#3F7D62', willowShadow: '#20533E' } : { waterDeep: '#4A69B5', waterMid: '#6E8FD1', waterLight: '#A5BEEB', warmGlow: '#FFBE8C', bloomHighlight: '#F9C7E1', willowLight: '#4A8C6E', willowShadow: '#2E6F57' });

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

  const featureScene = resolveFeatureScene(moment, theme.featureScene ?? 'auto');
  const showFeature = theme.intensity !== 'flat';
  const willowSprites = theme.pixels.willowStrands[mode];

  return (
    <>
      <SceneRoot aria-hidden>
        <BaseLayer
          image={`linear-gradient(180deg, ${waterPalette.waterLight} 0%, ${waterPalette.waterMid} 55%, ${waterPalette.waterDeep} 100%)`}
          opacity={1}
          $z={-3}
        />
        <BaseLayer
          image={theme.pixels.waterBase[mode]}
          opacity={0.45}
          $size="16px 16px"
          $repeat="repeat"
          $z={-2}
        />
        <BaseLayer
          image={theme.pixels.waterReflection[mode]}
          blend="soft-light"
          opacity={mode === 'dark' ? 0.4 : 0.3}
          $z={-1}
        />
        <BaseLayer
          image={theme.pixels.waterStrokes[mode].large}
          blend="screen"
          opacity={0.25}
          style={{ backgroundSize: '320px 160px' }}
          $animation={css`${gentleDrift} 28s linear infinite`}
        />
        <BaseLayer
          image={theme.pixels.waterStrokes[mode].medium}
          blend="screen"
          opacity={0.25}
          style={{ backgroundSize: '220px 120px' }}
          $animation={css`${gentleDrift} 20s linear infinite reverse`}
        />
        <BaseLayer
          image={theme.pixels.waterStrokes[mode].small}
          blend="soft-light"
          opacity={0.25}
          style={{ backgroundSize: '160px 80px' }}
          $animation={css`${gentleDrift} 16s linear infinite`}
        />
        {(moment === 'morning' || moment === 'twilight') && (
          <BaseLayer image={theme.pixels.cloudReflection[mode]} blend="screen" opacity={0.35} />
        )}
        <BaseLayer
          image={theme.pixels.causticRipple[mode]}
          blend="screen"
          opacity={mode === 'dark' ? 0.25 : 0.3}
          style={{ backgroundSize: '200px 200px' }}
          $animation={css`${gentleDrift} 32s linear infinite`}
        />
        <BaseLayer
          image={theme.pixels.sunGlow[mode]}
          blend="screen"
          opacity={0.8}
          style={{
            backgroundRepeat: 'no-repeat',
            backgroundPosition: '55% 28%',
            backgroundSize: 'min(400px, 45vw)'
          }}
        />
        <PadsLayer>
          {pads.map((pad) => (
            <PadSprite
              key={pad.id}
              sprite={pad.sprite}
              size={pad.size}
              depth={pad.depth}
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
        {showFeature && featureScene === 'bridge' && (
          <>
            <FeatureSprite
              style={{
                top: `${Math.max(12, horizon * 100 - 36)}%`,
                width: 'min(900px, 85vw)',
                height: '200px',
                backgroundImage: `url(${theme.pixels.bridgeArc[mode]})`
              }}
            />
            <FeatureSprite
              style={{
                top: `${Math.min(95, horizon * 100 - 6)}%`,
                width: 'min(900px, 85vw)',
                height: '200px',
                backgroundImage: `url(${theme.pixels.bridgeArcReflection[mode]})`,
                opacity: 0.6,
                mixBlendMode: 'soft-light'
              }}
            />
          </>
        )}
        {showFeature && featureScene === 'koi' && (
          <FeatureSprite
            style={{
              top: `${Math.min(95, horizon * 100 + 4)}%`,
              width: '200px',
              height: '120px',
              backgroundImage: `url(${theme.pixels.koi})`
            }}
          />
        )}
        {showFeature && featureScene === 'boat' && (
          <FeatureSprite
            style={{
              top: `${Math.min(90, horizon * 100 - 2)}%`,
              width: '260px',
              height: '180px',
              backgroundImage: `url(${theme.pixels.boat})`
            }}
          />
        )}
        <BaseLayer
          image={mode === 'dark' ? theme.pixels.speckles.dark : theme.pixels.speckles.light}
          blend={mode === 'dark' ? 'screen' : 'soft-light'}
          opacity={mode === 'dark' ? 0.35 : 0.2}
          style={{ backgroundSize: '160px 160px' }}
        />
        <BaseLayer
          image={theme.pixels.vignetteHaze[mode]}
          blend="multiply"
          opacity={mode === 'dark' ? 0.8 : 0.5}
          style={{ backgroundRepeat: 'no-repeat', backgroundSize: 'cover' }}
        />
      </SceneRoot>
      <ForegroundOverlay aria-hidden>
        {theme.willowEnabled !== false && (
          <>
            <WillowOverhang side="left" sprite={willowSprites.left} />
            <WillowOverhang side="right" sprite={willowSprites.right} />
          </>
        )}
        <FloatingBlossom
          sprite={blossomSprites[0]}
          glow={blossomGlow}
          style={{ left: '6%', top: '18%' }}
        />
        <FloatingBlossom
          sprite={blossomSprites[1]}
          glow={blossomGlow}
          style={{ right: '6%', top: '24%' }}
        />
        <FloatingBlossom
          sprite={blossomSprites[2]}
          glow={blossomGlow}
          style={{ left: '8%', bottom: '14%' }}
        />
        <FloatingBlossom
          sprite={blossomSprites[0]}
          glow={blossomGlow}
          style={{ right: '8%', bottom: '12%' }}
        />
      </ForegroundOverlay>
    </>
  );
}
