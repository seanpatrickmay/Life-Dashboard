// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
import { screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { renderWithProviders } from '../../test/renderWithProviders';
import { PageShell } from './PageShell';

// Stub heavy dependencies so PageShell renders in isolation
vi.mock('./CloudNavShelf', () => ({
  CloudNavShelf: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="cloud-nav-shelf">{children}</div>
  ),
}));

vi.mock('../dashboard/MonetChatPanel', () => ({
  MonetChatBubble: () => null,
}));

vi.mock('./SettingsDrawer', () => ({
  SettingsDrawer: ({ onClose }: { onClose: () => void }) => (
    <div role="dialog" data-testid="settings-drawer">
      <button onClick={onClose}>Close</button>
    </div>
  ),
}));

vi.mock('../../demo/guest/guestMode', () => ({
  isGuestMode: () => false,
  exitGuestMode: vi.fn(),
}));

vi.mock('../../demo/guest/guestStore', () => ({
  clearGuestState: vi.fn(),
}));

// ── Helpers ───────────────────────────────────────────────────────────────────

function renderShell(route = '/') {
  return renderWithProviders(
    <PageShell>
      <div data-testid="page-content">Content</div>
    </PageShell>,
    { route },
  );
}

// ── PageShell nav tests ───────────────────────────────────────────────────────

describe('PageShell primary nav', () => {
  it('renders exactly three nav links: Today, Read, Reflect', () => {
    renderShell('/');
    const nav = screen.getByRole('navigation', { name: /main navigation/i });
    const links = Array.from(nav.querySelectorAll('a'));
    const names = links.map((l) => l.textContent?.trim());
    expect(names).toEqual(['Today', 'Read', 'Reflect']);
  });

  it('does NOT render Insights link in nav', () => {
    renderShell('/');
    const nav = screen.getByRole('navigation', { name: /main navigation/i });
    expect(
      Array.from(nav.querySelectorAll('a')).find((a) =>
        /insights/i.test(a.textContent ?? ''),
      ),
    ).toBeUndefined();
  });

  it('does NOT render Calendar link in nav', () => {
    renderShell('/');
    const nav = screen.getByRole('navigation', { name: /main navigation/i });
    expect(
      Array.from(nav.querySelectorAll('a')).find((a) =>
        /calendar/i.test(a.textContent ?? ''),
      ),
    ).toBeUndefined();
  });

  it('does NOT render Projects link in nav', () => {
    renderShell('/');
    const nav = screen.getByRole('navigation', { name: /main navigation/i });
    expect(
      Array.from(nav.querySelectorAll('a')).find((a) =>
        /projects/i.test(a.textContent ?? ''),
      ),
    ).toBeUndefined();
  });

  it('does NOT render Nutrition link in nav', () => {
    renderShell('/');
    const nav = screen.getByRole('navigation', { name: /main navigation/i });
    expect(
      Array.from(nav.querySelectorAll('a')).find((a) =>
        /nutrition/i.test(a.textContent ?? ''),
      ),
    ).toBeUndefined();
  });

  it('does NOT render User link in nav', () => {
    renderShell('/');
    const nav = screen.getByRole('navigation', { name: /main navigation/i });
    expect(
      Array.from(nav.querySelectorAll('a')).find((a) =>
        /^user$/i.test(a.textContent?.trim() ?? ''),
      ),
    ).toBeUndefined();
  });

  it('renders the Settings gear button', () => {
    renderShell('/');
    expect(screen.getByRole('button', { name: /settings/i })).toBeInTheDocument();
  });

  it('Today link points to /', () => {
    renderShell('/');
    const nav = screen.getByRole('navigation', { name: /main navigation/i });
    const todayLink = Array.from(nav.querySelectorAll('a')).find(
      (a) => a.textContent?.trim() === 'Today',
    );
    expect(todayLink).toHaveAttribute('href', '/');
  });

  it('Read link points to /read', () => {
    renderShell('/');
    const nav = screen.getByRole('navigation', { name: /main navigation/i });
    const readLink = Array.from(nav.querySelectorAll('a')).find(
      (a) => a.textContent?.trim() === 'Read',
    );
    expect(readLink).toHaveAttribute('href', '/read');
  });

  it('Reflect link points to /reflect', () => {
    renderShell('/');
    const nav = screen.getByRole('navigation', { name: /main navigation/i });
    const reflectLink = Array.from(nav.querySelectorAll('a')).find(
      (a) => a.textContent?.trim() === 'Reflect',
    );
    expect(reflectLink).toHaveAttribute('href', '/reflect');
  });

  it('opening Settings drawer shows the drawer', () => {
    renderShell('/');
    fireEvent.click(screen.getByRole('button', { name: /settings/i }));
    expect(screen.getByTestId('settings-drawer')).toBeInTheDocument();
  });
});
