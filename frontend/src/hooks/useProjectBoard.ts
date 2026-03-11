import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  createProject,
  createTodo,
  deleteProject,
  deleteTodo,
  dismissProjectSuggestion,
  fetchProjectBoard,
  recomputeProjectSuggestions,
  updateProject,
  updateTodo
} from '../services/api';
import { getUserTimeZone } from '../utils/timeZone';

const PROJECT_BOARD_QUERY_KEY = ['projects', 'board'];
const TODOS_QUERY_KEY = ['todos', 'list'];

export function useProjectBoard() {
  const queryClient = useQueryClient();

  const boardQuery = useQuery({
    queryKey: PROJECT_BOARD_QUERY_KEY,
    queryFn: () => fetchProjectBoard()
  });

  const invalidateAll = async () => {
    await queryClient.invalidateQueries({ queryKey: PROJECT_BOARD_QUERY_KEY });
    await queryClient.invalidateQueries({ queryKey: TODOS_QUERY_KEY });
  };

  const createProjectMutation = useMutation({
    mutationFn: (payload: { name: string; notes?: string | null; sort_order?: number }) =>
      createProject(payload),
    onSuccess: invalidateAll
  });

  const updateProjectMutation = useMutation({
    mutationFn: (payload: {
      id: number;
      name?: string;
      notes?: string | null;
      archived?: boolean;
      sort_order?: number;
    }) => updateProject(payload.id, payload),
    onSuccess: invalidateAll
  });

  const createTodoMutation = useMutation({
    mutationFn: (payload: {
      text: string;
      project_id?: number;
      deadline_utc?: string | null;
      deadline_is_date_only?: boolean;
    }) =>
      createTodo({
        text: payload.text,
        project_id: payload.project_id,
        deadline_utc: payload.deadline_utc,
        deadline_is_date_only: payload.deadline_is_date_only,
        time_zone: getUserTimeZone()
      }),
    onSuccess: invalidateAll
  });

  const updateTodoMutation = useMutation({
    mutationFn: (payload: {
      id: number;
      text?: string;
      project_id?: number;
      deadline_utc?: string | null;
      deadline_is_date_only?: boolean;
      completed?: boolean;
      completed_at_utc?: string | null;
    }) =>
      updateTodo(payload.id, {
        text: payload.text,
        project_id: payload.project_id,
        deadline_utc: payload.deadline_utc,
        deadline_is_date_only: payload.deadline_is_date_only,
        completed: payload.completed,
        completed_at_utc: payload.completed_at_utc,
        time_zone: getUserTimeZone()
      }),
    onSuccess: invalidateAll
  });

  const deleteTodoMutation = useMutation({
    mutationFn: (id: number) => deleteTodo(id),
    onMutate: async (id: number) => {
      await queryClient.cancelQueries({ queryKey: PROJECT_BOARD_QUERY_KEY });
      await queryClient.cancelQueries({ queryKey: TODOS_QUERY_KEY });

      const previousBoard = queryClient.getQueryData<typeof boardQuery.data>(PROJECT_BOARD_QUERY_KEY);
      const previousTodoLists = queryClient.getQueriesData({ queryKey: TODOS_QUERY_KEY });

      queryClient.setQueryData(PROJECT_BOARD_QUERY_KEY, (current: typeof boardQuery.data) => {
        if (!current) return current;
        return {
          ...current,
          todos: current.todos.filter((todo) => todo.id !== id),
          suggestions: current.suggestions.filter((suggestion) => suggestion.todo_id !== id),
          projects: current.projects.map((project) => {
            const todo = current.todos.find((item) => item.id === id);
            if (!todo || project.id !== todo.project_id) {
              return project;
            }
            return {
              ...project,
              open_count: Math.max(0, project.open_count - (todo.completed ? 0 : 1)),
              completed_count: Math.max(0, project.completed_count - (todo.completed ? 1 : 0))
            };
          })
        };
      });

      queryClient.setQueriesData({ queryKey: TODOS_QUERY_KEY }, (current: unknown) => {
        if (!Array.isArray(current)) return current;
        return current.filter((todo) => {
          if (!todo || typeof todo !== 'object' || !('id' in todo)) return true;
          return (todo as { id: number }).id !== id;
        });
      });

      return { previousBoard, previousTodoLists };
    },
    onError: (_error, _id, context) => {
      if (context?.previousBoard !== undefined) {
        queryClient.setQueryData(PROJECT_BOARD_QUERY_KEY, context.previousBoard);
      }
      for (const [queryKey, data] of context?.previousTodoLists ?? []) {
        queryClient.setQueryData(queryKey, data);
      }
    },
    onSettled: invalidateAll
  });

  const deleteProjectMutation = useMutation({
    mutationFn: (id: number) => deleteProject(id),
    onSuccess: invalidateAll
  });

  const recomputeSuggestionsMutation = useMutation({
    mutationFn: (payload: { scope?: 'inbox' | 'all'; todo_ids?: number[] }) =>
      recomputeProjectSuggestions(payload),
    onSuccess: invalidateAll
  });

  const dismissSuggestionMutation = useMutation({
    mutationFn: (todo_id: number) => dismissProjectSuggestion(todo_id),
    onSuccess: invalidateAll
  });

  return {
    boardQuery,
    createProject: createProjectMutation.mutateAsync,
    updateProject: updateProjectMutation.mutateAsync,
    createTodo: createTodoMutation.mutateAsync,
    updateTodo: updateTodoMutation.mutateAsync,
    deleteTodo: deleteTodoMutation.mutateAsync,
    deleteProject: deleteProjectMutation.mutateAsync,
    recomputeSuggestions: recomputeSuggestionsMutation.mutateAsync,
    dismissSuggestion: dismissSuggestionMutation.mutateAsync
  };
}
