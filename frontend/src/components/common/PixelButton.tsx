import styled, { css } from 'styled-components';

export type PixelButtonVariant = 'primary' | 'secondary' | 'ghost';

const variants = {
  primary: css`
    background: ${({ theme }) => theme.colors.accent};
    color: ${({ theme }) => theme.colors.accentText};
    border: 2px solid ${({ theme }) => theme.colors.borderStrong};
    box-shadow: 3px 3px 0 0 ${({ theme }) => theme.colors.borderStrong};
  `,
  secondary: css`
    background: ${({ theme }) => theme.colors.surface ?? theme.colors.backgroundCard};
    color: ${({ theme }) => theme.colors.textPrimary};
    border: 2px solid ${({ theme }) => theme.colors.borderStrong};
    box-shadow: 3px 3px 0 0 ${({ theme }) => theme.colors.borderStrong};
  `,
  ghost: css`
    background: transparent;
    color: ${({ theme }) => theme.colors.textPrimary};
    border: 2px solid transparent;
    box-shadow: none;
    text-decoration: underline transparent;
    &:hover:not(:disabled) {
      text-decoration-color: currentColor;
    }
  `,
};

export const PixelButton = styled.button<{ variant?: PixelButtonVariant }>`
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 18px;
  letter-spacing: 0.04em;
  padding: 8px 16px;
  border-radius: ${({ theme }) => theme.radii?.pixel ?? '6px'};
  image-rendering: pixelated;
  cursor: pointer;
  transition: none;

  ${({ variant = 'primary' }) => variants[variant]}

  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: 2px;
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    box-shadow: none;
    pointer-events: none;
  }

  @media (prefers-reduced-motion: no-preference) {
    transition: transform 80ms ease-out, box-shadow 80ms ease-out;
    &:not(:disabled):active {
      transform: translate(3px, 3px);
      box-shadow: 0 0 0 0 transparent;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    &:not(:disabled):active {
      filter: brightness(0.92);
    }
  }
`;

PixelButton.displayName = 'PixelButton';
