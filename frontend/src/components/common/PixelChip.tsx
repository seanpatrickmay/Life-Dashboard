import React from 'react';
import styled from 'styled-components';

const ChipBase = styled.button<{ $active?: boolean }>`
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 14px;
  letter-spacing: 0.03em;
  padding: 4px 10px;
  border-radius: 4px;
  border: 2px solid ${({ theme }) => theme.colors.borderStrong};
  image-rendering: pixelated;
  cursor: pointer;
  background: ${({ theme, $active }) => ($active ? theme.colors.accent : theme.colors.surface)};
  color: ${({ theme, $active }) => ($active ? theme.colors.accentText : theme.colors.textPrimary)};
  &:focus-visible { outline: 2px solid ${({ theme }) => theme.colors.focusRing}; outline-offset: 2px; }
  &:disabled { opacity: 0.5; cursor: not-allowed; }
`;

export type PixelChipProps = React.ComponentPropsWithoutRef<'button'> & { active?: boolean };

export const PixelChip = React.forwardRef<HTMLButtonElement, PixelChipProps>(
  ({ active = false, ...rest }, ref) => (
    <ChipBase ref={ref} $active={active} aria-pressed={active} {...rest} />
  )
);
PixelChip.displayName = 'PixelChip';
