import { FormEvent, useEffect, useMemo, useRef, useState } from 'react';
import styled from 'styled-components';

import { Card } from '../components/common/Card';
import { useProjectBoard } from '../hooks/useProjectBoard';
import type { ProjectItem, TodoItem } from '../services/api';

const Page = styled.div`
  display: grid;
  gap: 16px;
  min-width: 0;
  overflow-x: hidden;
`;

const Header = styled(Card)`
  display: grid;
  gap: 12px;
`;

const HeaderRow = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  justify-content: space-between;
`;

const Title = styled.h1`
  margin: 0;
  font-family: ${({ theme }) => theme.fonts.heading};
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-size: 1rem;
`;

const ActionRow = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
`;

const Input = styled.input`
  border: 1px solid rgba(255, 255, 255, 0.25);
  background: rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  color: ${({ theme }) => theme.colors.textPrimary};
  padding: 8px 10px;
`;

const TextArea = styled.textarea`
  border: 1px solid rgba(255, 255, 255, 0.25);
  background: rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  color: ${({ theme }) => theme.colors.textPrimary};
  padding: 8px 10px;
  min-height: 68px;
`;

const Button = styled.button`
  border: 1px solid rgba(255, 255, 255, 0.25);
  background: rgba(255, 255, 255, 0.16);
  color: ${({ theme }) => theme.colors.textPrimary};
  border-radius: 999px;
  padding: 7px 12px;
  cursor: pointer;
  font-family: ${({ theme }) => theme.fonts.heading};
  letter-spacing: 0.1em;
  text-transform: uppercase;
  font-size: 0.68rem;

  &:disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }
`;

const DangerButton = styled(Button)`
  border-color: rgba(246, 126, 126, 0.55);
  background: rgba(246, 126, 126, 0.2);
`;

const SuggestionList = styled.div`
  display: grid;
  gap: 8px;
`;

const SuggestionRow = styled.div`
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 12px;
  padding: 10px;
  display: grid;
  gap: 8px;
`;

const SuggestionTop = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
`;

const Confidence = styled.span<{ $confidence: number }>`
  padding: 3px 8px;
  border-radius: 999px;
  font-size: 0.72rem;
  border: 1px solid
    ${({ $confidence }) =>
      $confidence >= 0.75
        ? 'rgba(120, 224, 163, 0.7)'
        : $confidence >= 0.5
          ? 'rgba(244, 212, 128, 0.7)'
          : 'rgba(246, 126, 126, 0.7)'};
  background: ${({ $confidence }) =>
    $confidence >= 0.75
      ? 'rgba(120, 224, 163, 0.12)'
      : $confidence >= 0.5
        ? 'rgba(244, 212, 128, 0.14)'
        : 'rgba(246, 126, 126, 0.12)'};
`;

const ProjectTabs = styled.div`
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding-bottom: 4px;
`;

const ProjectTabButton = styled.button<{ $active: boolean }>`
  border: 1px solid ${({ $active }) => ($active ? 'rgba(137, 189, 255, 0.75)' : 'rgba(255, 255, 255, 0.2)')};
  background: ${({ $active }) => ($active ? 'rgba(137, 189, 255, 0.18)' : 'rgba(255, 255, 255, 0.08)')};
  color: ${({ theme }) => theme.colors.textPrimary};
  border-radius: 999px;
  padding: 7px 11px;
  cursor: pointer;
  white-space: nowrap;
  font-size: 0.72rem;
`;

const SelectedProjectWrap = styled.div`
  display: grid;
  gap: 12px;
  min-width: 0;
`;

const WorkspaceRow = styled.div`
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(280px, 0.95fr);
  gap: 12px;
  align-items: start;

  @media (max-width: 980px) {
    grid-template-columns: 1fr;
  }
`;

const WorkspaceCard = styled(Card)`
  min-width: 0;
`;

const ProjectCard = styled(Card)`
  display: grid;
  gap: 10px;
  min-width: 0;
`;

const TodoList = styled.div`
  display: grid;
  gap: 6px;
`;

const TodoRow = styled.div`
  display: grid;
  gap: 8px;
  align-items: center;
  padding: 8px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.03);
