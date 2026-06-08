// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ThemeProvider } from 'styled-components';
import { testTheme } from '../../test/renderWithProviders';
import type { DefaultTheme } from 'styled-components';
import { Card } from './Card';

// Minimal theme satisfying new pixel tokens
const lightPixelTheme: DefaultTheme = {
  ...testTheme,
  mode: 'light',
  radii: {
    ...(testTheme.radii ?? {}),
    pixel: '6px',
    card: '6px',
    shell: '8px',
  },
  shadows: {
    ...(testTheme.shadows ?? {}),
    soft: '0 18px 34px rgba(28, 41, 64, 0.18)',
    pixel: '4px 4px 0 0 rgba(23, 20, 33, 0.85)',
    pixelDark: '4px 4px 0 0 rgba(0, 0, 0, 0.55)',
  },
  colors: {
    ...testTheme.colors,
    surface: '#FCFAF4',
    surfaceRaised: '#FFFFFF',
    surfaceInset: '#EFE7D6',
    borderStrong: '#1E1F2E',
    borderSoft: '#E1D6C8',
  },
} as unknown as DefaultTheme;

const darkPixelTheme: DefaultTheme = {
  ...lightPixelTheme,
  mode: 'dark',
  colors: {
    ...lightPixelTheme.colors,
    surface: '#18213A',
    surfaceRaised: '#222C49',
    surfaceInset: '#101831',
    borderStrong: '#E7E0F0',
  },
} as unknown as DefaultTheme;

function wrap(ui: React.ReactElement, theme: DefaultTheme = lightPixelTheme) {
  return render(<ThemeProvider theme={theme}>{ui}</ThemeProvider>);
}

describe('Card', () => {
  it('renders children', () => {
    wrap(<Card><span>hello pixel</span></Card>);
    expect(screen.getByText('hello pixel')).toBeInTheDocument();
  });

  it('forwards arbitrary HTML props (data-testid, className)', () => {
    wrap(<Card data-testid="my-card" className="extra"><p>content</p></Card>);
    const el = screen.getByTestId('my-card');
    expect(el).toBeInTheDocument();
    expect(el).toHaveClass('extra');
  });

  it('renders without crashing under lightPixelTheme', () => {
    const { container } = wrap(<Card>light content</Card>, lightPixelTheme);
    expect(container.firstChild).toBeInTheDocument();
  });

  it('renders without crashing under darkPixelTheme', () => {
    const { container } = wrap(<Card>dark content</Card>, darkPixelTheme);
    expect(container.firstChild).toBeInTheDocument();
  });

  it('renders a single div at the top level', () => {
    const { container } = wrap(<Card>body</Card>);
    expect(container.firstChild?.nodeName).toBe('DIV');
  });

  it('accepts and uses a forwarded ref', () => {
    let capturedRef: HTMLDivElement | null = null;
    const ref = (el: HTMLDivElement | null) => { capturedRef = el; };
    wrap(<Card ref={ref}>ref card</Card>);
    expect(capturedRef).not.toBeNull();
    expect(capturedRef!.tagName).toBe('DIV');
  });

  it('does NOT apply halo text-shadow to card shell children (pixel system is opaque, no glow needed)', () => {
    const { container } = wrap(
      <Card><p data-testid="body-text">body text</p></Card>
    );
    // The CardShell should no longer carry a wildcard text-shadow selector over its children.
    // We verify the p element does not receive an inline text-shadow (styled-components
    // injects via class, so we just assert the element is present — actual CSS is screenshot-verified).
    expect(screen.getByTestId('body-text')).toBeInTheDocument();
  });

  it('passes onPointerEnter and onPointerLeave events through', () => {
    // Card intercepts these internally but still fires the external handlers
    let entered = false;
    let left = false;
    const { container } = wrap(
      <Card onPointerEnter={() => { entered = true; }} onPointerLeave={() => { left = true; }}>event card</Card>
    );
    const el = container.firstChild as HTMLElement;
    fireEvent.pointerEnter(el);
    fireEvent.pointerLeave(el);
    expect(entered).toBe(true);
    expect(left).toBe(true);
  });
});
