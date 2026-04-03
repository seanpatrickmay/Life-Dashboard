// @vitest-environment jsdom
import { render } from '@testing-library/react';
import React from 'react';
import { describe, expect, it, beforeEach, vi } from 'vitest';

// ── Mocks ────────────────────────────────────────────────────────────────

const useQueryMock = vi.fn();
const useMutationMock = vi.fn();
const useQueryClientMock = vi.fn();

vi.mock('@tanstack/react-query', () => ({
  useQuery: (options: unknown) => useQueryMock(options),
  useMutation: (options: unknown) => useMutationMock(options),
  useQueryClient: () => useQueryClientMock(),
}));

const getTopPerCategoryMock = vi.fn();
const getAllByCategoryMock = vi.fn();
const getCuratedFeedMock = vi.fn();
const refreshFeedMock = vi.fn();
const markArticleReadMock = vi.fn();
const getArticleByIdMock = vi.fn();
const extractKeywordsMock = vi.fn();
const hasArticlesMock = vi.fn();

vi.mock('../services/newsFeedService', () => ({
  getTopPerCategory: (...args: unknown[]) => getTopPerCategoryMock(...args),
  getAllByCategory: (...args: unknown[]) => getAllByCategoryMock(...args),
  getCuratedFeed: (...args: unknown[]) => getCuratedFeedMock(...args),
  refreshFeed: (...args: unknown[]) => refreshFeedMock(...args),
  markArticleRead: (...args: unknown[]) => markArticleReadMock(...args),
  getArticleById: (...args: unknown[]) => getArticleByIdMock(...args),
  extractKeywordsFromContext: (...args: unknown[]) => extractKeywordsMock(...args),
  hasArticles: () => hasArticlesMock(),
}));

vi.mock('../services/interestProfile', () => ({
  recordRead: vi.fn(),
  recordDismiss: vi.fn(),
  saveArticle: vi.fn(),
  unsaveArticle: vi.fn(),
  dismissArticle: vi.fn(),
  getSavedArticleIds: vi.fn().mockReturnValue([]),
  getCategoryDistribution: vi.fn().mockReturnValue({}),
  getExplorationSlots: vi.fn().mockReturnValue(4),
}));

vi.mock('../services/api', () => ({
  scoreArticles: vi.fn().mockResolvedValue([]),
  annotateArticles: vi.fn().mockResolvedValue([]),
  summarizeProfile: vi.fn().mockResolvedValue({ narrative: '', topics: [] }),
  embedTexts: vi.fn().mockResolvedValue([]),
}));

vi.mock('../services/profileSummarizer', () => ({
  getProfileEmbedding: vi.fn().mockResolvedValue(null),
  getArticleEmbeddings: vi.fn().mockResolvedValue(new Map()),
  cosineSimilarity: vi.fn().mockReturnValue(0),
}));

const useTodosMock = vi.fn();

vi.mock('./useTodos', () => ({
  useTodos: () => useTodosMock(),
}));

import { useNewsFeed } from './useNewsFeed';

// ── Hook probe ───────────────────────────────────────────────────────────

let hookResult: ReturnType<typeof useNewsFeed>;

function HookProbe() {
  hookResult = useNewsFeed();
  return null;
}

// ── Setup ────────────────────────────────────────────────────────────────

beforeEach(() => {
  vi.clearAllMocks();

  useQueryMock.mockReturnValue({ data: [], isLoading: false });
  useMutationMock.mockReturnValue({ mutate: vi.fn(), mutateAsync: vi.fn(), isPending: false });
  useQueryClientMock.mockReturnValue({ invalidateQueries: vi.fn() });

  useTodosMock.mockReturnValue({
    todosQuery: { data: [] },
  });

  hasArticlesMock.mockReturnValue(true);
  getTopPerCategoryMock.mockReturnValue([]);
  getAllByCategoryMock.mockReturnValue({ tech: [], science: [], world: [], culture: [], history: [], business: [], wikipedia: [] });
  getCuratedFeedMock.mockReturnValue({ picks: [], more: [], saved: [] });
  refreshFeedMock.mockResolvedValue({ articles: [], newCount: 0 });
  extractKeywordsMock.mockReturnValue([]);
  getArticleByIdMock.mockReturnValue(null);
});

// ── Tests ────────────────────────────────────────────────────────────────

