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

const getUnsurfacedArticlesMock = vi.fn();
const refreshFeedMock = vi.fn();
const markArticleReadMock = vi.fn();
const extractKeywordsMock = vi.fn();
const hasArticlesMock = vi.fn();

vi.mock('../services/newsFeedService', () => ({
  getUnsurfacedArticles: (...args: unknown[]) => getUnsurfacedArticlesMock(...args),
  refreshFeed: (...args: unknown[]) => refreshFeedMock(...args),
  markArticleRead: (...args: unknown[]) => markArticleReadMock(...args),
  extractKeywordsFromContext: (...args: unknown[]) => extractKeywordsMock(...args),
  hasArticles: () => hasArticlesMock(),
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
  getUnsurfacedArticlesMock.mockReturnValue([]);
  refreshFeedMock.mockResolvedValue({ articles: [], newCount: 0 });
  extractKeywordsMock.mockReturnValue([]);
});

// ── Tests ────────────────────────────────────────────────────────────────

describe('useNewsFeed', () => {
  it('creates a query with the correct key and stale time', () => {
    render(<HookProbe />);

    expect(useQueryMock).toHaveBeenCalledWith(
      expect.objectContaining({
        queryKey: ['news', 'feed'],
        staleTime: 5 * 60 * 1000,
        refetchOnWindowFocus: false,
      })
    );
  });

  it('provides a queryFn that calls getUnsurfacedArticles', async () => {
    render(<HookProbe />);

    const queryOptions = useQueryMock.mock.calls[0][0];
    const queryFn = queryOptions.queryFn;

    hasArticlesMock.mockReturnValue(true);
    getUnsurfacedArticlesMock.mockReturnValue([{ id: 'test' }]);

    const result = await queryFn();
    expect(getUnsurfacedArticlesMock).toHaveBeenCalledWith(8);
    expect(result).toEqual([{ id: 'test' }]);
  });

  it('triggers auto-refresh when no articles exist', async () => {
    render(<HookProbe />);

    const queryFn = useQueryMock.mock.calls[0][0].queryFn;

    hasArticlesMock.mockReturnValue(false);
    getUnsurfacedArticlesMock.mockReturnValue([]);

    await queryFn();

    expect(refreshFeedMock).toHaveBeenCalled();
  });

  it('does not auto-refresh when articles exist', async () => {
    render(<HookProbe />);

    const queryFn = useQueryMock.mock.calls[0][0].queryFn;

    hasArticlesMock.mockReturnValue(true);
    getUnsurfacedArticlesMock.mockReturnValue([{ id: 'existing' }]);

    await queryFn();

    expect(refreshFeedMock).not.toHaveBeenCalled();
  });

  it('extracts keywords from active todos for refresh', async () => {
    useTodosMock.mockReturnValue({
      todosQuery: {
        data: [
          { id: 1, text: 'Learn Python', completed: false },
          { id: 2, text: 'Buy groceries', completed: true }, // should be filtered
          { id: 3, text: 'Study machine learning', completed: false },
        ],
      },
    });

    render(<HookProbe />);

    const queryFn = useQueryMock.mock.calls[0][0].queryFn;
    hasArticlesMock.mockReturnValue(false);
    await queryFn();

    expect(extractKeywordsMock).toHaveBeenCalledWith(
      ['Learn Python', 'Study machine learning'],
      []
    );
  });

  it('creates a mutation for markRead', () => {
    render(<HookProbe />);

    // Second useMutation call is for markRead
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

  it('exposes feedQuery from useQuery', () => {
    const mockQueryResult = { data: [{ id: 'x' }], isLoading: false };
    useQueryMock.mockReturnValue(mockQueryResult);

    render(<HookProbe />);
    expect(hookResult.feedQuery).toBe(mockQueryResult);
  });
});
