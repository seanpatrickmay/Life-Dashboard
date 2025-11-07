import { createGlobalStyle } from 'styled-components';

export const GlobalStyle = createGlobalStyle`

  :root {
    --pixel-border: ${({ theme }) => theme.colors.borderSubtle};
    --pixel-grid: ${({ theme }) => theme.colors.grid};
    --text-primary: ${({ theme }) => theme.colors.textPrimary};
    --text-secondary: ${({ theme }) => theme.colors.textSecondary};
    color-scheme: ${({ theme }) => (theme.mode === 'dark' ? 'dark' : 'light')};
  }

  * {
    box-sizing: border-box;
  }

  body {
    margin: 0;
    min-height: 100vh;
    font-family: ${({ theme }) => theme.fonts.body};
    color: var(--text-primary);
    background-color: ${({ theme }) => theme.colors.backgroundPage};
    background-attachment: fixed;
    image-rendering: pixelated;
    transition: background-color 0.4s ease, color 0.2s ease;
  }

  #root {
    min-height: 100vh;
  }

  h1, h2, h3, h4, nav, .heading-font {
    font-family: ${({ theme }) => theme.fonts.heading};
    letter-spacing: 0.5px;
    text-transform: uppercase;
  }

  button, input, select, textarea {
    font-family: ${({ theme }) => theme.fonts.body};
  }

  button {
    appearance: none;
    border: 2px solid ${({ theme }) => theme.colors.borderSubtle};
    border-radius: 10px;
    padding: 10px 14px;
    color: ${({ theme }) => theme.colors.textPrimary};
    background: ${({ theme }) => theme.colors.backgroundCard};
    box-shadow: ${({ theme }) => theme.shadows.pixel};
    image-rendering: pixelated;
    cursor: pointer;
  }

  button:active {
    transform: translateY(1px);
    box-shadow: 0 0 0 2px rgba(23, 20, 33, 0.08) inset;
  }

  input, select, textarea {
    appearance: none;
    border: 2px solid ${({ theme }) => theme.colors.borderSubtle};
    border-radius: 10px;
    padding: 10px 12px;
    background: ${({ theme }) => theme.colors.backgroundCard};
    color: ${({ theme }) => theme.colors.textPrimary};
    box-shadow: inset 0 0 0 2px rgba(23,20,33,0.06);
  }

  ::selection {
    background: rgba(255, 192, 117, 0.5);
    color: ${({ theme }) => (theme.mode === 'dark' ? '#171421' : '#1E1F2E')};
  }

  /* Accessibility: reduce motion */
  @media (prefers-reduced-motion: reduce) {
    * { transition-duration: 0s !important; animation: none !important; }
  }

  /* Accessibility: high contrast mode flattens textures */
  @media (prefers-contrast: more) {
    .flatten-textures {
      background-image: none !important;
      backdrop-filter: none !important;
    }
  }
`;
