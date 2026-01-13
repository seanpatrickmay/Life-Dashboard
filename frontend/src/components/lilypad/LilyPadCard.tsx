import { ReactNode } from 'react';
import styled, { css } from 'styled-components';
import { useTheme } from 'styled-components';
import { MonetTheme, getPadTextSpriteForMoment } from '../../theme/monetTheme';
import { Z_LAYERS } from '../../styles/zLayers';

type Side = 'left' | 'right' | 'center';
type PadScale = number;

export type LilyPadCardProps = {
  id?: string;
  side: Side;
  topOffsetPx: number; // distance from bridge-band-bottom
  scale?: PadScale;
  padWidth?: string;
  aspectRatio?: number; // width / height
  contentScale?: number;
  centerShiftPx?: number;
  title: string;
  value?: string; // when absent, show error state
  subtitle?: string; // optional small line under value
  interactive?: boolean;
  children?: ReactNode;
  edgeOffsetPx?: number;
  sideShiftPercent?: number;
  contentWidthPct?: number;
};

const Layer = styled.div`
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: ${Z_LAYERS.lilyPadTextLayer};
`;

const Pad = styled.div<{
  $side: Side;
  $topPx: number;
  $img: string;
  $scale: number;
  $width?: string;
  $aspect?: number;
  $interactive?: boolean;
  $edgeOffset: number;
  $shiftPercent: number;
  $centerShift: number;
}>`
  position: absolute;
  top: calc(var(--bridge-band-bottom, 32vh) + ${(p) => p.$topPx}px);
  ${(p) =>
    p.$side === 'center'
      ? 'left: 50%;'
      : p.$side === 'left'
        ? `left: calc(var(--willow-offset, 6vw) + clamp(12px, 3vw, 60px) + ${p.$edgeOffset}px);`
        : `right: calc(var(--willow-offset, 6vw) + clamp(12px, 3vw, 60px) + ${p.$edgeOffset}px);`}
  width: ${(p) => p.$width ?? 'clamp(560px, 48vw, 960px)'};
  aspect-ratio: ${(p) => p.$aspect ?? 16/6};
  background-image: url(${(p) => p.$img});
  background-repeat: no-repeat;
  background-size: contain;
  background-position: center;
  image-rendering: pixelated;
  transform-origin: ${(p) =>
    p.$side === 'center' ? 'center center' : p.$side === 'left' ? 'left center' : 'right center'};
  ${(p) =>
    css`
      transform: ${p.$side === 'center'
        ? `translateX(calc(-50% + ${p.$centerShift}px)) scale(${p.$scale})`
        : `translateX(${p.$side === 'left' ? '-' : ''}${p.$shiftPercent}%) scale(${p.$scale})`};
    `}
  pointer-events: ${(p) => (p.$interactive ? 'auto' : 'none')};
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0.95;
`;

const PadContent = styled.div<{ $interactive?: boolean; $widthPct: number; $contentScale: number }>`
  text-align: center;
  padding: clamp(10px, 2.2vw, 24px);
  text-shadow: 0 2px 12px rgba(5, 20, 36, 0.75);
  width: 100%;
  max-width: clamp(220px, ${(p) => p.$widthPct * 100}%, 420px);
  color: #ffffff;
  transform: scale(${(p) => p.$contentScale});
  transform-origin: center;
  * {
    color: inherit;
  }
`;

const Title = styled.div`
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: clamp(18px, 2.4vw, 32px);
  letter-spacing: 0.6px;
  color: #ffffff;
  opacity: 0.98;
`;

const Value = styled.div`
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: clamp(22px, 3.2vw, 40px);
  margin-top: 6px;
  color: #ffffff;
`;

const Subtitle = styled.div`
  font-size: clamp(11px, 1.5vw, 14px);
  opacity: 0.85;
  margin-top: 6px;
  color: rgba(255, 255, 255, 0.9);
`;

const ErrorMsg = styled.div`
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: clamp(18px, 3vw, 28px);
  opacity: 0.95;
  color: #ffffff;
`;

export function LilyPadCard({
  id,
  side,
  topOffsetPx,
  scale = 0.88,
  padWidth,
  aspectRatio,
  contentScale = 1,
  centerShiftPx = 0,
  title,
  value,
  subtitle,
  children,
  interactive,
  edgeOffsetPx = 0,
  sideShiftPercent = 22,
  contentWidthPct = 0.58
}: LilyPadCardProps) {
  const theme = useTheme() as MonetTheme;
  const img = getPadTextSpriteForMoment(theme.moment ?? 'noon');
  const showError = !value && !children;
  const widthPct = Math.min(0.92, Math.max(0.36, contentWidthPct));
  return (
    <Layer>
      <Pad
        id={id}
      $side={side}
        $topPx={topOffsetPx}
        $img={img}
        $scale={scale}
        $width={padWidth}
        $aspect={aspectRatio}
        $interactive={interactive}
        $edgeOffset={edgeOffsetPx}
        $shiftPercent={sideShiftPercent}
        $centerShift={centerShiftPx}
      >
        <PadContent $interactive={interactive} $widthPct={widthPct} $contentScale={contentScale}>
          <Title>{title}</Title>
          {children ? (
            children
          ) : showError ? (
            <ErrorMsg>Unavailable — data missing</ErrorMsg>
          ) : (
            <>
              <Value>{value}</Value>
              {subtitle ? <Subtitle>{subtitle}</Subtitle> : null}
            </>
          )}
        </PadContent>
      </Pad>
    </Layer>
  );
}
