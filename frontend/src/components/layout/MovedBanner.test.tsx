// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
import { screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, beforeEach } from 'vitest';
import { renderWithProviders } from '../../test/renderWithProviders';
import { MovedBanner } from './MovedBanner';

const FLAG = 'ld_nav_moved_dismissed';

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('MovedBanner', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('renders when the dismissed flag is absent', () => {
    renderWithProviders(<MovedBanner />);
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('does NOT render when the dismissed flag is set', () => {
    localStorage.setItem(FLAG, '1');
    renderWithProviders(<MovedBanner />);
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });

  it('contains the dismiss button with aria-label', () => {
    renderWithProviders(<MovedBanner />);
    expect(screen.getByRole('button', { name: /dismiss/i })).toBeInTheDocument();
  });

  it('clicking dismiss hides the banner', () => {
    renderWithProviders(<MovedBanner />);
    fireEvent.click(screen.getByRole('button', { name: /dismiss/i }));
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });

  it('clicking dismiss persists the flag to localStorage', () => {
    renderWithProviders(<MovedBanner />);
    fireEvent.click(screen.getByRole('button', { name: /dismiss/i }));
    expect(localStorage.getItem(FLAG)).toBe('1');
  });

  it('mentions the three primary tabs in the copy', () => {
    renderWithProviders(<MovedBanner />);
    const alert = screen.getByRole('status');
    expect(alert.textContent).toMatch(/today/i);
    expect(alert.textContent).toMatch(/read/i);
    expect(alert.textContent).toMatch(/reflect/i);
  });

  it('mentions the settings gear in the copy', () => {
    renderWithProviders(<MovedBanner />);
    const alert = screen.getByRole('status');
    // Should mention settings or ⚙ somewhere
    expect(alert.textContent).toMatch(/settings|⚙/i);
  });
});
