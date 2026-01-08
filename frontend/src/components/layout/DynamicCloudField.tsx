import { useMemo } from 'react';
import styled, { keyframes } from 'styled-components';
import type { Moment } from '../../theme/monetTheme';
import { getCloudSpritesForMoment } from '../../theme/monetTheme';
import { Z_LAYERS } from '../../styles/zLayers';

const drift = keyframes`
  0% { transform: translateX(120vw); }
  100% { transform: translateX(-140vw); }
`;

const Field = styled.div`
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 360px; /* static cloud band height to sit above the horizon */
  pointer-events: none;
  overflow: visible;
  z-index: ${Z_LAYERS.clouds};
`;

const CloudSprite = styled.img<{
  $top: number;
  $width: number;
  $duration: number;
  $delay: number;
  $opacity: number;
  $z: number;
}>`
  position: absolute;
  top: ${(p) => `${p.$top}px`};
  left: 0;
  width: ${(p) => `${p.$width}px`};
  height: auto;
  pointer-events: none;
  z-index: ${(p) => p.$z};
  filter: drop-shadow(0 10px 24px rgba(15, 30, 69, 0.25));
  animation: ${drift} ${(p) => p.$duration}s linear infinite;
  animation-delay: ${(p) => `-${p.$delay}s`};
  opacity: ${(p) => p.$opacity};
`;

type LayerKey = 'back' | 'mid' | 'front';

type CloudConfig = {
  count: number;
  topRange: [number, number];
  widthRange: [number, number];
  durationRange: [number, number];
  delayRange: [number, number];
  opacityRange: [number, number];
  z: number;
};

const LAYER_CONFIG: Record<LayerKey, CloudConfig> = {
  back: {
    count: 22,
    topRange: [0, 40],
    widthRange: [140, 220],
    durationRange: [180, 260],
    delayRange: [0, 200],
    opacityRange: [0.7, 0.98],
    z: 1
  },
  mid: {
    count: 24,
    topRange: [20, 60],
    widthRange: [160, 240],
    durationRange: [220, 340],
    delayRange: [0, 200],
    opacityRange: [0.75, 0.98],
    z: 2
  },
  front: {
    count: 16,
    topRange: [40, 80],
    widthRange: [180, 260],
    durationRange: [260, 380],
    delayRange: [0, 200],
    opacityRange: [0.75, 0.98],
    z: 3
  }
};

type Props = {
  moment: Moment;
};

type CloudInstance = {
  id: string;
  layer: LayerKey;
  img: string;
  top: number;
  width: number;
  duration: number;
  delay: number;
  opacity: number;
  z: number;
};

const randInRange = (min: number, max: number) => min + Math.random() * (max - min);

export function DynamicCloudField({ moment }: Props) {
  const sprites = getCloudSpritesForMoment(moment);

  const clouds = useMemo<CloudInstance[]>(() => {
    const result: CloudInstance[] = [];
    (['back', 'mid', 'front'] as LayerKey[]).forEach((layer) => {
      const config = LAYER_CONFIG[layer];
      const images = sprites[layer];
      if (!images || !images.length) return;
      for (let i = 0; i < config.count; i += 1) {
        const img = images[i % images.length];
        result.push({
          id: `${layer}-${i}-${moment}`,
          layer,
          img,
          top: randInRange(...config.topRange),
          width: randInRange(...config.widthRange),
          duration: randInRange(...config.durationRange),
          delay: randInRange(...config.delayRange),
          opacity: randInRange(...config.opacityRange),
          z: config.z
        });
      }
    });
    return result;
  }, [moment, sprites]);

  return (
    <Field aria-hidden>
      {clouds.map((cloud) => (
        <CloudSprite
          key={cloud.id}
          src={cloud.img}
          alt="cloud"
          $top={cloud.top}
          $width={cloud.width}
          $duration={cloud.duration}
          $delay={cloud.delay}
          $opacity={cloud.opacity}
          $z={cloud.z}
        />
      ))}
    </Field>
  );
}
