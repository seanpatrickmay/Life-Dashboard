// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from 'vitest';

import { clearGuestState, getGuestJournalDay } from './guestStore';

const getLocalDateKey = (date: Date) => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
};

describe('guest journal summaries', () => {
  beforeEach(() => {
    clearGuestState();
  });

  it('returns structured summary items for guest mode', () => {
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    const response = getGuestJournalDay(getLocalDateKey(yesterday), 'America/New_York');
    const firstItem = response.summary?.groups[0]?.items[0];

    expect(firstItem).toEqual(
      expect.objectContaining({
        text: expect.any(String),
        time_precision: 'exact',
        time_label: expect.any(String),
        occurred_at_local: expect.any(String)
      })
    );
  });
});
