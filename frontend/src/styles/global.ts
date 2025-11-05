import { createGlobalStyle } from 'styled-components';

export const GlobalStyle = createGlobalStyle`
  :root {
    color-scheme: light;
    background: ${({ theme }) => theme.colors.mistWhite};
  }

  * {
    box-sizing: border-box;
  }

  body {
    margin: 0;
    font-family: ${({ theme }) => theme.fonts.body};
    background: radial-gradient(circle at top left, rgba(126, 200, 227, 0.5), transparent),
      radial-gradient(circle at bottom right, rgba(156, 208, 161, 0.5), transparent),
      ${({ theme }) => theme.colors.mistWhite};
    min-height: 100vh;
    color: ${({ theme }) => theme.colors.nightNavy};
  }

  #root {
    min-height: 100vh;
  }

  h1, h2, h3, h4 {
    font-family: ${({ theme }) => theme.fonts.heading};
    letter-spacing: 1px;
  }
`;