`;

const TodoMain = styled.div`
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 8px;
  align-items: center;
  grid-column: 1 / -1;
  min-width: 0;
`;

const TodoMetaRow = styled.div`
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 220px) auto;
  gap: 8px;
  align-items: center;
  grid-column: 1 / -1;
  min-width: 0;

  @media (max-width: 1024px) {
    grid-template-columns: minmax(0, 1fr) minmax(140px, 220px);
  }

  @media (max-width: 760px) {
    grid-template-columns: 1fr;
  }
`;

const DueBadge = styled.span<{ $kind: 'overdue' | 'soon' | 'scheduled' | 'none' }>`
  font-size: 0.72rem;
  padding: 4px 8px;
  border-radius: 999px;
  width: fit-content;
  border: 1px solid
    ${({ $kind }) =>
      $kind === 'overdue'
        ? 'rgba(246, 126, 126, 0.75)'
        : $kind === 'soon'
          ? 'rgba(244, 212, 128, 0.75)'
          : $kind === 'scheduled'
            ? 'rgba(137, 189, 255, 0.75)'
            : 'rgba(255, 255, 255, 0.24)'};
  background: ${({ $kind }) =>
    $kind === 'overdue'
      ? 'rgba(246, 126, 126, 0.15)'
      : $kind === 'soon'
        ? 'rgba(244, 212, 128, 0.15)'
        : $kind === 'scheduled'
          ? 'rgba(137, 189, 255, 0.15)'
          : 'rgba(255, 255, 255, 0.05)'};
`;

const Muted = styled.div`
  opacity: 0.75;
  font-size: 0.85rem;
`;

const TodoText = styled.input`
  border: 1px solid rgba(255, 255, 255, 0.2);
  background: rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  color: ${({ theme }) => theme.colors.textPrimary};
  padding: 6px 8px;
  min-width: 0;
`;

const Select = styled.select`
  border: 1px solid rgba(255, 255, 255, 0.2);
  background: rgba(0, 0, 0, 0.25);
  border-radius: 8px;
  color: ${({ theme }) => theme.colors.textPrimary};
  padding: 6px;
  width: 100%;
  min-width: 0;
`;

const TodoDeleteButton = styled(DangerButton)`
  justify-self: start;
  width: auto;

  @media (max-width: 1024px) {
    grid-column: 1 / -1;
  }
`;

const ProjectSummary = styled.div`
  display: grid;
  gap: 4px;
`;

const ProjectName = styled.div`
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.9rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
`;

const ProjectNotes = styled.div`
  opacity: 0.85;
  font-size: 0.86rem;
  line-height: 1.35;
`;

const Banner = styled.div<{ $kind: 'info' | 'success' | 'error' }>`
  border-radius: 12px;
  border: 1px solid
    ${({ $kind }) =>
      $kind === 'success'
        ? 'rgba(120, 224, 163, 0.65)'
        : $kind === 'error'
          ? 'rgba(246, 126, 126, 0.65)'
          : 'rgba(137, 189, 255, 0.65)'};
  background: ${({ $kind }) =>
    $kind === 'success'
      ? 'rgba(120, 224, 163, 0.13)'
      : $kind === 'error'
        ? 'rgba(246, 126, 126, 0.13)'
        : 'rgba(137, 189, 255, 0.12)'};
  padding: 9px 10px;
  display: flex;
  gap: 10px;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
