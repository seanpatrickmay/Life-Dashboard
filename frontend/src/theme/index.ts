import { colors } from './colors';

export const theme = {
  colors,
  fonts: {
    heading: '"Press Start 2P", cursive',
    body: '"Inter", sans-serif'
  },
  shadows: {
    soft: '0 10px 40px rgba(31, 42, 68, 0.15)'
  }
} as const;

export type Theme = typeof theme;
