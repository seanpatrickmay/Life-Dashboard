import { FormEvent, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import styled from 'styled-components';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

import {
  fetchProjectBoard,
  fetchProjectActivities,
  createProjectTodo,
  updateProjectTodo,
  deleteProjectTodo,
  type ProjectItem,
  type ProjectActivity,
  type TodoItem,
} from '../services/api';

/* ═══════════════════════════════════════════════════════════════════════
   Styled Components
   ═══════════════════════════════════════════════════════════════════════ */

const Shell = styled.div`
  display: grid;
  grid-template-columns: 260px 1fr;
  height: 100vh;
  background: ${({ theme }) => theme.colors.backgroundPage};
  color: ${({ theme }) => theme.colors.textPrimary};
`;

/* ── Sidebar ────────────────────────────────────────────────────────── */

const Sidebar = styled.aside`
  border-right: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  padding: 24px 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
`;

const SidebarTitle = styled.div`
  font-size: 0.72rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: ${({ theme }) => theme.colors.textSecondary};
  padding: 0 20px;
  margin-bottom: 8px;
`;

const ProjectRow = styled.button<{ $active?: boolean }>`
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 20px;
  border: none;
  background: ${({ $active, theme }) => ($active ? theme.colors.backgroundCard : 'transparent')};
  color: ${({ theme }) => theme.colors.textPrimary};
  font-size: 0.88rem;
  text-align: left;
  cursor: pointer;
  width: 100%;
  border-radius: 0;

  &:hover {
    background: ${({ theme }) => theme.colors.backgroundCard};
  }
`;

const ProjectName = styled.span`
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
`;

const Badge = styled.span`
  font-size: 0.72rem;
  color: ${({ theme }) => theme.colors.textSecondary};
  flex-shrink: 0;
`;

/* ── Main Content ───────────────────────────────────────────────────── */

const Main = styled.main`
  overflow-y: auto;
  padding: 32px 48px;
`;

const Content = styled.div`
  max-width: 780px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 32px;
`;

const ProjectTitle = styled.h1`
  font-size: 1.6rem;
  font-weight: 700;
  margin: 0;
`;

/* ── Section Layout ─────────────────────────────────────────────────── */

const Section = styled.section`
  display: flex;
  flex-direction: column;
  gap: 10px;
`;

const SectionHeader = styled.h2`
  font-size: 0.76rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: ${({ theme }) => theme.colors.textSecondary};
  margin: 0;
`;

/* ── State Summary ──────────────────────────────────────────────────── */

const StateCard = styled.div`
  background: ${({ theme }) => theme.colors.backgroundCard};
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  border-radius: 12px;
  padding: 18px 22px;
  display: flex;
  flex-direction: column;
  gap: 12px;
`;

const StateLabel = styled.div`
  font-size: 0.72rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: ${({ theme }) => theme.colors.textSecondary};
  margin-bottom: 2px;
`;

const StateText = styled.div`
  font-size: 0.9rem;
  line-height: 1.5;
`;

const NextStepsList = styled.ul`
  margin: 0;
  padding-left: 18px;
  font-size: 0.9rem;
  line-height: 1.6;
`;

const Freshness = styled.div<{ $stale?: boolean }>`
  font-size: 0.72rem;
  color: ${({ theme }) => theme.colors.textSecondary};
  opacity: ${({ $stale }) => ($stale ? 0.5 : 0.8)};
  font-style: ${({ $stale }) => ($stale ? 'italic' : 'normal')};
`;

/* ── Todos ──────────────────────────────────────────────────────────── */

const TodoList = styled.div`
  display: flex;
  flex-direction: column;
  gap: 4px;
`;

const TodoRow = styled.div<{ $done?: boolean }>`
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-radius: 8px;
  background: ${({ theme }) => theme.colors.backgroundCard};
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  opacity: ${({ $done }) => ($done ? 0.55 : 1)};
`;

const Checkbox = styled.input`
  width: 16px;
  height: 16px;
  cursor: pointer;
  flex-shrink: 0;
`;

const TodoText = styled.span<{ $done?: boolean }>`
  flex: 1;
  font-size: 0.9rem;
  text-decoration: ${({ $done }) => ($done ? 'line-through' : 'none')};
`;

const TodoDelete = styled.button`
  background: none;
  border: none;
  color: ${({ theme }) => theme.colors.textSecondary};
  cursor: pointer;
  font-size: 0.78rem;
  padding: 2px 6px;
  border-radius: 4px;
  opacity: 0;

  ${TodoRow}:hover & {
    opacity: 0.6;
  }
  &:hover {
    opacity: 1 !important;
    color: #e53e3e;
  }
`;

const AddTodoForm = styled.form`
  display: flex;
  gap: 8px;
  margin-top: 4px;
`;

const AddTodoInput = styled.input`
  flex: 1;
  padding: 8px 12px;
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  border-radius: 8px;
  background: ${({ theme }) => theme.colors.backgroundCard};
  color: ${({ theme }) => theme.colors.textPrimary};
  font-size: 0.88rem;

  &::placeholder {
    color: ${({ theme }) => theme.colors.textSecondary};
  }
  &:focus {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: -1px;
  }
`;

const AddTodoButton = styled.button`
  padding: 8px 16px;
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  border-radius: 8px;
  background: ${({ theme }) => theme.colors.backgroundCard};
  color: ${({ theme }) => theme.colors.textPrimary};
  font-size: 0.84rem;
  cursor: pointer;

  &:hover {
    background: ${({ theme }) => theme.colors.borderSubtle};
  }
`;

/* ── Activity Feed ──────────────────────────────────────────────────── */

const ActivityGroup = styled.div`
  display: flex;
  flex-direction: column;
  gap: 6px;
`;

const ActivityDate = styled.div`
  font-size: 0.76rem;
  font-weight: 600;
  color: ${({ theme }) => theme.colors.textSecondary};
  letter-spacing: 0.04em;
  padding-bottom: 4px;
  border-bottom: 1px solid ${({ theme }) => theme.colors.borderSubtle};
`;

const ActivityCard = styled.div`
  padding: 10px 14px;
  background: ${({ theme }) => theme.colors.backgroundCard};
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  border-radius: 10px;
`;

const ActivitySummary = styled.div`
  font-size: 0.88rem;
  line-height: 1.5;
`;

const CategoryBadge = styled.span<{ $cat?: string }>`
  display: inline-block;
  font-size: 0.68rem;
  font-weight: 600;
  padding: 1px 7px;
  border-radius: 4px;
  margin-right: 6px;
  vertical-align: middle;
  color: #fff;
  background: ${({ $cat }) => {
    const m: Record<string, string> = {
      feature: '#4a9eff',
      bugfix: '#ff6b6b',
      refactor: '#ffd93d',
      debugging: '#ff8c42',
      planning: '#a78bfa',
      research: '#67d5b5',
      config: '#888',
    };
    return m[$cat ?? ''] ?? '#888';
  }};
`;

const ActivityMeta = styled.div`
  margin-top: 4px;
  font-size: 0.76rem;
  color: ${({ theme }) => theme.colors.textSecondary};
`;

const Muted = styled.div`
  color: ${({ theme }) => theme.colors.textSecondary};
  font-size: 0.88rem;
  padding: 4px 0;
`;

/* ═══════════════════════════════════════════════════════════════════════
   Helpers
   ═══════════════════════════════════════════════════════════════════════ */

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const h = Math.floor(diff / 3600000);
  if (h < 1) return 'just now';
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  if (d < 7) return `${d}d ago`;
  return `${Math.floor(d / 7)}w ago`;
}

