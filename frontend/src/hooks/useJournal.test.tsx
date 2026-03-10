// @vitest-environment jsdom
import { render } from '@testing-library/react';
import React from 'react';
import { describe, expect, it, beforeEach, vi } from 'vitest';

const useQueryMock = vi.fn();
const useMutationMock = vi.fn();
const useQueryClientMock = vi.fn();

vi.mock('@tanstack/react-query', () => ({
  useQuery: (options: unknown) => useQueryMock(options),
  useMutation: (options: unknown) => useMutationMock(options),
  useQueryClient: () => useQueryClientMock()
}));

vi.mock('../utils/timeZone', () => ({
  getUserTimeZone: () => 'America/New_York'
}));

vi.mock('../services/api', () => ({
  createJournalEntry: vi.fn(),
  fetchJournalDay: vi.fn(),
  fetchJournalWeek: vi.fn()
}));

import { useJournal } from './useJournal';

function HookProbe() {
  useJournal('2026-03-10', '2026-03-08');
  return null;
}

describe('useJournal', () => {
  beforeEach(() => {
    useQueryMock.mockReset();
    useMutationMock.mockReset();
    useQueryClientMock.mockReset();
    useQueryMock.mockReturnValue({});
    useMutationMock.mockReturnValue({ mutateAsync: vi.fn(), isPending: false });
    useQueryClientMock.mockReturnValue({ invalidateQueries: vi.fn() });
  });

  it('uses journal-specific polling and refetch options', () => {
    render(<HookProbe />);

    expect(useQueryMock).toHaveBeenNthCalledWith(
      1,
      expect.objectContaining({
        refetchOnWindowFocus: true,
        refetchInterval: 60 * 1000,
        refetchIntervalInBackground: false
      })
    );
    expect(useQueryMock).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({
        refetchOnWindowFocus: true,
        refetchInterval: 5 * 60 * 1000,
        refetchIntervalInBackground: false
      })
    );
  });
});
