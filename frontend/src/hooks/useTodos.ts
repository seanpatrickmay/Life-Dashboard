import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useRef, useCallback } from 'react';
import { createTodo, deleteTodo, fetchTodos, updateTodo, type TodoItem } from '../services/api';
import { getUserTimeZone } from '../utils/timeZone';

const TODOS_QUERY_KEY = ['todos', 'list'];

export function useTodos() {
  const queryClient = useQueryClient();
  const invalidateTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingUpdatesRef = useRef<Set<number>>(new Set());

  // Debounced invalidation to prevent multiple refreshes
  const debouncedInvalidate = useCallback(() => {
    if (invalidateTimerRef.current) {
      clearTimeout(invalidateTimerRef.current);
    }

    invalidateTimerRef.current = setTimeout(() => {
      // Only invalidate if no pending updates
      if (pendingUpdatesRef.current.size === 0) {
        queryClient.invalidateQueries({ queryKey: TODOS_QUERY_KEY });
        queryClient.invalidateQueries({ queryKey: ['journal'] });
      }
      invalidateTimerRef.current = null;
    }, 300); // Wait 300ms after last update
  }, [queryClient]);

  const timeZone = getUserTimeZone();
  const todosQuery = useQuery<TodoItem[]>({
    queryKey: [...TODOS_QUERY_KEY, timeZone],
    queryFn: () => fetchTodos(timeZone),
    staleTime: 30_000, // Consider data fresh for 30 seconds
    refetchInterval: false, // Disable auto-refetch
  });

  const createMutation = useMutation({
    mutationFn: (payload: { text: string; deadline_utc?: string | null; deadline_is_date_only?: boolean }) => {
      const shouldSendTimeZone = payload.deadline_utc !== undefined || payload.deadline_is_date_only !== undefined;
      const timeZone = shouldSendTimeZone ? getUserTimeZone() : undefined;
      return createTodo({
        text: payload.text,
        deadline_utc: payload.deadline_utc,
        deadline_is_date_only: payload.deadline_is_date_only,
        time_zone: timeZone
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: TODOS_QUERY_KEY });
    }
  });

  const updateMutation = useMutation({
    mutationFn: (payload: {
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
      const timeZone = shouldSendTimeZone ? getUserTimeZone() : undefined;

      // Track this update
      pendingUpdatesRef.current.add(payload.id);

      return updateTodo(payload.id, {
        text: payload.text,
        deadline_utc: payload.deadline_utc,
        deadline_is_date_only: payload.deadline_is_date_only,
        completed: payload.completed,
        completed_at_utc: payload.completed_at_utc,
        time_zone: timeZone
      }).finally(() => {
        // Remove from pending when done
        pendingUpdatesRef.current.delete(payload.id);
      });
    },
    onMutate: async (payload) => {
      // Cancel any outgoing refetches to prevent conflicts
      await queryClient.cancelQueries({ queryKey: TODOS_QUERY_KEY });

      // Get current data for rollback
      const previousTodoLists = queryClient.getQueriesData<TodoItem[]>({ queryKey: TODOS_QUERY_KEY });

      // Optimistically update the cache immediately
      queryClient.setQueriesData<TodoItem[]>({ queryKey: TODOS_QUERY_KEY }, (current) => {
        if (!current) return current;

        return current.map(item => {
          if (item.id !== payload.id) return item;

          // Merge updates with existing item
          const updated = { ...item };

          if (payload.text !== undefined) updated.text = payload.text;
          if (payload.deadline_utc !== undefined) updated.deadline_utc = payload.deadline_utc;
          if (payload.deadline_is_date_only !== undefined) updated.deadline_is_date_only = payload.deadline_is_date_only;

          if (payload.completed !== undefined) {
            updated.completed = payload.completed;
            // Add completed_at if marking complete and not provided
            if (payload.completed && !payload.completed_at_utc && !item.completed_at_utc) {
              updated.completed_at_utc = new Date().toISOString();
            } else if (payload.completed_at_utc !== undefined) {
              updated.completed_at_utc = payload.completed_at_utc;
            }

            // Update is_overdue flag
            if (updated.deadline_utc) {
              updated.is_overdue = !updated.completed && new Date(updated.deadline_utc) < new Date();
            }
          }

          return updated;
        });
      });

      // Return context for potential rollback
      return { previousTodoLists };
    },
    onError: (_error, _payload, context) => {
      // Rollback optimistic update on error
      if (context?.previousTodoLists) {
        for (const [queryKey, data] of context.previousTodoLists) {
          queryClient.setQueryData(queryKey, data);
        }
      }
    },
    onSuccess: () => {
      // Use debounced invalidation instead of immediate
      debouncedInvalidate();
    },
    // Remove onSettled to prevent immediate invalidation
    retry: 1, // Retry once on failure
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteTodo(id),
    onMutate: async (id: number) => {
      await queryClient.cancelQueries({ queryKey: TODOS_QUERY_KEY });
      const previousTodoLists = queryClient.getQueriesData<TodoItem[]>({ queryKey: TODOS_QUERY_KEY });

      // Optimistically remove the item
      queryClient.setQueriesData<TodoItem[]>({ queryKey: TODOS_QUERY_KEY }, (current) =>
        (current ?? []).filter((item) => item.id !== id)
      );

      return { previousTodoLists };
    },
    onError: (_error, _id, context) => {
      // Rollback on error
      for (const [queryKey, data] of context?.previousTodoLists ?? []) {
        queryClient.setQueryData(queryKey, data);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: TODOS_QUERY_KEY });
    }
  });

  // Batch update function for multiple todos
  const batchUpdateTodos = useCallback((updates: Array<{
    id: number;
    completed?: boolean;
    text?: string;
  }>) => {
    // Update all items optimistically at once
    queryClient.setQueriesData<TodoItem[]>({ queryKey: TODOS_QUERY_KEY }, (current) => {
      if (!current) return current;

      const updateMap = new Map(updates.map(u => [u.id, u]));

      return current.map(item => {
        const update = updateMap.get(item.id);
        if (!update) return item;

        return {
          ...item,
          ...update,
          completed_at_utc: update.completed && !item.completed_at_utc
            ? new Date().toISOString()
            : item.completed_at_utc
        };
      });
    });

    // Send individual updates without triggering immediate invalidation
    updates.forEach(update => {
      updateMutation.mutate(update);
    });
  }, [queryClient, updateMutation]);

  return {
    todosQuery,
    createTodo: createMutation.mutateAsync,
    updateTodo: updateMutation.mutate,
    batchUpdateTodos,
    deleteTodo: deleteMutation.mutateAsync,
    isUpdating: updateMutation.isPending || pendingUpdatesRef.current.size > 0
  };
}