import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useRef, useCallback, useMemo } from 'react';
import { createTodo, deleteTodo, fetchTodos, updateTodo, type TodoItem } from '../services/api';
import { getUserTimeZone } from '../utils/timeZone';

const TODOS_QUERY_KEY = ['todos', 'list'];

/**
 * Optimized todos hook with race condition prevention
 * Key improvements:
 * 1. Maintains optimistic state separately from server state
 * 2. Prevents query invalidation during pending updates
 * 3. Batches multiple updates intelligently
 * 4. Smooth UI with no flashing or unmarking
 */
export function useTodosOptimized() {
  const queryClient = useQueryClient();
  const pendingUpdatesRef = useRef<Map<number, Partial<TodoItem>>>(new Map());
  const invalidateTimerRef = useRef<NodeJS.Timeout | null>(null);

  const timeZone = getUserTimeZone();

  // Smart invalidation that waits for all updates to complete
  const smartInvalidate = useCallback(() => {
    // Clear any existing timer
    if (invalidateTimerRef.current) {
      clearTimeout(invalidateTimerRef.current);
    }

    // Set a new timer to invalidate after updates settle
    invalidateTimerRef.current = setTimeout(() => {
      // Only invalidate if no pending updates remain
      if (pendingUpdatesRef.current.size === 0) {
        queryClient.invalidateQueries({ queryKey: TODOS_QUERY_KEY });
        queryClient.invalidateQueries({ queryKey: ['journal'] });
      } else {
        // Check again in a bit if updates are still pending
        smartInvalidate();
      }
    }, 500); // Wait 500ms for updates to settle
  }, [queryClient]);

  // Main query with longer stale time
  const todosQuery = useQuery<TodoItem[]>({
    queryKey: [...TODOS_QUERY_KEY, timeZone],
    queryFn: () => fetchTodos(timeZone),
    staleTime: 10000, // 10 seconds - prevent excessive refetching
    gcTime: 30000, // Keep in cache for 30 seconds
    refetchOnWindowFocus: false, // Don't refetch on window focus
  });

  // Merge pending updates with query data for smooth UI
  const todosWithPending = useMemo(() => {
    const items = todosQuery.data ?? [];
    if (pendingUpdatesRef.current.size === 0) return items;

    return items.map(item => {
      const pending = pendingUpdatesRef.current.get(item.id);
      if (!pending) return item;

      // Merge pending changes
      return { ...item, ...pending };
    });
  }, [todosQuery.data, pendingUpdatesRef.current.size]);

  const updateMutation = useMutation({
    mutationFn: async (payload: {
      id: number;
      text?: string;
      deadline_utc?: string | null;
      deadline_is_date_only?: boolean;
      completed?: boolean;
      completed_at_utc?: string | null;
    }) => {
      const shouldSendTimeZone =
        payload.completed !== undefined ||
        payload.deadline_utc !== undefined ||
        payload.deadline_is_date_only !== undefined;
      const tz = shouldSendTimeZone ? getUserTimeZone() : undefined;

      // Store pending update
      pendingUpdatesRef.current.set(payload.id, {
        ...pendingUpdatesRef.current.get(payload.id),
        ...payload,
      });

      try {
        const result = await updateTodo(payload.id, {
          text: payload.text,
          deadline_utc: payload.deadline_utc,
          deadline_is_date_only: payload.deadline_is_date_only,
          completed: payload.completed,
          completed_at_utc: payload.completed_at_utc,
          time_zone: tz
        });

        return result;
      } finally {
        // Remove from pending after completion
        pendingUpdatesRef.current.delete(payload.id);
      }
    },
    onMutate: async (payload) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: TODOS_QUERY_KEY });

      const previousData = queryClient.getQueryData<TodoItem[]>([...TODOS_QUERY_KEY, timeZone]);

      // Update cache optimistically
      queryClient.setQueryData<TodoItem[]>([...TODOS_QUERY_KEY, timeZone], (current) => {
        if (!current) return current;

        return current.map(item => {
          if (item.id !== payload.id) return item;

          const updated = { ...item };

          // Apply all updates
          if (payload.text !== undefined) updated.text = payload.text;
          if (payload.deadline_utc !== undefined) updated.deadline_utc = payload.deadline_utc;
          if (payload.deadline_is_date_only !== undefined) {
            updated.deadline_is_date_only = payload.deadline_is_date_only;
          }

          if (payload.completed !== undefined) {
            updated.completed = payload.completed;
            if (payload.completed && !payload.completed_at_utc) {
              updated.completed_at_utc = new Date().toISOString();
            } else if (payload.completed_at_utc !== undefined) {
              updated.completed_at_utc = payload.completed_at_utc;
            }

            // Update derived fields
            if (updated.deadline_utc) {
              updated.is_overdue = !updated.completed && new Date(updated.deadline_utc) < new Date();
            }
          }

          return updated;
        });
      });

      return { previousData };
    },
    onError: (_error, _payload, context) => {
      // Rollback on error
      if (context?.previousData) {
        queryClient.setQueryData([...TODOS_QUERY_KEY, timeZone], context.previousData);
      }
    },
    onSettled: () => {
      // Use smart invalidation
      smartInvalidate();
    },
    retry: 1,
  });

  // Batch update for multiple todos at once
  const batchComplete = useCallback((todoIds: number[], completed: boolean = true) => {
    // Update cache for all items at once
    queryClient.setQueryData<TodoItem[]>([...TODOS_QUERY_KEY, timeZone], (current) => {
      if (!current) return current;

      const idSet = new Set(todoIds);
      const now = new Date().toISOString();

      return current.map(item => {
        if (!idSet.has(item.id)) return item;

        return {
          ...item,
          completed,
          completed_at_utc: completed ? now : null,
          is_overdue: false,
        };
      });
    });

    // Send updates without blocking
    todoIds.forEach(id => {
      updateMutation.mutate({ id, completed });
    });
  }, [queryClient, timeZone, updateMutation]);

  const deleteMutation = useMutation({
    mutationFn: deleteTodo,
    onMutate: async (id: number) => {
      await queryClient.cancelQueries({ queryKey: TODOS_QUERY_KEY });

      const previousData = queryClient.getQueryData<TodoItem[]>([...TODOS_QUERY_KEY, timeZone]);

      // Remove optimistically
      queryClient.setQueryData<TodoItem[]>([...TODOS_QUERY_KEY, timeZone], (current) =>
        (current ?? []).filter(item => item.id !== id)
      );

      return { previousData };
    },
    onError: (_error, _id, context) => {
      if (context?.previousData) {
        queryClient.setQueryData([...TODOS_QUERY_KEY, timeZone], context.previousData);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: TODOS_QUERY_KEY });
    },
  });

  return {
    todos: todosWithPending, // Use merged data
    todosQuery,
    createTodo: useMutation({
      mutationFn: (payload: { text: string; deadline_utc?: string | null; deadline_is_date_only?: boolean }) => {
        const shouldSendTimeZone = payload.deadline_utc !== undefined || payload.deadline_is_date_only !== undefined;
        const tz = shouldSendTimeZone ? getUserTimeZone() : undefined;
        return createTodo({
          ...payload,
          time_zone: tz
        });
      },
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: TODOS_QUERY_KEY });
      }
    }).mutateAsync,
    updateTodo: updateMutation.mutate,
    batchComplete,
    deleteTodo: deleteMutation.mutateAsync,
    hasPendingUpdates: pendingUpdatesRef.current.size > 0,
    isUpdating: updateMutation.isPending,
  };
}