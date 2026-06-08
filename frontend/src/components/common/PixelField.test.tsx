// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ThemeProvider } from 'styled-components';
import { testTheme } from '../../test/renderWithProviders';
import type { DefaultTheme } from 'styled-components';
import React, { useState } from 'react';
import { PixelField } from './PixelField';
import { PixelChip } from './PixelChip';

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
    surfaceInset: '#EFE7D6',
    borderStrong: '#1E1F2E',
    accentText: '#1E1F2E',
    accentStrong: '#5BB8A4',
    focusRing: '#5BB8A4',
    accent: '#7ED7C4',
  },
} as unknown as DefaultTheme;

function wrap(ui: React.ReactElement) {
  return render(<ThemeProvider theme={pixelTheme}>{ui}</ThemeProvider>);
}

// Small controlled wrapper for testing PixelField value updates
function ControlledField(props: React.ComponentPropsWithoutRef<'input'>) {
  const [value, setValue] = useState('');
  return (
    <PixelField
      {...props}
      value={value}
      onChange={(e) => setValue(e.target.value)}
    />
  );
}

describe('PixelField', () => {
  it('renders as an input element', () => {
    wrap(<PixelField aria-label="search" />);
    expect(screen.getByRole('textbox', { name: 'search' })).toBeInTheDocument();
    expect(screen.getByRole('textbox', { name: 'search' }).tagName).toBe('INPUT');
  });

  it('forwards aria-label correctly', () => {
    wrap(<PixelField aria-label="my field" />);
    const input = screen.getByRole('textbox', { name: 'my field' });
    expect(input).toHaveAttribute('aria-label', 'my field');
  });

  it('updates a controlled value on change', () => {
    wrap(<ControlledField aria-label="controlled" />);
    const input = screen.getByRole('textbox', { name: 'controlled' });
    expect(input).toHaveValue('');
    fireEvent.change(input, { target: { value: 'hello' } });
    expect(input).toHaveValue('hello');
  });
});

describe('PixelChip', () => {
  it('renders children', () => {
    wrap(<PixelChip>Tech</PixelChip>);
    expect(screen.getByRole('button', { name: 'Tech' })).toBeInTheDocument();
  });

  it('defaults aria-pressed to false', () => {
    wrap(<PixelChip>Tag</PixelChip>);
    expect(screen.getByRole('button', { name: 'Tag' })).toHaveAttribute('aria-pressed', 'false');
  });

  it('sets aria-pressed to true when active', () => {
    wrap(<PixelChip active>Active Tag</PixelChip>);
    expect(screen.getByRole('button', { name: 'Active Tag' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('fires onClick when clicked', () => {
    const onClick = vi.fn();
    wrap(<PixelChip onClick={onClick}>Click me</PixelChip>);
    fireEvent.click(screen.getByRole('button', { name: 'Click me' }));
    expect(onClick).toHaveBeenCalledOnce();
  });
});
