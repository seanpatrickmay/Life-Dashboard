import React, { forwardRef, useCallback, useRef } from 'react';
import styled from 'styled-components';
import { useSceneForeground } from '../scene/SceneForegroundContext';
import { Z_LAYERS } from '../../styles/zLayers';

const CardShell = styled.div`
  position: relative;
  z-index: ${Z_LAYERS.uiCards};
  background: ${({ theme }) => theme.colors.surface ?? theme.colors.backgroundCard};
  color: ${({ theme }) => theme.colors.textPrimary};
  padding: clamp(18px, 2vw, 26px);
  image-rendering: pixelated;
  border: 2px solid ${({ theme }) => theme.colors.borderStrong ?? theme.colors.borderSubtle};
  border-radius: ${({ theme }) => theme.radii?.pixel ?? theme.radii?.card ?? '6px'};
  pointer-events: auto;
  box-shadow: ${({ theme }) =>
    theme.mode === 'dark'
      ? (theme.shadows?.pixelDark ?? '4px 4px 0 0 rgba(0,0,0,0.55)')
      : (theme.shadows?.pixel ?? '4px 4px 0 0 rgba(23,20,33,0.85)')};

  @media (prefers-reduced-motion: no-preference) {
    transition: transform 120ms ease, box-shadow 120ms ease;

    &:hover {
      transform: translate(-1px, -1px);
      box-shadow: ${({ theme }) =>
        theme.mode === 'dark'
          ? '6px 6px 0 0 rgba(0,0,0,0.55)'
          : '6px 6px 0 0 rgba(23,20,33,0.85)'};
    }
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
