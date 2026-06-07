// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
import { screen, fireEvent, within } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { renderWithProviders } from '../../test/renderWithProviders';
import { PageShell } from './PageShell';
import { BottomNav } from './BottomNav';
import { MoreSheet } from './MoreSheet';

// ── Mock heavy PageShell deps ─────────────────────────────────────────────────

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

// ── matchMedia stub helpers ───────────────────────────────────────────────────

function stubMatchMedia(mobileMatches: boolean) {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    configurable: true,
    value: (query: string) => ({
      matches: mobileMatches,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
    }),
  });
}

function renderShell(route = '/') {
  return renderWithProviders(
    <PageShell>
      <div data-testid="page-content">Content</div>
    </PageShell>,
    { route },
  );
}

// ── PageShell responsive split ────────────────────────────────────────────────

describe('PageShell responsive nav split', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  describe('mobile (≤640px)', () => {
    beforeEach(() => stubMatchMedia(true));

    it('renders BottomNav with Primary aria-label', () => {
      renderShell('/');
      expect(screen.getByRole('navigation', { name: /primary/i })).toBeInTheDocument();
    });

    it('BottomNav contains Today, Read, Reflect, More', () => {
      renderShell('/');
      const bottomNav = screen.getByRole('navigation', { name: /primary/i });
      expect(within(bottomNav).getByRole('link', { name: /today/i })).toBeInTheDocument();
      expect(within(bottomNav).getByRole('link', { name: /read/i })).toBeInTheDocument();
      expect(within(bottomNav).getByRole('link', { name: /reflect/i })).toBeInTheDocument();
      expect(within(bottomNav).getByRole('button', { name: /more/i })).toBeInTheDocument();
    });

    it('does NOT render the desktop CloudNavShelf top strip', () => {
      renderShell('/');
      expect(screen.queryByTestId('cloud-nav-shelf')).not.toBeInTheDocument();
    });

    it('clicking More opens the MoreSheet dialog', () => {
      renderShell('/');
      const moreBtn = screen.getByRole('button', { name: /more/i });
      fireEvent.click(moreBtn);
      expect(screen.getByRole('dialog', { name: /more/i })).toBeInTheDocument();
    });

    it('MoreSheet lists Body, Calendar, Projects, Settings', () => {
      renderShell('/');
      fireEvent.click(screen.getByRole('button', { name: /more/i }));

      const dialog = screen.getByRole('dialog', { name: /more/i });
      expect(within(dialog).getByRole('link', { name: /body/i })).toBeInTheDocument();
      expect(within(dialog).getByRole('link', { name: /calendar/i })).toBeInTheDocument();
      expect(within(dialog).getByRole('link', { name: /projects/i })).toBeInTheDocument();
      expect(within(dialog).getByRole('button', { name: /settings/i })).toBeInTheDocument();
    });

    it('MoreSheet → Settings opens SettingsDrawer and closes MoreSheet', () => {
      renderShell('/');
      fireEvent.click(screen.getByRole('button', { name: /more/i }));
      fireEvent.click(screen.getByRole('button', { name: /settings/i }));

      // MoreSheet should be gone
      expect(screen.queryByRole('dialog', { name: /more/i })).not.toBeInTheDocument();
      // SettingsDrawer should be open
      expect(screen.getByTestId('settings-drawer')).toBeInTheDocument();
    });

    it('Escape closes the MoreSheet', () => {
      renderShell('/');
      fireEvent.click(screen.getByRole('button', { name: /more/i }));
      expect(screen.getByRole('dialog', { name: /more/i })).toBeInTheDocument();

      fireEvent.keyDown(document, { key: 'Escape' });
      expect(screen.queryByRole('dialog', { name: /more/i })).not.toBeInTheDocument();
    });

    it('backdrop click closes the MoreSheet', () => {
      renderShell('/');
      fireEvent.click(screen.getByRole('button', { name: /more/i }));
      const backdrop = screen.getByTestId('more-sheet-backdrop');
      fireEvent.click(backdrop);
      expect(screen.queryByRole('dialog', { name: /more/i })).not.toBeInTheDocument();
    });

    it('route change closes an open MoreSheet', () => {
      renderShell('/');
      // Open the MoreSheet
      fireEvent.click(screen.getByRole('button', { name: /more/i }));
      expect(screen.getByRole('dialog', { name: /more/i })).toBeInTheDocument();
      // Navigate by clicking one of the sheet's links (Body → /body)
      // This triggers MemoryRouter to update pathname, causing PageShell's
      // useEffect([pathname]) to fire setMoreOpen(false)
      fireEvent.click(screen.getByRole('link', { name: /body/i }));
      expect(screen.queryByRole('dialog', { name: /more/i })).not.toBeInTheDocument();
    });
  });

  describe('desktop (>640px)', () => {
    beforeEach(() => stubMatchMedia(false));

    it('renders the desktop CloudNavShelf top strip', () => {
      renderShell('/');
      expect(screen.getByTestId('cloud-nav-shelf')).toBeInTheDocument();
    });

    it('does NOT render BottomNav', () => {
      renderShell('/');
      expect(screen.queryByRole('navigation', { name: /primary/i })).not.toBeInTheDocument();
    });

    it('still renders the Main navigation nav inside CloudNavShelf', () => {
      renderShell('/');
      expect(screen.getByRole('navigation', { name: /main navigation/i })).toBeInTheDocument();
    });
  });
});

