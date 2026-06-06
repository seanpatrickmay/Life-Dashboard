import { describe, expect, it } from 'vitest';

import { partitionByCompletion } from './todoOrdering';
import type { TodoItem } from '../../services/api';

const makeTodo = (over: Partial<TodoItem>): TodoItem => ({
  id: 1,
  project_id: 1,
  text: 'task',
  completed: false,
  completed_at_utc: null,
  deadline_utc: null,
  deadline_is_date_only: false,
  time_horizon: 'this_week',
  is_overdue: false,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  ...over
});

describe('partitionByCompletion', () => {
  it('splits active and completed items', () => {
    const items = [
      makeTodo({ id: 1, completed: false }),
      makeTodo({ id: 2, completed: true, completed_at_utc: '2026-01-02T00:00:00Z' })
    ];
    const { active, done } = partitionByCompletion(items);
    expect(active.map((i) => i.id)).toEqual([1]);
    expect(done.map((i) => i.id)).toEqual([2]);
  });

  it('orders completed items most-recently-completed first', () => {
    const items = [
      makeTodo({ id: 1, completed: true, completed_at_utc: '2026-01-01T00:00:00Z' }),
      makeTodo({ id: 2, completed: true, completed_at_utc: '2026-03-01T00:00:00Z' }),
      makeTodo({ id: 3, completed: true, completed_at_utc: '2026-02-01T00:00:00Z' })
    ];
    const { done } = partitionByCompletion(items);
    expect(done.map((i) => i.id)).toEqual([2, 3, 1]);
  });

  it('keeps active items in their original order', () => {
    const items = [makeTodo({ id: 5 }), makeTodo({ id: 4 }), makeTodo({ id: 6 })];
    const { active } = partitionByCompletion(items);
    expect(active.map((i) => i.id)).toEqual([5, 4, 6]);
  });

  it('sorts completed items with missing timestamps to the end, stably', () => {
    const items = [
      makeTodo({ id: 1, completed: true, completed_at_utc: null }),
      makeTodo({ id: 2, completed: true, completed_at_utc: '2026-01-01T00:00:00Z' }),
      makeTodo({ id: 3, completed: true, completed_at_utc: null })
    ];
    const { done } = partitionByCompletion(items);
    expect(done.map((i) => i.id)).toEqual([2, 1, 3]);
  });
});
