import React, { forwardRef, useCallback, useRef } from 'react';
import styled from 'styled-components';
import { useSceneForeground } from '../scene/SceneForegroundContext';
import { Z_LAYERS } from '../../styles/zLayers';

const defaultHeadingHalo = '0 0 2px rgba(65,201,211,0.80), 0 0 8px rgba(125,215,196,0.45), 0 10px 24px rgba(17,122,158,0.20)';
const defaultBodyHalo = '0 0 2px rgba(201,243,246,0.75), 0 0 6px rgba(126,215,196,0.28)';

const CardShell = styled.div`
  position: relative;
  z-index: ${Z_LAYERS.uiCards};
  background: ${({ theme }) =>
    theme.mode === 'dark' ? 'rgba(20, 28, 46, 0.72)' : 'rgba(255, 255, 255, 0.82)'};
  color: ${({ theme }) => theme.colors.textPrimary};
  padding: clamp(18px, 2vw, 26px);
  image-rendering: pixelated;
  border: 1px solid
    ${({ theme }) =>
      theme.mode === 'dark' ? 'rgba(246, 240, 232, 0.24)' : 'rgba(30, 31, 46, 0.18)'};
  border-radius: ${({ theme }) => theme.radii?.card ?? '16px'};
  pointer-events: auto;
  box-shadow: 0 16px 36px rgba(8, 14, 28, 0.35);

  &, p, span, label, small, li, strong, em, div {
    text-shadow: ${({ theme }) => theme.tokens?.halo?.body ?? defaultBodyHalo};
  }

  h1, h2, h3, h4, h5, h6, [data-halo='heading'] {
    text-shadow: ${({ theme }) => theme.tokens?.halo?.heading ?? defaultHeadingHalo};
  }

  [data-halo='body'] {
    text-shadow: ${({ theme }) => theme.tokens?.halo?.body ?? defaultBodyHalo};
  }

  &::before {
    content: '';
    position: absolute;
    left: 10%;
    right: 10%;
    bottom: -26px;
    height: 56px;
    background: radial-gradient(circle, rgba(15, 30, 69, 0.25) 0%, transparent 70%);
    filter: blur(18px);
    opacity: 0.35;
    z-index: ${Z_LAYERS.gradient};
  }
`;

type CardProps = React.ComponentPropsWithoutRef<'div'>;

export const Card = forwardRef<HTMLDivElement, CardProps>(({ onPointerEnter, onPointerLeave, ...rest }, ref) => {
  const fg = useSceneForeground();
  const localRef = useRef<HTMLDivElement | null>(null);

  const combinedRef = useCallback(
    (node: HTMLDivElement | null) => {
      localRef.current = node;
      if (typeof ref === 'function') ref(node);
      else if (ref) (ref as React.MutableRefObject<HTMLDivElement | null>).current = node;
    },
    [ref]
  );

  const handleEnter = (event: React.PointerEvent<HTMLDivElement>) => {
    if (localRef.current && fg) {
      fg.dimSprites(localRef.current.getBoundingClientRect());
    }
    onPointerEnter?.(event);
  };

  const handleLeave = (event: React.PointerEvent<HTMLDivElement>) => {
    fg?.clearDims();
    onPointerLeave?.(event);
  };

  return <CardShell ref={combinedRef} onPointerEnter={handleEnter} onPointerLeave={handleLeave} {...rest} />;
});

Card.displayName = 'Card';