describe('useNewsFeed', () => {
  it('creates three queries: feedQuery, allQuery, and curatedQuery', () => {
    render(<HookProbe />);

    // Should call useQuery five times (profile, feed, all, curated, annotations)
    expect(useQueryMock).toHaveBeenCalledTimes(5);
  });

  it('feedQuery uses correct key and stale time', () => {
    render(<HookProbe />);

    expect(useQueryMock).toHaveBeenCalledWith(
      expect.objectContaining({
        queryKey: ['news', 'feed'],
        staleTime: 5 * 60 * 1000,
        refetchOnWindowFocus: false,
      })
    );
  });

  it('allQuery uses correct key and stale time', () => {
    render(<HookProbe />);

    expect(useQueryMock).toHaveBeenCalledWith(
      expect.objectContaining({
        queryKey: ['news', 'all'],
        staleTime: 5 * 60 * 1000,
        refetchOnWindowFocus: false,
      })
    );
  });

  it('feedQuery calls getTopPerCategory', async () => {
    render(<HookProbe />);

    const feedQueryOptions = useQueryMock.mock.calls.find(
      (call: any) => call[0].queryKey[1] === 'feed'
    )[0];

    hasArticlesMock.mockReturnValue(true);
    getTopPerCategoryMock.mockReturnValue([{ id: 'top1', category: 'tech' }]);

    const result = await feedQueryOptions.queryFn();
    expect(getTopPerCategoryMock).toHaveBeenCalled();
    expect(result).toEqual([{ id: 'top1', category: 'tech' }]);
  });

  it('allQuery calls getAllByCategory', async () => {
    render(<HookProbe />);

    const allQueryOptions = useQueryMock.mock.calls.find(
      (call: any) => call[0].queryKey[1] === 'all'
    )[0];

    hasArticlesMock.mockReturnValue(true);
    const mockResult = { tech: [{ id: 't1' }], science: [], world: [], culture: [], history: [], business: [], wikipedia: [] };
    getAllByCategoryMock.mockReturnValue(mockResult);

    const result = await allQueryOptions.queryFn();
    expect(getAllByCategoryMock).toHaveBeenCalled();
    expect(result).toEqual(mockResult);
  });

  it('triggers auto-refresh when no articles exist', async () => {
    render(<HookProbe />);

    const feedQueryOptions = useQueryMock.mock.calls.find(
      (call: any) => call[0].queryKey[1] === 'feed'
    )[0];

    hasArticlesMock.mockReturnValue(false);
    getTopPerCategoryMock.mockReturnValue([]);

    await feedQueryOptions.queryFn();
    expect(refreshFeedMock).toHaveBeenCalled();
  });

  it('does not auto-refresh when articles exist', async () => {
    render(<HookProbe />);

    const feedQueryOptions = useQueryMock.mock.calls.find(
      (call: any) => call[0].queryKey[1] === 'feed'
    )[0];

    hasArticlesMock.mockReturnValue(true);
    getTopPerCategoryMock.mockReturnValue([{ id: 'existing' }]);

    await feedQueryOptions.queryFn();
    expect(refreshFeedMock).not.toHaveBeenCalled();
  });

  it('extracts keywords from active todos for refresh', async () => {
    useTodosMock.mockReturnValue({
      todosQuery: {
        data: [
          { id: 1, text: 'Learn Python', completed: false },
          { id: 2, text: 'Buy groceries', completed: true },
          { id: 3, text: 'Study machine learning', completed: false },
        ],
      },
    });

    render(<HookProbe />);

    const feedQueryOptions = useQueryMock.mock.calls.find(
      (call: any) => call[0].queryKey[1] === 'feed'
    )[0];
    hasArticlesMock.mockReturnValue(false);
    await feedQueryOptions.queryFn();

    expect(extractKeywordsMock).toHaveBeenCalledWith(
      ['Learn Python', 'Study machine learning'],
      [],
      [],
    );
  });

  it('creates a mutation for markRead', () => {
    render(<HookProbe />);

    expect(useMutationMock).toHaveBeenCalled();
    const markReadOptions = useMutationMock.mock.calls[0][0];
    expect(markReadOptions.mutationFn).toBeDefined();
  });

  it('markRead mutation calls markArticleRead service', async () => {
    render(<HookProbe />);

    const markReadMutationFn = useMutationMock.mock.calls[0][0].mutationFn;
    await markReadMutationFn('article-123');

    expect(markArticleReadMock).toHaveBeenCalledWith('article-123');
  });

  it('exposes isRefreshing state', () => {
    render(<HookProbe />);
    expect(hookResult.isRefreshing).toBe(false);
  });

  it('exposes feedQuery, allQuery, and curatedQuery from useQuery', () => {
    const mockResult = { data: [{ id: 'x' }], isLoading: false };
    useQueryMock.mockReturnValue(mockResult);

    render(<HookProbe />);
    expect(hookResult.feedQuery).toBe(mockResult);
    expect(hookResult.allQuery).toBe(mockResult);
    expect(hookResult.curatedQuery).toBe(mockResult);
  });
});
