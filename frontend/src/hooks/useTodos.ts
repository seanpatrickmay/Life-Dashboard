import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { createTodo, deleteTodo, fetchTodos, updateTodo, type TodoItem } from '../services/api';
import { getUserTimeZone } from '../utils/timeZone';

const TODOS_QUERY_KEY = ['todos', 'list'];

export function useTodos() {
  const queryClient = useQueryClient();

  const timeZone = getUserTimeZone();
  const todosQuery = useQuery<TodoItem[]>({
    queryKey: [...TODOS_QUERY_KEY, timeZone],
    queryFn: () => fetchTodos(timeZone)
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
      return updateTodo(payload.id, {
        text: payload.text,
        deadline_utc: payload.deadline_utc,
        deadline_is_date_only: payload.deadline_is_date_only,
        completed: payload.completed,
        completed_at_utc: payload.completed_at_utc,
        time_zone: timeZone
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: TODOS_QUERY_KEY });
      queryClient.invalidateQueries({ queryKey: ['journal'] });
    }
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteTodo(id),
    onMutate: async (id: number) => {
      await queryClient.cancelQueries({ queryKey: TODOS_QUERY_KEY });
      const previousTodoLists = queryClient.getQueriesData<TodoItem[]>({ queryKey: TODOS_QUERY_KEY });
      queryClient.setQueriesData<TodoItem[]>({ queryKey: TODOS_QUERY_KEY }, (current) =>
        (current ?? []).filter((item) => item.id !== id)
      );
      return { previousTodoLists };
    },
    onError: (_error, _id, context) => {
      for (const [queryKey, data] of context?.previousTodoLists ?? []) {
        queryClient.setQueryData(queryKey, data);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: TODOS_QUERY_KEY });
    }
  });

  return {
    todosQuery,
    createTodo: createMutation.mutateAsync,
    updateTodo: updateMutation.mutateAsync,
    deleteTodo: deleteMutation.mutateAsync
  };
}
