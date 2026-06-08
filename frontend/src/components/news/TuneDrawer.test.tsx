// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { QueryClient } from '@tanstack/react-query';
import { renderWithProviders } from '../../test/renderWithProviders';
import { TuneDrawer } from './TuneDrawer';
import { getBoostedTopics, getMutedTopics } from '../../services/interestProfile';
import { NEWS_CURATED_KEY } from '../../hooks/useNewsFeed';

// Mock useNewsFeed to avoid network calls
vi.mock('../../hooks/useNewsFeed', () => ({
  useNewsFeed: () => ({
    profileQuery: { data: { narrative: 'You like tech.', topics: ['llms', 'rust', 'python'] } },
    curatedQuery: { data: null },
    annotationsQuery: { data: {} },
    feedQuery: { data: [] },
    allQuery: { data: {} },
    refreshFeed: vi.fn(),
    markRead: vi.fn(),
    saveArticle: vi.fn(),
    unsaveArticle: vi.fn(),
    dismissArticle: vi.fn(),
    isRefreshing: false,
  }),
  NEWS_CURATED_KEY: ['news', 'curated'],
}));

describe('TuneDrawer', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('renders the drawer heading', () => {
    renderWithProviders(<TuneDrawer onClose={() => {}} />);
    expect(screen.getByText('Tune your feed')).toBeInTheDocument();
  });

  it('renders profile topics as chips', () => {
    renderWithProviders(<TuneDrawer onClose={() => {}} />);
    expect(screen.getByText('llms')).toBeInTheDocument();
    expect(screen.getByText('rust')).toBeInTheDocument();
    expect(screen.getByText('python')).toBeInTheDocument();
  });

  it('renders boost and mute buttons for each topic', () => {
    renderWithProviders(<TuneDrawer onClose={() => {}} />);
    // Each topic chip should have + (boost) and ✕ (mute) buttons
    const boostBtns = screen.getAllByRole('button', { name: /boost/i });
    expect(boostBtns.length).toBeGreaterThan(0);
    const muteBtns = screen.getAllByRole('button', { name: /mute/i });
    expect(muteBtns.length).toBeGreaterThan(0);
  });

  it('persists boost toggle to localStorage', () => {
    renderWithProviders(<TuneDrawer onClose={() => {}} />);
    const boostBtn = screen.getByRole('button', { name: /boost llms/i });
    fireEvent.click(boostBtn);
    expect(getBoostedTopics()).toContain('llms');
  });

  it('persists mute toggle to localStorage', () => {
    renderWithProviders(<TuneDrawer onClose={() => {}} />);
    const muteBtn = screen.getByRole('button', { name: /^Mute llms$/i });
    fireEvent.click(muteBtn);
    expect(getMutedTopics()).toContain('llms');
  });

  it('muting a boosted topic removes it from boosted', () => {
    renderWithProviders(<TuneDrawer onClose={() => {}} />);
    // First boost llms
    fireEvent.click(screen.getByRole('button', { name: /boost llms/i }));
    expect(getBoostedTopics()).toContain('llms');
    // After boosting, the mute button label changes to "Mute llms" (currently not muted)
    fireEvent.click(screen.getByRole('button', { name: /^Mute llms$/i }));
    // toggleMute removes from boosted set before saving
    expect(getMutedTopics()).toContain('llms');
    // boosted should no longer include llms after mute cross-clears it
    const boosted = getBoostedTopics();
    expect(boosted).not.toContain('llms');
  });

  it('calls onClose when close button is clicked', () => {
    const onClose = vi.fn();
    renderWithProviders(<TuneDrawer onClose={onClose} />);
    fireEvent.click(screen.getByRole('button', { name: /close/i }));
    expect(onClose).toHaveBeenCalled();
  });

  it('renders exploration slider', () => {
    renderWithProviders(<TuneDrawer onClose={() => {}} />);
    expect(screen.getByRole('slider', { name: /exploration/i })).toBeInTheDocument();
  });

  it('renders clear overrides button', () => {
    renderWithProviders(<TuneDrawer onClose={() => {}} />);
    expect(screen.getByRole('button', { name: /clear all/i })).toBeInTheDocument();
  });

  it('clear overrides resets boosted and muted topics in localStorage', () => {
    renderWithProviders(<TuneDrawer onClose={() => {}} />);
    fireEvent.click(screen.getByRole('button', { name: /boost llms/i }));
    fireEvent.click(screen.getByRole('button', { name: /mute rust/i }));
    fireEvent.click(screen.getByRole('button', { name: /clear all/i }));
    expect(getBoostedTopics()).toEqual([]);
    expect(getMutedTopics()).toEqual([]);
  });

  it('moves focus to the close button when the drawer opens', async () => {
    renderWithProviders(<TuneDrawer onClose={() => {}} />);
    const closeBtn = screen.getByRole('button', { name: /close/i });
    await waitFor(() => {
      expect(document.activeElement).toBe(closeBtn);
    });
  });

  it('calls queryClient.invalidateQueries with NEWS_CURATED_KEY when closed', () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: 0 } },
    });
    const spy = vi.spyOn(queryClient, 'invalidateQueries');
    const onClose = vi.fn();
    renderWithProviders(<TuneDrawer onClose={onClose} />, { queryClient });
    fireEvent.click(screen.getByRole('button', { name: /close/i }));
    expect(spy).toHaveBeenCalledWith({ queryKey: NEWS_CURATED_KEY });
    expect(onClose).toHaveBeenCalled();
  });
});
