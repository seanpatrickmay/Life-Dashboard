import { css } from 'styled-components';

// Top-level pixel card: solid fill, thick ink border, hard offset shadow, squarer corners.
export const pixelPanel = css`
  background: ${({ theme }) => theme.colors.surface};
  border: 2px solid ${({ theme }) => theme.colors.borderStrong};
  border-radius: ${({ theme }) => theme.radii.pixel};
  box-shadow: ${({ theme }) => (theme.mode === 'dark' ? theme.shadows.pixelDark : theme.shadows.pixel)};
  image-rendering: pixelated;
`;

// Nested well / inset row: keeps hierarchy FLAT — no shadow, hairline border.
export const pixelWell = css`
  background: ${({ theme }) => theme.colors.surfaceInset};
  border: 1px solid ${({ theme }) => theme.colors.borderSoft};
  border-radius: ${({ theme }) => theme.radii.pixel};
`;
