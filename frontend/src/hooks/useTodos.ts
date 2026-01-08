import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { createTodo, deleteTodo, fetchTodos, updateTodo, type TodoItem } from '../services/api';

const TODOS_QUERY_KEY = ['todos', 'list'];

export function useTodos() {
  const queryClient = useQueryClient();

  const todosQuery = useQuery<TodoItem[]>({
    queryKey: TODOS_QUERY_KEY,
    queryFn: fetchTodos
  });

  const createMutation = useMutation({
    mutationFn: (payload: { text: string; deadline_utc?: string | null }) => createTodo(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: TODOS_QUERY_KEY });
    }
  });

  const updateMutation = useMutation({
    mutationFn: (payload: { id: number; text?: string; deadline_utc?: string | null; completed?: boolean }) =>
      updateTodo(payload.id, {
        text: payload.text,
        deadline_utc: payload.deadline_utc,
        completed: payload.completed
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: TODOS_QUERY_KEY });
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

