// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
import { screen, fireEvent, waitFor, within } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { renderWithProviders } from '../../test/renderWithProviders';
import { SettingsDrawer } from './SettingsDrawer';
import { ThemeModeContext } from '../../theme/ThemeProvider';
import type { ReactNode } from 'react';

// Stub UserProfileScene so tests focus on drawer shell
vi.mock('../user/UserProfileScene', () => ({
  UserProfileScene: () => <div data-testid="user-profile-scene" />,
}));

// Stub useNavigate to capture calls
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

// Helper: minimal ThemeModeContext value
const mockSetMode = vi.fn();
function makeThemeCtx(mode: 'light' | 'dark' | 'system' = 'dark') {
  return {
    mode,
    effective: (mode === 'system' ? 'dark' : mode) as 'light' | 'dark',
    setMode: mockSetMode,
    toggle: vi.fn(),
    intensity: 'rich' as const,
    setIntensity: vi.fn(),
    motion: true,
    setMotion: vi.fn(),
    timeOfDayMode: 'auto' as const,
    setTimeOfDayMode: vi.fn(),
    moment: 'night' as const,
    featureScene: 'auto' as const,
    setFeatureScene: vi.fn(),
    willowEnabled: true,
    setWillowEnabled: vi.fn(),
    sceneDensity: 'sparse' as const,
    setSceneDensity: vi.fn(),
    horizonMode: 'auto' as const,
    setHorizonMode: vi.fn(),
    sceneHorizon: 0.7,
    timeTestEnabled: false,
    setTimeTestEnabled: vi.fn(),
    sceneHour: 22,
    setSceneHour: vi.fn(),
  };
}

function renderWithTheme(
  ui: ReactNode,
  { mode = 'dark' as 'light' | 'dark' | 'system', route = '/' } = {},
) {
  const ctx = makeThemeCtx(mode);
  return renderWithProviders(
    <ThemeModeContext.Provider value={ctx}>{ui}</ThemeModeContext.Provider>,
    { route },
  );
}

describe('SettingsDrawer', () => {
  beforeEach(() => {
    mockNavigate.mockReset();
    mockSetMode.mockReset();
  });

  // ── Structure / a11y ──────────────────────────────────────────────────────

  it('renders a dialog with aria-modal and the Settings heading', () => {
    renderWithTheme(<SettingsDrawer onClose={() => {}} />);
    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(screen.getByRole('heading', { name: /settings/i })).toBeInTheDocument();
  });

  it('has an accessible close button', () => {
    renderWithTheme(<SettingsDrawer onClose={() => {}} />);
    expect(screen.getByRole('button', { name: /close/i })).toBeInTheDocument();
  });

  it('moves focus into the panel when it opens', async () => {
    renderWithTheme(<SettingsDrawer onClose={() => {}} />);
    await waitFor(() => {
      expect(document.activeElement).not.toBe(document.body);
    });
  });

  // ── Close behaviour ───────────────────────────────────────────────────────

  it('calls onClose when the close button is clicked', () => {
    const onClose = vi.fn();
    renderWithTheme(<SettingsDrawer onClose={onClose} />);
    fireEvent.click(screen.getByRole('button', { name: /close/i }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('calls onClose when Escape is pressed', () => {
    const onClose = vi.fn();
    renderWithTheme(<SettingsDrawer onClose={onClose} />);
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('calls onClose when clicking the backdrop (not the panel)', () => {
    const onClose = vi.fn();
    const { container } = renderWithTheme(<SettingsDrawer onClose={onClose} />);
    // The backdrop is the outermost element; simulate click directly on it
    const backdrop = container.firstChild as HTMLElement;
    fireEvent.click(backdrop);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('does NOT call onClose when clicking inside the panel', () => {
    const onClose = vi.fn();
    renderWithTheme(<SettingsDrawer onClose={onClose} />);
    const dialog = screen.getByRole('dialog');
    fireEvent.click(dialog);
    expect(onClose).not.toHaveBeenCalled();
  });

  // ── Theme control ─────────────────────────────────────────────────────────

  it('renders Light, Dark, and System theme options', () => {
    renderWithTheme(<SettingsDrawer onClose={() => {}} />);
    expect(screen.getByRole('button', { name: /^light$/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^dark$/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^system$/i })).toBeInTheDocument();
  });

  it('calls setMode("light") when Light is clicked', () => {
    renderWithTheme(<SettingsDrawer onClose={() => {}} />, { mode: 'dark' });
    fireEvent.click(screen.getByRole('button', { name: /^light$/i }));
    expect(mockSetMode).toHaveBeenCalledWith('light');
  });

  it('calls setMode("dark") when Dark is clicked', () => {
    renderWithTheme(<SettingsDrawer onClose={() => {}} />, { mode: 'light' });
    fireEvent.click(screen.getByRole('button', { name: /^dark$/i }));
    expect(mockSetMode).toHaveBeenCalledWith('dark');
  });

  it('calls setMode("system") when System is clicked', () => {
    renderWithTheme(<SettingsDrawer onClose={() => {}} />, { mode: 'light' });
    fireEvent.click(screen.getByRole('button', { name: /^system$/i }));
    expect(mockSetMode).toHaveBeenCalledWith('system');
  });

  it('marks the current mode button as selected (aria-pressed)', () => {
    renderWithTheme(<SettingsDrawer onClose={() => {}} />, { mode: 'dark' });
    expect(screen.getByRole('button', { name: /^dark$/i })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: /^light$/i })).toHaveAttribute('aria-pressed', 'false');
  });

  // ── Food DB link ──────────────────────────────────────────────────────────

  it('renders the "Manage food database" control', () => {
    renderWithTheme(<SettingsDrawer onClose={() => {}} />);
    expect(screen.getByRole('button', { name: /manage food database/i })).toBeInTheDocument();
  });

  it('navigates to /settings/food-db and calls onClose when food-db button is clicked', () => {
    const onClose = vi.fn();
    renderWithTheme(<SettingsDrawer onClose={onClose} />);
    fireEvent.click(screen.getByRole('button', { name: /manage food database/i }));
    expect(mockNavigate).toHaveBeenCalledWith('/settings/food-db');
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  // ── UserProfileScene reuse ────────────────────────────────────────────────

  it('renders the UserProfileScene stub', () => {
    renderWithTheme(<SettingsDrawer onClose={() => {}} />);
    expect(screen.getByTestId('user-profile-scene')).toBeInTheDocument();
  });
});
