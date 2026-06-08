import styled from 'styled-components';

// Pixel text field. Use `<PixelField as="select">` or `as="textarea"` for those inputs.
export const PixelField = styled.input`
  font-family: ${({ theme }) => theme.fonts.body};
  font-size: 15px;
  color: ${({ theme }) => theme.colors.textPrimary};
  background: ${({ theme }) => theme.colors.surfaceInset};
  border: 2px solid ${({ theme }) => theme.colors.borderStrong};
  border-radius: ${({ theme }) => theme.radii.pixel};
  padding: 8px 12px;
  image-rendering: pixelated;
  &::placeholder { color: ${({ theme }) => theme.colors.textSecondary}; }
  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: 1px;
    border-color: ${({ theme }) => theme.colors.accentStrong};
  }
  &:disabled { opacity: 0.5; cursor: not-allowed; }
`;

PixelField.displayName = 'PixelField';
