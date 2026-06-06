import type { TodoItem } from '../../services/api';

function completedAtMs(item: TodoItem): number {
  if (!item.completed_at_utc) return 0;
  const t = Date.parse(item.completed_at_utc);
  return Number.isNaN(t) ? 0 : t;
}

/**
 * Split a section's todos into active and completed.
 * Active items keep their original order; completed items are sorted
 * most-recently-completed first (stable for missing/equal timestamps).
 */
export function partitionByCompletion(items: TodoItem[]): {
  active: TodoItem[];
  done: TodoItem[];
} {
  const active: TodoItem[] = [];
  const done: TodoItem[] = [];
  for (const item of items) {
    if (item.completed) done.push(item);
    else active.push(item);
  }
  done.sort((a, b) => completedAtMs(b) - completedAtMs(a));
  return { active, done };
}