`;

type StatusBanner = {
  kind: 'info' | 'success' | 'error';
  message: string;
  undo?: () => void;
};

type PendingCommit = {
  label: string;
  run: () => Promise<void>;
};

const projectSortKey = (project: ProjectItem) =>
  `${project.name.toLowerCase() === 'inbox' ? '0' : '1'}-${project.sort_order}-${project.id}`;

export function ProjectsPage() {
  const {
    boardQuery,
    createProject,
    updateProject,
    createTodo,
    updateTodo,
    deleteTodo,
    deleteProject,
    recomputeSuggestions,
    dismissSuggestion
  } = useProjectBoard();

  const [newProjectName, setNewProjectName] = useState('');
  const [newProjectNotes, setNewProjectNotes] = useState('');
  const [todoDrafts, setTodoDrafts] = useState<Record<number, string>>({});
  const [editCache, setEditCache] = useState<Record<number, string>>({});
  const [showCompletedByProject, setShowCompletedByProject] = useState<Record<number, boolean>>({});
  const [editingProjectId, setEditingProjectId] = useState<number | null>(null);
  const [projectDrafts, setProjectDrafts] = useState<Record<number, { name: string; notes: string }>>({});
  const [isResuggesting, setIsResuggesting] = useState(false);
  const [status, setStatus] = useState<StatusBanner | null>(null);
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null);
  const pendingCommitRef = useRef<PendingCommit | null>(null);
  const pendingCommitTimerRef = useRef<number | null>(null);

  const board = boardQuery.data;
  const todosById = useMemo(() => {
    const map = new Map<number, TodoItem>();
    for (const todo of board?.todos ?? []) {
      map.set(todo.id, todo);
    }
    return map;
  }, [board?.todos]);

  useEffect(() => {
    return () => {
      if (pendingCommitTimerRef.current !== null) {
        window.clearTimeout(pendingCommitTimerRef.current);
      }
      if (pendingCommitRef.current) {
        void pendingCommitRef.current.run();
      }
    };
  }, []);

  const clearPendingCommit = () => {
    if (pendingCommitTimerRef.current !== null) {
      window.clearTimeout(pendingCommitTimerRef.current);
      pendingCommitTimerRef.current = null;
    }
    pendingCommitRef.current = null;
  };

  const queueUndoableAction = (pending: PendingCommit) => {
    if (pendingCommitRef.current) {
      const previous = pendingCommitRef.current;
      clearPendingCommit();
      void previous.run();
    }
    pendingCommitRef.current = pending;
    pendingCommitTimerRef.current = window.setTimeout(() => {
      const current = pendingCommitRef.current;
      clearPendingCommit();
      if (!current) return;
      void current
        .run()
        .then(() => {
          setStatus({ kind: 'success', message: `${pending.label} complete.` });
        })
        .catch(() => {
          setStatus({ kind: 'error', message: `${pending.label} failed.` });
        });
    }, 5000);
    setStatus({
      kind: 'info',
      message: `${pending.label} in 5 seconds.`,
      undo: () => {
        clearPendingCommit();
        setStatus({ kind: 'info', message: `${pending.label} canceled.` });
      }
    });
  };

  const projects = useMemo(
    () => [...(board?.projects ?? [])].sort((left, right) => projectSortKey(left).localeCompare(projectSortKey(right))),
    [board?.projects]
  );
  const selectedProject =
    projects.find((project) => project.id === selectedProjectId) ?? projects[0] ?? null;

  useEffect(() => {
    if (projects.length === 0) {
      setSelectedProjectId(null);
      return;
    }
    const stillExists = projects.some((project) => project.id === selectedProjectId);
    if (!stillExists) {
      setSelectedProjectId(projects[0].id);
    }
  }, [projects, selectedProjectId]);

  const todosByProject = useMemo(() => {
    const map = new Map<number, TodoItem[]>();
    for (const todo of board?.todos ?? []) {
      const list = map.get(todo.project_id) ?? [];
      list.push(todo);
      map.set(todo.project_id, list);
    }
    return map;
  }, [board?.todos]);

  const handleCreateProject = async (event: FormEvent) => {
    event.preventDefault();
    const name = newProjectName.trim();
    if (!name) return;
    await createProject({ name, notes: newProjectNotes.trim() || null });
    setNewProjectName('');
    setNewProjectNotes('');
    setStatus({ kind: 'success', message: 'Project created.' });
  };

  const handleCreateTodo = async (projectId: number) => {
    const text = (todoDrafts[projectId] ?? '').trim();
    if (!text) return;
    await createTodo({ text, project_id: projectId });
    setTodoDrafts((prev) => ({ ...prev, [projectId]: '' }));
    setStatus({ kind: 'success', message: 'Todo added.' });
  };

  const applySuggestion = async (todoId: number, projectName: string) => {
    const existing = projects.find(
      (project) => project.name.trim().toLowerCase() === projectName.trim().toLowerCase()
    );
    const project = existing ?? (await createProject({ name: projectName.trim() }));
    await updateTodo({ id: todoId, project_id: project.id });
    await dismissSuggestion(todoId);
    setStatus({ kind: 'success', message: 'Suggestion applied.' });
  };

  const handleReSuggestInbox = async () => {
    setIsResuggesting(true);
    try {
      const response = await recomputeSuggestions({ scope: 'inbox' });
      setStatus({
        kind: 'success',
        message: `${response.scheduled_count} inbox todo${response.scheduled_count === 1 ? '' : 's'} queued for suggestion.`
      });
    } catch {
      setStatus({ kind: 'error', message: 'Could not queue suggestions.' });
    } finally {
      setIsResuggesting(false);
    }
  };

  const startEditProject = (project: ProjectItem) => {
    setEditingProjectId(project.id);
    setProjectDrafts((prev) => ({
      ...prev,
      [project.id]: {
        name: project.name,
        notes: project.notes ?? ''
      }
    }));
  };

  const saveProject = async (project: ProjectItem) => {
    const draft = projectDrafts[project.id];
    if (!draft) {
      setEditingProjectId(null);
      return;
    }
    const nextName = draft.name.trim();
    const nextNotes = draft.notes.trim();
    if (!nextName) {
      setStatus({ kind: 'error', message: 'Project name cannot be empty.' });
      return;
    }
    await updateProject({
      id: project.id,
      name: nextName,
      notes: nextNotes || null
    });
    setEditingProjectId(null);
    setStatus({ kind: 'success', message: 'Project updated.' });
  };

  const getDueMeta = (todo: TodoItem): { kind: 'overdue' | 'soon' | 'scheduled' | 'none'; label: string } => {
    if (!todo.deadline_utc) return { kind: 'none', label: 'No due date' };
    const now = Date.now();
    const due = new Date(todo.deadline_utc).getTime();
    if (Number.isNaN(due)) return { kind: 'none', label: 'No due date' };
    if (!todo.completed && due < now) return { kind: 'overdue', label: 'Overdue' };
    const dayMs = 24 * 60 * 60 * 1000;
    if (due - now <= dayMs) return { kind: 'soon', label: 'Due soon' };
    return { kind: 'scheduled', label: new Date(todo.deadline_utc).toLocaleString() };
  };

  const sortTodos = (todos: TodoItem[]) => {
    const toRank = (todo: TodoItem) => {
      if (todo.completed) return 4;
      if (todo.is_overdue) return 0;
      if (!todo.deadline_utc) return 3;
      const due = new Date(todo.deadline_utc).getTime();
      const now = Date.now();
      const dayMs = 24 * 60 * 60 * 1000;
      if (due - now <= dayMs) return 1;
      return 2;
    };
    return [...todos].sort((left, right) => {
      const rankDiff = toRank(left) - toRank(right);
      if (rankDiff !== 0) return rankDiff;
      const leftDue = left.deadline_utc ? new Date(left.deadline_utc).getTime() : Number.MAX_SAFE_INTEGER;
      const rightDue = right.deadline_utc ? new Date(right.deadline_utc).getTime() : Number.MAX_SAFE_INTEGER;
      return leftDue - rightDue;
    });
  };

  if (boardQuery.isLoading) {
    return <Muted>Loading projects...</Muted>;
  }

  return (
    <Page>
      <Header>
        <HeaderRow>
          <Title data-halo="heading">Projects</Title>
          <ActionRow>
            <Button type="button" onClick={handleReSuggestInbox} disabled={isResuggesting}>
              {isResuggesting ? 'Queueing…' : 'Re-suggest Inbox'}
            </Button>
          </ActionRow>
        </HeaderRow>
        {status ? (
          <Banner $kind={status.kind}>
            <span>{status.message}</span>
            {status.undo ? (
              <Button type="button" onClick={status.undo}>
                Undo
              </Button>
            ) : null}
          </Banner>
        ) : null}
        <form onSubmit={handleCreateProject}>
          <ActionRow>
            <Input
              value={newProjectName}
              onChange={(event) => setNewProjectName(event.target.value)}
              placeholder="New project name"
            />
            <Input
              value={newProjectNotes}
              onChange={(event) => setNewProjectNotes(event.target.value)}
              placeholder="Project notes (optional)"
            />
            <Button type="submit">Create Project</Button>
          </ActionRow>
        </form>
      </Header>

      <Card>
        <HeaderRow>
          <Title data-halo="heading">Project Selector</Title>
          <Muted>{projects.length} total</Muted>
        </HeaderRow>
        <ProjectTabs>
          {projects.map((project) => (
            <ProjectTabButton
              key={project.id}
              type="button"
              $active={selectedProject?.id === project.id}
              onClick={() => setSelectedProjectId(project.id)}
            >
              {project.name} ({project.open_count}/{project.completed_count})
            </ProjectTabButton>
          ))}
        </ProjectTabs>
      </Card>

      <WorkspaceRow>
        {selectedProject ? (
          <SelectedProjectWrap>
            {(() => {
              const project = selectedProject;
              const projectTodos = todosByProject.get(project.id) ?? [];
              const showCompleted = !!showCompletedByProject[project.id];
              const visibleTodos = showCompleted
                ? sortTodos(projectTodos)
                : sortTodos(projectTodos.filter((item) => !item.completed));
              const isEditingProject = editingProjectId === project.id;
              const draft = projectDrafts[project.id];
              return (
                <ProjectCard key={project.id}>
                <HeaderRow>
                  <ProjectName data-halo="heading">{project.name}</ProjectName>
                  <Muted>
                    {project.open_count} open / {project.completed_count} done
                  </Muted>
                </HeaderRow>
                {isEditingProject ? (
                  <>
                    <Input
                      value={draft?.name ?? project.name}
                      onChange={(event) =>
                        setProjectDrafts((prev) => ({
                          ...prev,
                          [project.id]: {
                            name: event.target.value,
                            notes: prev[project.id]?.notes ?? project.notes ?? ''
                          }
                        }))
                      }
                    />
                    <TextArea
                      value={draft?.notes ?? project.notes ?? ''}
                      onChange={(event) =>
                        setProjectDrafts((prev) => ({
                          ...prev,
                          [project.id]: {
                            name: prev[project.id]?.name ?? project.name,
                            notes: event.target.value
                          }
                        }))
                      }
                    />
                  </>
                ) : (
                  <ProjectSummary>
                    <ProjectName>{project.name}</ProjectName>
                    <ProjectNotes>{project.notes || 'No project notes yet.'}</ProjectNotes>
                  </ProjectSummary>
                )}
                <ActionRow>
                  {isEditingProject ? (
                    <>
                      <Button type="button" onClick={() => saveProject(project)}>
                        Save Project
                      </Button>
                      <Button type="button" onClick={() => setEditingProjectId(null)}>
                        Cancel
                      </Button>
                    </>
                  ) : (
                    <Button type="button" onClick={() => startEditProject(project)}>
                      Edit Project
                    </Button>
                  )}
                  <Button
                    type="button"
                    onClick={() =>
                      setShowCompletedByProject((prev) => ({ ...prev, [project.id]: !prev[project.id] }))
                    }
                  >
                    {showCompleted ? 'Hide Completed' : 'Show Completed'}
                  </Button>
                  {project.name.toLowerCase() !== 'inbox' ? (
                    <DangerButton
                      type="button"
                      onClick={() => {
                        const confirmed = window.confirm(`Archive project "${project.name}"?`);
                        if (!confirmed) return;
                        queueUndoableAction({
                          label: `Archive "${project.name}"`,
                          run: () => updateProject({ id: project.id, archived: true })
                        });
                      }}
                    >
                      Archive
                    </DangerButton>
                  ) : null}
                  {project.name.toLowerCase() !== 'inbox' ? (
                    <DangerButton
                      type="button"
                      onClick={async () => {
                        const confirmed = window.confirm(
                          `Delete project "${project.name}"? Todos will move to Inbox.`
                        );
                        if (!confirmed) return;
                        await deleteProject(project.id);
                        setStatus({
                          kind: 'success',
                          message: `Project "${project.name}" deleted. Todos moved to Inbox.`
                        });
                      }}
                    >
                      Delete Project
                    </DangerButton>
                  ) : null}
                </ActionRow>
                <ActionRow>
                  <Input
                    value={todoDrafts[project.id] ?? ''}
                    onChange={(event) => setTodoDrafts((prev) => ({ ...prev, [project.id]: event.target.value }))}
                    placeholder="Add todo to this project"
                  />
                  <Button type="button" onClick={() => handleCreateTodo(project.id)}>
                    Add
                  </Button>
                </ActionRow>
                <TodoList>
                  {visibleTodos.map((todo) => (
                    <TodoRow key={todo.id}>
                      <TodoMain>
                        <input
                          type="checkbox"
                          checked={todo.completed}
                          onChange={() => updateTodo({ id: todo.id, completed: !todo.completed })}
                        />
                        <TodoText
                          value={editCache[todo.id] ?? todo.text}
                          onChange={(event) => setEditCache((prev) => ({ ...prev, [todo.id]: event.target.value }))}
                          onBlur={() => {
                            const draftText = editCache[todo.id];
                            if (!draftText) return;
                            const next = draftText.trim();
                            if (next && next !== todo.text) {
                              void updateTodo({ id: todo.id, text: next });
                            }
                            setEditCache((prev) => {
                              const nextCache = { ...prev };
                              delete nextCache[todo.id];
                              return nextCache;
                            });
                          }}
                        />
                      </TodoMain>
                      <TodoMetaRow>
                        {(() => {
                          const dueMeta = getDueMeta(todo);
                          return <DueBadge $kind={dueMeta.kind}>{dueMeta.label}</DueBadge>;
                        })()}
                        <Select
                          value={todo.project_id}
                          onChange={(event) => updateTodo({ id: todo.id, project_id: Number(event.target.value) })}
                        >
                          {projects.map((option) => (
                            <option key={option.id} value={option.id}>
                              {option.name}
                            </option>
                          ))}
                        </Select>
                        <TodoDeleteButton
                          type="button"
                          onClick={() => {
                            const confirmed = window.confirm('Delete this todo?');
                            if (!confirmed) return;
                            queueUndoableAction({
                              label: 'Delete todo',
                              run: () => deleteTodo(todo.id)
                            });
                          }}
                        >
                          Delete
                        </TodoDeleteButton>
                      </TodoMetaRow>
                    </TodoRow>
                  ))}
                  {visibleTodos.length === 0 ? <Muted>No todos in this view.</Muted> : null}
                </TodoList>
                </ProjectCard>
              );
            })()}
          </SelectedProjectWrap>
        ) : (
          <WorkspaceCard>
            <Muted>No projects available yet.</Muted>
          </WorkspaceCard>
        )}

        <WorkspaceCard>
          <HeaderRow>
            <Title data-halo="heading">Suggestions</Title>
            <Muted>{board?.suggestions.length ?? 0} pending</Muted>
          </HeaderRow>
          {board?.suggestions.length ? (
            <SuggestionList>
              {board.suggestions.map((item) => (
                <SuggestionRow key={item.todo_id}>
                  <SuggestionTop>
                    <Muted>
                      Todo #{item.todo_id} {'->'} {item.suggested_project_name}
                    </Muted>
                    <Confidence $confidence={item.confidence}>
                      {Math.round(item.confidence * 100)}%
                    </Confidence>
                  </SuggestionTop>
                  <Muted>{todosById.get(item.todo_id)?.text ?? 'Todo not found'}</Muted>
                  {item.reason ? <Muted>{item.reason}</Muted> : null}
                  <ActionRow>
                    <Button type="button" onClick={() => applySuggestion(item.todo_id, item.suggested_project_name)}>
                      Apply
                    </Button>
                    <Button type="button" onClick={() => dismissSuggestion(item.todo_id)}>
                      Dismiss
                    </Button>
                  </ActionRow>
                </SuggestionRow>
              ))}
            </SuggestionList>
          ) : (
            <Muted>No pending suggestions.</Muted>
          )}
        </WorkspaceCard>
      </WorkspaceRow>
    </Page>
  );
}
