// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
import { act, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { renderWithProviders } from '../../test/renderWithProviders';
import { QuickCapture } from './QuickCapture';

// ── Mock hooks ───────────────────────────────────────────────────────────────

const mockCreateTodoInbox = vi.fn();
const mockCreateTodoBoard = vi.fn();

vi.mock('../../hooks/useTodos', () => ({
  useTodos: () => ({
    createTodo: mockCreateTodoInbox,
    todosQuery: { data: [], isLoading: false },
    updateTodo: vi.fn(),
    deleteTodo: vi.fn(),
    batchUpdateTodos: vi.fn(),
    isUpdating: false,
  }),
}));

vi.mock('../../hooks/useProjectBoard', () => ({
  useProjectBoard: () => ({
    boardQuery: {
      data: {
        projects: [
          {
            id: 1,
            name: 'Life Dashboard',
            display_name: null,
            notes: null,
            archived: false,
            sort_order: 0,
            created_at: '2024-01-01',
            updated_at: '2024-01-01',
            open_count: 2,
            completed_count: 1,
          },
          {
            id: 2,
            name: 'Side Project',
            display_name: null,
            notes: null,
            archived: false,
            sort_order: 1,
            created_at: '2024-01-01',
            updated_at: '2024-01-01',
            open_count: 0,
            completed_count: 0,
          },
        ],
        todos: [],
        suggestions: [],
      },
      isLoading: false,
    },
    createTodo: mockCreateTodoBoard,
    createProject: vi.fn(),
    updateProject: vi.fn(),
    updateTodo: vi.fn(),
    deleteTodo: vi.fn(),
    deleteProject: vi.fn(),
    recomputeSuggestions: vi.fn(),
    dismissSuggestion: vi.fn(),
  }),
}));

// ── Tests ────────────────────────────────────────────────────────────────────

describe('QuickCapture', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockCreateTodoInbox.mockResolvedValue({});
    mockCreateTodoBoard.mockResolvedValue({});
  });

  it('renders the text input and project select', () => {
    renderWithProviders(<QuickCapture />);
    expect(screen.getByRole('textbox', { name: /add a task/i })).toBeInTheDocument();
    expect(screen.getByRole('combobox', { name: /project/i })).toBeInTheDocument();
  });

  it('renders Inbox as the default project option', () => {
    renderWithProviders(<QuickCapture />);
    expect(screen.getByRole('combobox', { name: /project/i })).toHaveValue('inbox');
  });

  it('lists user projects in the select', () => {
    renderWithProviders(<QuickCapture />);
    expect(screen.getByRole('option', { name: 'Inbox' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Life Dashboard' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Side Project' })).toBeInTheDocument();
  });

  it('submits with Enter key and calls inbox createTodo (no project_id) when Inbox is selected', async () => {
    renderWithProviders(<QuickCapture />);
    const input = screen.getByRole('textbox', { name: /add a task/i });
    fireEvent.change(input, { target: { value: 'Buy groceries' } });
    fireEvent.keyDown(input, { key: 'Enter' });

    await waitFor(() => {
      expect(mockCreateTodoInbox).toHaveBeenCalledTimes(1);
      expect(mockCreateTodoInbox).toHaveBeenCalledWith({ text: 'Buy groceries' });
    });
    expect(mockCreateTodoBoard).not.toHaveBeenCalled();
  });

  it('submits via the add button and calls inbox createTodo', async () => {
    renderWithProviders(<QuickCapture />);
    const input = screen.getByRole('textbox', { name: /add a task/i });
    fireEvent.change(input, { target: { value: 'Read a book' } });
    fireEvent.click(screen.getByRole('button', { name: /add task/i }));

    await waitFor(() => {
      expect(mockCreateTodoInbox).toHaveBeenCalledTimes(1);
      expect(mockCreateTodoInbox).toHaveBeenCalledWith({ text: 'Read a book' });
    });
  });

  it('calls board createTodo with project_id when a project is selected', async () => {
    renderWithProviders(<QuickCapture />);
    const select = screen.getByRole('combobox', { name: /project/i });
    fireEvent.change(select, { target: { value: '1' } });

    const input = screen.getByRole('textbox', { name: /add a task/i });
    fireEvent.change(input, { target: { value: 'Fix the bug' } });
    fireEvent.keyDown(input, { key: 'Enter' });

    await waitFor(() => {
      expect(mockCreateTodoBoard).toHaveBeenCalledTimes(1);
      expect(mockCreateTodoBoard).toHaveBeenCalledWith({ text: 'Fix the bug', project_id: 1 });
    });
    expect(mockCreateTodoInbox).not.toHaveBeenCalled();
  });

  it('does NOT call create when input is empty', async () => {
    renderWithProviders(<QuickCapture />);
    const input = screen.getByRole('textbox', { name: /add a task/i });
    fireEvent.keyDown(input, { key: 'Enter' });
    await waitFor(() => {
      expect(mockCreateTodoInbox).not.toHaveBeenCalled();
      expect(mockCreateTodoBoard).not.toHaveBeenCalled();
    });
  });

  it('does NOT call create when input is whitespace-only', async () => {
    renderWithProviders(<QuickCapture />);
    const input = screen.getByRole('textbox', { name: /add a task/i });
    fireEvent.change(input, { target: { value: '   ' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    await waitFor(() => {
      expect(mockCreateTodoInbox).not.toHaveBeenCalled();
      expect(mockCreateTodoBoard).not.toHaveBeenCalled();
    });
  });

  it('clears the input after a successful submit', async () => {
    renderWithProviders(<QuickCapture />);
    const input = screen.getByRole('textbox', { name: /add a task/i });
    fireEvent.change(input, { target: { value: 'Do the thing' } });
    fireEvent.keyDown(input, { key: 'Enter' });

    await waitFor(() => {
      expect(input).toHaveValue('');
    });
  });

  it('retains the selected project after submit so the user can add multiple tasks', async () => {
    renderWithProviders(<QuickCapture />);
    const select = screen.getByRole('combobox', { name: /project/i });
    fireEvent.change(select, { target: { value: '2' } });

    const input = screen.getByRole('textbox', { name: /add a task/i });
    fireEvent.change(input, { target: { value: 'Task one' } });
    fireEvent.keyDown(input, { key: 'Enter' });

    await waitFor(() => {
      expect(input).toHaveValue('');
    });
    // Project select should still be on "Side Project" (id=2)
    expect(select).toHaveValue('2');
  });

  it('disables input and button while mutation is pending', async () => {
    // Make createTodo hang so we can inspect the pending state
    let resolveFn!: () => void;
    mockCreateTodoInbox.mockImplementation(
      () => new Promise<void>((resolve) => { resolveFn = resolve; })
    );

    renderWithProviders(<QuickCapture />);
    const input = screen.getByRole('textbox', { name: /add a task/i });
    fireEvent.change(input, { target: { value: 'Pending task' } });
    fireEvent.keyDown(input, { key: 'Enter' });

    await waitFor(() => {
      expect(input).toBeDisabled();
      expect(screen.getByRole('button', { name: /add task/i })).toBeDisabled();
    });

    // Resolve the pending promise inside act() so the final setIsPending(false)
    // state update is flushed before teardown (prevents act() warning).
    await act(async () => { resolveFn(); });
  });

  it('shows an error message when create fails', async () => {
    mockCreateTodoInbox.mockRejectedValue(new Error('network'));

    renderWithProviders(<QuickCapture />);
    const input = screen.getByRole('textbox', { name: /add a task/i });
    fireEvent.change(input, { target: { value: 'Doomed task' } });
    fireEvent.keyDown(input, { key: 'Enter' });

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Failed to add task — please try again.');
  });
});
