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
    mutationFn: (payload: { text: string; deadline_utc?: string | null }) => createTodo(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: TODOS_QUERY_KEY });
    }
  });

  const updateMutation = useMutation({
    mutationFn: (payload: {
      id: number;
      text?: string;
      deadline_utc?: string | null;
      completed?: boolean;
    }) => {
      const timeZone = payload.completed !== undefined ? getUserTimeZone() : undefined;
      return updateTodo(payload.id, {
        text: payload.text,
        deadline_utc: payload.deadline_utc,
        completed: payload.completed,
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
    onSuccess: () => {
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