// ── BottomNav unit tests ──────────────────────────────────────────────────────

describe('BottomNav', () => {
  beforeEach(() => stubMatchMedia(true));

  it('Today NavLink points to /', () => {
    renderWithProviders(<BottomNav onMore={vi.fn()} />, { route: '/' });
    const link = screen.getByRole('link', { name: /today/i });
    expect(link).toHaveAttribute('href', '/');
  });

  it('Read NavLink points to /read', () => {
    renderWithProviders(<BottomNav onMore={vi.fn()} />, { route: '/' });
    const link = screen.getByRole('link', { name: /read/i });
    expect(link).toHaveAttribute('href', '/read');
  });

  it('Reflect NavLink points to /reflect', () => {
    renderWithProviders(<BottomNav onMore={vi.fn()} />, { route: '/' });
    const link = screen.getByRole('link', { name: /reflect/i });
    expect(link).toHaveAttribute('href', '/reflect');
  });

  it('More button has aria-haspopup="dialog"', () => {
    renderWithProviders(<BottomNav onMore={vi.fn()} />, { route: '/' });
    const btn = screen.getByRole('button', { name: /more/i });
    expect(btn).toHaveAttribute('aria-haspopup', 'dialog');
  });

  it('More button reflects aria-expanded when moreOpen=true', () => {
    renderWithProviders(<BottomNav onMore={vi.fn()} moreOpen />, { route: '/' });
    const btn = screen.getByRole('button', { name: /more/i });
    expect(btn).toHaveAttribute('aria-expanded', 'true');
  });

  it('Read link has aria-current="page" when on /read', () => {
    renderWithProviders(<BottomNav onMore={vi.fn()} />, { route: '/read' });
    const link = screen.getByRole('link', { name: /read/i });
    expect(link).toHaveAttribute('aria-current', 'page');
  });

  it('Today link has aria-current="page" on /', () => {
    renderWithProviders(<BottomNav onMore={vi.fn()} />, { route: '/' });
    const link = screen.getByRole('link', { name: /today/i });
    expect(link).toHaveAttribute('aria-current', 'page');
  });

  it('calls onMore when More is clicked', () => {
    const onMore = vi.fn();
    renderWithProviders(<BottomNav onMore={onMore} />, { route: '/' });
    fireEvent.click(screen.getByRole('button', { name: /more/i }));
    expect(onMore).toHaveBeenCalledTimes(1);
  });
});

// ── MoreSheet unit tests ──────────────────────────────────────────────────────

describe('MoreSheet', () => {
  const onClose = vi.fn();
  const onOpenSettings = vi.fn();

  beforeEach(() => {
    onClose.mockClear();
    onOpenSettings.mockClear();
  });

  function renderSheet() {
    return renderWithProviders(
      <MoreSheet onClose={onClose} onOpenSettings={onOpenSettings} />,
    );
  }

  it('renders with role=dialog and aria-modal', () => {
    renderSheet();
    const dialog = screen.getByRole('dialog', { name: /more/i });
    expect(dialog).toHaveAttribute('aria-modal', 'true');
  });

  it('Body link has href /body', () => {
    renderSheet();
    expect(screen.getByRole('link', { name: /body/i })).toHaveAttribute('href', '/body');
  });

  it('Calendar link has href /calendar', () => {
    renderSheet();
    expect(screen.getByRole('link', { name: /calendar/i })).toHaveAttribute('href', '/calendar');
  });

  it('Projects link has href /projects', () => {
    renderSheet();
    expect(screen.getByRole('link', { name: /projects/i })).toHaveAttribute('href', '/projects');
  });

  it('Body link click calls onClose', () => {
    renderSheet();
    fireEvent.click(screen.getByRole('link', { name: /body/i }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('Calendar link click calls onClose', () => {
    renderSheet();
    fireEvent.click(screen.getByRole('link', { name: /calendar/i }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('Projects link click calls onClose', () => {
    renderSheet();
    fireEvent.click(screen.getByRole('link', { name: /projects/i }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('Settings button calls onOpenSettings', () => {
    renderSheet();
    fireEvent.click(screen.getByRole('button', { name: /settings/i }));
    expect(onOpenSettings).toHaveBeenCalledTimes(1);
  });

  it('Escape key calls onClose', () => {
    renderSheet();
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('clicking backdrop calls onClose', () => {
    renderSheet();
    const backdrop = screen.getByTestId('more-sheet-backdrop');
    fireEvent.click(backdrop);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('clicking the panel does NOT call onClose', () => {
    renderSheet();
    const dialog = screen.getByRole('dialog', { name: /more/i });
    fireEvent.click(dialog);
    expect(onClose).not.toHaveBeenCalled();
  });

  it('Close button calls onClose', () => {
    renderSheet();
    fireEvent.click(screen.getByRole('button', { name: /close/i }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