function friendlyDate(dateStr: string): string {
  const d = new Date(dateStr + 'T00:00:00');
  const today = new Date();
  if (d.toDateString() === today.toDateString()) return 'Today';
  const y = new Date(today);
  y.setDate(y.getDate() - 1);
  if (d.toDateString() === y.toDateString()) return 'Yesterday';
  return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
}

function groupByDate(activities: ProjectActivity[]): [string, ProjectActivity[]][] {
  const map: Record<string, ProjectActivity[]> = {};
  for (const a of activities) {
    (map[a.local_date] ||= []).push(a);
  }
  return Object.entries(map);
}

/* ═══════════════════════════════════════════════════════════════════════
   Main Component
   ═══════════════════════════════════════════════════════════════════════ */

const BOARD_KEY = ['projectBoard'];
const TZ = Intl.DateTimeFormat().resolvedOptions().timeZone;

export function ProjectsPage() {
  const [params, setParams] = useSearchParams();
  const queryClient = useQueryClient();

  const selectedId = Number(params.get('project')) || null;
  const selectProject = (id: number) => setParams({ project: String(id) });

  // ── Data fetching ──────────────────────────────────────────────────

  const boardQuery = useQuery({
    queryKey: BOARD_KEY,
    queryFn: fetchProjectBoard,
    staleTime: 60_000,
  });

  const projects = boardQuery.data?.projects ?? [];
  const allTodos = boardQuery.data?.todos ?? [];

  // Auto-select first project if none selected
  const activeProject: ProjectItem | undefined =
    projects.find((p) => p.id === selectedId) ?? projects[0];

  const activeProjectId = activeProject?.id ?? null;

  const activitiesQuery = useQuery({
    queryKey: ['projectActivities', activeProjectId],
    queryFn: () => (activeProjectId ? fetchProjectActivities(activeProjectId) : Promise.resolve([])),
    staleTime: 5 * 60_000,
    enabled: activeProjectId !== null,
  });

  const projectTodos = allTodos.filter((t) => t.project_id === activeProjectId);
  const openTodos = projectTodos.filter((t) => !t.completed);
  const doneTodos = projectTodos.filter((t) => t.completed);
  const activities = activitiesQuery.data ?? [];

  // ── Mutations ──────────────────────────────────────────────────────

  const invalidateBoard = () => queryClient.invalidateQueries({ queryKey: BOARD_KEY });

  const [newTodoText, setNewTodoText] = useState('');

  const createMutation = useMutation({
    mutationFn: createProjectTodo,
    onSuccess: () => {
      invalidateBoard();
      setNewTodoText('');
    },
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, completed }: { id: number; completed: boolean }) =>
      updateProjectTodo(id, { completed, time_zone: TZ }),
    onSuccess: invalidateBoard,
  });

  const deleteMutation = useMutation({
    mutationFn: deleteProjectTodo,
    onSuccess: invalidateBoard,
  });

  const handleAddTodo = (e: FormEvent) => {
    e.preventDefault();
    const text = newTodoText.trim();
    if (!text || !activeProjectId) return;
    createMutation.mutate({ text, project_id: activeProjectId, time_zone: TZ });
  };

  // ── Render ─────────────────────────────────────────────────────────

  if (boardQuery.isLoading) return <Shell><Muted style={{ padding: 32 }}>Loading…</Muted></Shell>;

  const state = activeProject?.state_summary_json;
  const stateUpdated = activeProject?.state_updated_at_utc;
  const isStale = stateUpdated
    ? Date.now() - new Date(stateUpdated).getTime() > 7 * 24 * 60 * 60 * 1000
    : true;

  return (
    <Shell>
      {/* ── Sidebar ─────────────────────────────────────────────── */}
      <Sidebar>
        <SidebarTitle>Projects</SidebarTitle>
        {projects.map((p) => (
          <ProjectRow
            key={p.id}
            $active={p.id === activeProjectId}
            onClick={() => selectProject(p.id)}
          >
            <ProjectName>{p.name}</ProjectName>
            {p.open_count > 0 && <Badge>{p.open_count}</Badge>}
          </ProjectRow>
        ))}
      </Sidebar>

      {/* ── Main Content ────────────────────────────────────────── */}
      <Main>
        {activeProject ? (
          <Content>
            <ProjectTitle>{activeProject.name}</ProjectTitle>

            {/* ── State Summary ──────────────────────────────── */}
            {state && (
              <Section>
                <SectionHeader>State</SectionHeader>
                <StateCard>
                  <div>
                    <StateLabel>Status</StateLabel>
                    <StateText>{state.status}</StateText>
                  </div>
                  <div>
                    <StateLabel>Recent Focus</StateLabel>
                    <StateText>{state.recent_focus}</StateText>
                  </div>
                  {state.next_steps.length > 0 && (
                    <div>
                      <StateLabel>Next Steps</StateLabel>
                      <NextStepsList>
                        {state.next_steps.map((s, i) => (
                          <li key={i}>{s}</li>
                        ))}
                      </NextStepsList>
                    </div>
                  )}
                  {stateUpdated && (
                    <Freshness $stale={isStale}>
                      Updated {relativeTime(stateUpdated)}
                    </Freshness>
                  )}
                </StateCard>
              </Section>
            )}

            {/* ── Todos ──────────────────────────────────────── */}
            <Section>
              <SectionHeader>
                Todos{openTodos.length > 0 ? ` (${openTodos.length})` : ''}
              </SectionHeader>
              <TodoList>
                {openTodos.map((todo) => (
                  <TodoRow key={todo.id}>
                    <Checkbox
                      type="checkbox"
                      checked={false}
                      onChange={() => toggleMutation.mutate({ id: todo.id, completed: true })}
                    />
                    <TodoText>{todo.text}</TodoText>
                    <TodoDelete type="button" onClick={() => deleteMutation.mutate(todo.id)}>
                      ×
                    </TodoDelete>
                  </TodoRow>
                ))}
                {doneTodos.length > 0 && doneTodos.slice(0, 5).map((todo) => (
                  <TodoRow key={todo.id} $done>
                    <Checkbox
                      type="checkbox"
                      checked
                      onChange={() => toggleMutation.mutate({ id: todo.id, completed: false })}
                    />
                    <TodoText $done>{todo.text}</TodoText>
                  </TodoRow>
                ))}
                {openTodos.length === 0 && doneTodos.length === 0 && (
                  <Muted>No todos yet.</Muted>
                )}
              </TodoList>
              <AddTodoForm onSubmit={handleAddTodo}>
                <AddTodoInput
                  type="text"
                  placeholder="Add a todo…"
                  value={newTodoText}
                  onChange={(e) => setNewTodoText(e.target.value)}
                />
                <AddTodoButton type="submit" disabled={!newTodoText.trim()}>
                  Add
                </AddTodoButton>
              </AddTodoForm>
            </Section>

            {/* ── Activity ───────────────────────────────────── */}
            <Section>
              <SectionHeader>Activity</SectionHeader>
              {activitiesQuery.isLoading ? (
                <Muted>Loading activity…</Muted>
              ) : activities.length === 0 ? (
                <Muted>No activity recorded yet.</Muted>
              ) : (
                groupByDate(activities).map(([dateStr, items]) => (
                  <ActivityGroup key={dateStr}>
                    <ActivityDate>{friendlyDate(dateStr)}</ActivityDate>
                    {items.map((a) => (
                      <ActivityCard key={a.id}>
                        <ActivitySummary>
                          {a.details_json?.category && (
                            <CategoryBadge $cat={a.details_json.category}>
                              {a.details_json.category}
                            </CategoryBadge>
                          )}
                          {a.summary}
                        </ActivitySummary>
                        {a.details_json && (
                          <ActivityMeta>
                            {a.details_json.git_branch && (
                              <span>Branch: {a.details_json.git_branch}</span>
                            )}
                            {a.details_json.files_modified?.length ? (
                              <span>
                                {a.details_json.git_branch ? ' · ' : ''}
                                {a.details_json.files_modified.length} files modified
                              </span>
                            ) : null}
                          </ActivityMeta>
                        )}
                      </ActivityCard>
                    ))}
                  </ActivityGroup>
                ))
              )}
            </Section>
          </Content>
        ) : (
          <Muted>Select a project from the sidebar.</Muted>
        )}
      </Main>
    </Shell>
  );
}
