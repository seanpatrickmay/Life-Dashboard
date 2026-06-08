// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ThemeProvider } from 'styled-components';
import { testTheme } from '../../test/renderWithProviders';
import type { DefaultTheme } from 'styled-components';
import { PixelButton } from './PixelButton';

// Minimal theme satisfying pixel tokens (mirrors Card.test.tsx convention)
const pixelTheme: DefaultTheme = {
  ...testTheme,
  fonts: { heading: '"VT323", "Courier New", monospace', body: 'sans-serif' },
  radii: {
    ...(testTheme.radii ?? {}),
    pixel: '6px',
    card: '6px',
    shell: '8px',
  },
  colors: {
    ...testTheme.colors,
    surface: '#FCFAF4',
    borderStrong: '#1E1F2E',
    accentText: '#1E1F2E',
    accentStrong: '#5BB8A4',
    focusRing: '#5BB8A4',
  },
} as unknown as DefaultTheme;

function wrap(ui: React.ReactElement) {
  return render(<ThemeProvider theme={pixelTheme}>{ui}</ThemeProvider>);
}

describe('PixelButton', () => {
  it('renders children and fires onClick', () => {
    const onClick = vi.fn();
    wrap(<PixelButton onClick={onClick}>Go</PixelButton>);
    fireEvent.click(screen.getByRole('button', { name: 'Go' }));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it('supports variant and disabled', () => {
    wrap(<PixelButton variant="ghost" disabled>X</PixelButton>);
    expect(screen.getByRole('button', { name: 'X' })).toBeDisabled();
  });

  it('renders a button element', () => {
    wrap(<PixelButton>Click</PixelButton>);
    expect(screen.getByRole('button', { name: 'Click' })).toBeInTheDocument();
  });

  it('defaults to primary variant without crashing', () => {
    const { container } = wrap(<PixelButton>Primary</PixelButton>);
    expect(container.firstChild?.nodeName).toBe('BUTTON');
  });

  it('supports secondary variant without crashing', () => {
    const { container } = wrap(<PixelButton variant="secondary">Secondary</PixelButton>);
    expect(container.firstChild?.nodeName).toBe('BUTTON');
  });

  it('does not fire onClick when disabled', () => {
    const onClick = vi.fn();
    wrap(<PixelButton disabled onClick={onClick}>Disabled</PixelButton>);
    const btn = screen.getByRole('button', { name: 'Disabled' });
    fireEvent.click(btn);
    expect(onClick).not.toHaveBeenCalled();
  });

  it('forwards arbitrary HTML props (data-testid, type)', () => {
    wrap(<PixelButton data-testid="submit-btn" type="submit">Submit</PixelButton>);
    const btn = screen.getByTestId('submit-btn');
    expect(btn).toBeInTheDocument();
    expect(btn).toHaveAttribute('type', 'submit');
  });
});
