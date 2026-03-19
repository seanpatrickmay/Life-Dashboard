import { css, keyframes } from 'styled-components';

export const fadeUp = keyframes`
  from {
    opacity: 0;
    transform: translateY(18px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
`;

export const reducedMotion = css`
  @media (prefers-reduced-motion: reduce) {
    animation: none !important;
    transition-duration: 0.01ms !important;
  }
`;

export const focusRing = css`
  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.palette?.pond?.['200'] ?? '#7ED7C4'};
    outline-offset: 2px;
  }
`;
