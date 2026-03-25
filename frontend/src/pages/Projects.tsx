import { FormEvent, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import styled, { keyframes } from 'styled-components';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

import {
  fetchProjectBoard,
  fetchProjectActivities,
  createProjectTodo,
  updateProjectTodo,
  deleteProjectTodo,
  updateProject,
  deleteProject,
  type ProjectItem,
  type ProjectActivity,
} from '../services/api';

/* ═══════════════════════════════════════════════════════════════════════
   Animations
   ═══════════════════════════════════════════════════════════════════════ */

const fadeIn = keyframes`
  from { opacity: 0; transform: translateY(6px); }
  to   { opacity: 1; transform: translateY(0); }
`;

/* ═══════════════════════════════════════════════════════════════════════
   Layout
   ═══════════════════════════════════════════════════════════════════════ */

const Shell = styled.div`
  display: grid;
  grid-template-columns: 280px 1fr;
  height: 100vh;
  background: ${({ theme }) => theme.colors.backgroundPage};
  color: ${({ theme }) => theme.colors.textPrimary};

  @media (max-width: 800px) {
    grid-template-columns: 1fr;
  }
`;

/* ── Sidebar ────────────────────────────────────────────────────────── */

const Sidebar = styled.aside`
  border-right: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  background: ${({ theme }) => theme.colors.surfaceRaised};

  @media (max-width: 800px) {
    display: none;
  }
`;

const SidebarTop = styled.div`
  padding: 28px 24px 20px;
  font-size: 1.1rem;
  font-weight: 700;
  letter-spacing: -0.01em;
`;

const SidebarSection = styled.div`
  padding: 0 12px;
  margin-bottom: 20px;
`;

const SidebarLabel = styled.div`
  font-size: 0.68rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: ${({ theme }) => theme.colors.textSecondary};
  padding: 0 12px;
  margin-bottom: 6px;
`;

const ProjectRow = styled.button<{ $active?: boolean }>`
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 7px 12px;
  border: none;
  background: ${({ $active, theme }) =>
    $active ? theme.colors.backgroundCard : 'transparent'};
  color: ${({ theme }) => theme.colors.textPrimary};
  font-size: 0.86rem;
  text-align: left;
  cursor: pointer;
  width: 100%;
  border-radius: 8px;
  transition: background 0.12s;

  ${({ $active, theme }) =>
    $active &&
    `box-shadow: 0 1px 3px ${theme.colors.overlay}, 0 0 0 1px ${theme.colors.borderSubtle};`}

  &:hover {
    background: ${({ $active, theme }) =>
      $active ? theme.colors.backgroundCard : theme.colors.overlayHover};
  }
`;

const ProjectName = styled.span`
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 500;
`;

const Badge = styled.span`
  font-size: 0.7rem;
  font-weight: 600;
  color: ${({ theme }) => theme.colors.accent};
  background: ${({ theme }) => theme.colors.accentSubtle};
  padding: 1px 7px;
  border-radius: 10px;
  flex-shrink: 0;
`;

/* ── Main Content ───────────────────────────────────────────────────── */

const Main = styled.main`
  overflow-y: auto;
  padding: 36px 48px 64px;

  @media (max-width: 1000px) {
    padding: 24px 20px 48px;
  }
`;

const Content = styled.div`
  max-width: 740px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 36px;
  animation: ${fadeIn} 0.3s ease-out;
`;

/* ── Project Header ─────────────────────────────────────────────────── */

const ProjectHeader = styled.div`
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 16px;
`;

const ProjectTitle = styled.h1`
  font-size: 1.75rem;
  font-weight: 800;
  letter-spacing: -0.02em;
  margin: 0;
  flex: 1;
`;

const ProjectTitleInput = styled.input`
  font-size: 1.75rem;
  font-weight: 800;
  letter-spacing: -0.02em;
  margin: 0;
  flex: 1;
  border: none;
  border-bottom: 2px solid ${({ theme }) => theme.colors.accent};
  background: transparent;
  color: ${({ theme }) => theme.colors.textPrimary};
  padding: 0 0 2px;
  outline: none;
`;

const HeaderActions = styled.div`
  display: flex;
  gap: 4px;
  flex-shrink: 0;
`;

const SmallButton = styled.button`
  background: none;
  border: 1px solid transparent;
  color: ${({ theme }) => theme.colors.textSecondary};
  cursor: pointer;
  font-size: 0.78rem;
  padding: 4px 10px;
  border-radius: 6px;
  transition: all 0.12s;

  &:hover {
    border-color: ${({ theme }) => theme.colors.borderSubtle};
    color: ${({ theme }) => theme.colors.textPrimary};
    background: ${({ theme }) => theme.colors.overlayHover};
  }
`;

const DangerButton = styled(SmallButton)`
  &:hover {
    border-color: ${({ theme }) => theme.colors.danger};
    color: ${({ theme }) => theme.colors.danger};
    background: ${({ theme }) => theme.colors.dangerSubtle};
  }
`;

/* ── Sections ───────────────────────────────────────────────────────── */

const Section = styled.section`
  display: flex;
  flex-direction: column;
  gap: 12px;
`;

const SectionHeader = styled.h2`
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: ${({ theme }) => theme.colors.textSecondary};
  margin: 0;
  display: flex;
  align-items: center;
  gap: 8px;
`;

const SectionCount = styled.span`
  font-weight: 600;
  font-size: 0.68rem;
  color: ${({ theme }) => theme.colors.accent};
  background: ${({ theme }) => theme.colors.accentSubtle};
  padding: 0 6px;
  border-radius: 8px;
  line-height: 1.6;
`;

/* ── State Card ─────────────────────────────────────────────────────── */

const StateCard = styled.div`
  background: ${({ theme }) => theme.colors.backgroundCard};
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  border-radius: 14px;
  padding: 20px 24px;
  display: grid;
  gap: 16px;
  box-shadow: 0 1px 4px ${({ theme }) => theme.colors.overlay};
`;

const StateRow = styled.div``;

const StateLabel = styled.div`
  font-size: 0.68rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: ${({ theme }) => theme.colors.textSecondary};
  margin-bottom: 4px;
`;

const StateText = styled.div`
  font-size: 0.9rem;
  line-height: 1.55;
`;

const NextStepsList = styled.ul`
  margin: 0;
  padding-left: 18px;
  font-size: 0.9rem;
  line-height: 1.7;

  li::marker {
    color: ${({ theme }) => theme.colors.accent};
  }
`;

const Freshness = styled.div<{ $stale?: boolean }>`
  font-size: 0.7rem;
  color: ${({ theme }) => theme.colors.textSecondary};
  opacity: ${({ $stale }) => ($stale ? 0.45 : 0.7)};
  font-style: ${({ $stale }) => ($stale ? 'italic' : 'normal')};
`;

/* ── Todos ──────────────────────────────────────────────────────────── */

const TodoList = styled.div`
  display: flex;
  flex-direction: column;
  gap: 3px;
`;

const TodoRow = styled.div<{ $done?: boolean }>`
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 14px;
  border-radius: 10px;
  background: ${({ theme }) => theme.colors.backgroundCard};
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  opacity: ${({ $done }) => ($done ? 0.5 : 1)};
  transition: opacity 0.15s, box-shadow 0.15s;

  &:hover {
    box-shadow: 0 1px 4px ${({ theme }) => theme.colors.overlay};
  }
`;

const Checkbox = styled.input`
  appearance: none;
  width: 18px;
  height: 18px;
  border: 2px solid ${({ theme }) => theme.colors.borderSubtle};
  border-radius: 5px;
  cursor: pointer;
  flex-shrink: 0;
  transition: all 0.12s;
  position: relative;

  &:checked {
    background: ${({ theme }) => theme.colors.accent};
    border-color: ${({ theme }) => theme.colors.accent};
  }
  &:checked::after {
    content: '';
    position: absolute;
    left: 4px;
    top: 1px;
    width: 5px;
    height: 9px;
    border: solid white;
    border-width: 0 2px 2px 0;
    transform: rotate(45deg);
  }
  &:hover {
    border-color: ${({ theme }) => theme.colors.accent};
  }
`;

const TodoText = styled.span<{ $done?: boolean }>`
  flex: 1;
  font-size: 0.9rem;
  line-height: 1.4;
  text-decoration: ${({ $done }) => ($done ? 'line-through' : 'none')};
  color: ${({ $done, theme }) => ($done ? theme.colors.textSecondary : theme.colors.textPrimary)};
`;

const TodoDelete = styled.button`
  background: none;
  border: none;
  color: ${({ theme }) => theme.colors.textSecondary};
  cursor: pointer;
  font-size: 1rem;
  padding: 0 4px;
  border-radius: 4px;
  opacity: 0;
  transition: opacity 0.1s;
  line-height: 1;

  ${TodoRow}:hover & { opacity: 0.4; }
  &:hover {
    opacity: 1 !important;
    color: ${({ theme }) => theme.colors.danger};
  }
`;

const CompletedToggle = styled.button`
  background: none;
  border: none;
  color: ${({ theme }) => theme.colors.textSecondary};
  font-size: 0.78rem;
  cursor: pointer;
  padding: 4px 0;
  margin-top: 2px;

  &:hover { color: ${({ theme }) => theme.colors.textPrimary}; }
`;

const AddTodoForm = styled.form`
  display: flex;
  gap: 8px;
  margin-top: 6px;
`;

const AddTodoInput = styled.input`
  flex: 1;
  padding: 9px 14px;
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  border-radius: 10px;
  background: ${({ theme }) => theme.colors.backgroundCard};
  color: ${({ theme }) => theme.colors.textPrimary};
  font-size: 0.88rem;
  transition: border-color 0.12s;

  &::placeholder { color: ${({ theme }) => theme.colors.textSecondary}; opacity: 0.6; }
  &:focus {
    outline: none;
    border-color: ${({ theme }) => theme.colors.accent};
    box-shadow: 0 0 0 3px ${({ theme }) => theme.colors.accentSubtle};
  }
`;

const AddTodoButton = styled.button`
  padding: 9px 18px;
  border: none;
  border-radius: 10px;
  background: ${({ theme }) => theme.colors.accent};
  color: white;
  font-size: 0.84rem;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.12s;

  &:hover { opacity: 0.85; }
  &:disabled { opacity: 0.4; cursor: default; }
`;

/* ── Activity ───────────────────────────────────────────────────────── */

const ActivityTimeline = styled.div`
  display: flex;
  flex-direction: column;
  gap: 16px;
`;

const ActivityGroup = styled.div`
  display: flex;
  flex-direction: column;
  gap: 6px;
`;

const ActivityDate = styled.div`
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: ${({ theme }) => theme.colors.textSecondary};
  padding-bottom: 4px;
`;

const ActivityCard = styled.div`
  padding: 12px 16px;
  background: ${({ theme }) => theme.colors.backgroundCard};
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  border-radius: 10px;
  transition: box-shadow 0.12s;

  &:hover {
    box-shadow: 0 2px 8px ${({ theme }) => theme.colors.overlay};
  }
`;

const ActivitySummary = styled.div`
  font-size: 0.88rem;
  line-height: 1.55;
`;

const CategoryBadge = styled.span<{ $cat?: string }>`
  display: inline-block;
  font-size: 0.64rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  padding: 2px 8px;
  border-radius: 5px;
  margin-right: 8px;
  vertical-align: middle;
  color: #fff;
  background: ${({ $cat }) => {
    const m: Record<string, string> = {
      feature: '#4a90d9',
      bugfix: '#d94a4a',
      refactor: '#c9a227',
      debugging: '#d97a2e',
      planning: '#8b6fc0',
      research: '#3f9b8a',
      config: '#7a7a8a',
    };
    return m[$cat ?? ''] ?? '#7a7a8a';
  }};
`;

const ActivityMeta = styled.div`
  margin-top: 6px;
  font-size: 0.74rem;
  color: ${({ theme }) => theme.colors.textSecondary};
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
`;

const MetaItem = styled.span`
  display: inline-flex;
  align-items: center;
  gap: 4px;
`;

const Muted = styled.div`
  color: ${({ theme }) => theme.colors.textSecondary};
  font-size: 0.88rem;
  padding: 4px 0;
`;

const EmptyState = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 8px;
  color: ${({ theme }) => theme.colors.textSecondary};
  font-size: 0.92rem;
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

function projectLabel(p: ProjectItem): string {
  return p.display_name || p.name;
}

/* ═══════════════════════════════════════════════════════════════════════
   Component
   ═══════════════════════════════════════════════════════════════════════ */

const BOARD_KEY = ['projectBoard'];
const TZ = Intl.DateTimeFormat().resolvedOptions().timeZone;
const ACTIVE_CUTOFF = 30 * 24 * 60 * 60 * 1000;
const COMPLETED_PREVIEW = 3;

export function ProjectsPage() {
  const [params, setParams] = useSearchParams();
  const queryClient = useQueryClient();

  const selectedId = Number(params.get('project')) || null;
  const selectProject = (id: number) => setParams({ project: String(id) });

  // ── Data ───────────────────────────────────────────────────────────

  const boardQuery = useQuery({
    queryKey: BOARD_KEY,
    queryFn: fetchProjectBoard,
    staleTime: 60_000,
  });

  const allProjects = boardQuery.data?.projects ?? [];
  const allTodos = boardQuery.data?.todos ?? [];
  const now = Date.now();

  const activeProjects = allProjects
    .filter((p) => {
      if (p.open_count > 0) return true;
      if (p.last_activity_date)
        return now - new Date(p.last_activity_date + 'T00:00:00').getTime() < ACTIVE_CUTOFF;
      return false;
    })
    .sort((a, b) => {
      const ad = a.last_activity_date || '0';
      const bd = b.last_activity_date || '0';
      if (ad !== bd) return bd.localeCompare(ad);
      return b.open_count - a.open_count;
    });

  const otherProjects = allProjects
    .filter((p) => !activeProjects.includes(p))
    .sort((a, b) => projectLabel(a).localeCompare(projectLabel(b)));

  const activeProject: ProjectItem | undefined =
    allProjects.find((p) => p.id === selectedId) ?? activeProjects[0] ?? allProjects[0];
  const activeProjectId = activeProject?.id ?? null;

  const activitiesQuery = useQuery({
    queryKey: ['projectActivities', activeProjectId],
    queryFn: () =>
      activeProjectId ? fetchProjectActivities(activeProjectId) : Promise.resolve([]),
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
  const [renaming, setRenaming] = useState(false);
  const [renameValue, setRenameValue] = useState('');
  const [showCompleted, setShowCompleted] = useState(false);
  const renameRef = useRef<HTMLInputElement>(null);

  const createMutation = useMutation({
    mutationFn: createProjectTodo,
    onSuccess: () => { invalidateBoard(); setNewTodoText(''); },
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
  const renameMutation = useMutation({
    mutationFn: ({ id, display_name }: { id: number; display_name: string }) =>
      updateProject(id, { display_name: display_name || null }),
    onSuccess: () => { invalidateBoard(); setRenaming(false); },
  });
  const deleteProjectMutation = useMutation({
    mutationFn: deleteProject,
    onSuccess: () => { invalidateBoard(); setParams({}); },
  });

  const startRename = () => {
    if (!activeProject) return;
    setRenameValue(projectLabel(activeProject));
    setRenaming(true);
    setTimeout(() => renameRef.current?.select(), 0);
  };
  const submitRename = () => {
    if (!activeProject) return;
    const trimmed = renameValue.trim();
    if (trimmed && trimmed !== projectLabel(activeProject)) {
      renameMutation.mutate({ id: activeProject.id, display_name: trimmed });
    } else {
      setRenaming(false);
    }
  };
  const handleDelete = () => {
    if (!activeProject || activeProject.name === 'Inbox') return;
    if (!window.confirm(`Delete "${projectLabel(activeProject)}"? Todos will move to Inbox.`)) return;
    deleteProjectMutation.mutate(activeProject.id);
  };
  const handleAddTodo = (e: FormEvent) => {
    e.preventDefault();
    const text = newTodoText.trim();
    if (!text || !activeProjectId) return;
    createMutation.mutate({ text, project_id: activeProjectId, time_zone: TZ });
  };

  // ── Render ─────────────────────────────────────────────────────────

  if (boardQuery.isLoading) return <Shell><EmptyState>Loading projects...</EmptyState></Shell>;

  const state = activeProject?.state_summary_json;
  const stateUpdated = activeProject?.state_updated_at_utc;
  const isStale = stateUpdated
    ? Date.now() - new Date(stateUpdated).getTime() > 7 * 24 * 60 * 60 * 1000
    : true;

  const visibleCompleted = showCompleted ? doneTodos : doneTodos.slice(0, COMPLETED_PREVIEW);

  const sidebarGroup = (label: string, items: ProjectItem[]) =>
    items.length > 0 && (
      <SidebarSection>
        <SidebarLabel>{label}</SidebarLabel>
        {items.map((p) => (
          <ProjectRow key={p.id} $active={p.id === activeProjectId} onClick={() => selectProject(p.id)}>
            <ProjectName>{projectLabel(p)}</ProjectName>
            {p.open_count > 0 && <Badge>{p.open_count}</Badge>}
          </ProjectRow>
        ))}
      </SidebarSection>
    );

  return (
    <Shell>
      <Sidebar>
        <SidebarTop>Projects</SidebarTop>
        {sidebarGroup('Active', activeProjects)}
        {sidebarGroup('Other', otherProjects)}
      </Sidebar>

      <Main>
        {activeProject ? (
          <Content key={activeProject.id}>
            {/* Header */}
            <ProjectHeader>
              {renaming ? (
                <ProjectTitleInput
                  ref={renameRef}
                  value={renameValue}
                  onChange={(e) => setRenameValue(e.target.value)}
                  onBlur={submitRename}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') submitRename();
                    if (e.key === 'Escape') setRenaming(false);
                  }}
                />
              ) : (
                <ProjectTitle>{projectLabel(activeProject)}</ProjectTitle>
              )}
              {!renaming && (
                <HeaderActions>
                  <SmallButton type="button" onClick={startRename}>Rename</SmallButton>
                  {activeProject.name !== 'Inbox' && (
                    <DangerButton type="button" onClick={handleDelete}>Delete</DangerButton>
                  )}
                </HeaderActions>
              )}
            </ProjectHeader>

            {/* State */}
            {state && (
              <Section>
                <SectionHeader>Overview</SectionHeader>
                <StateCard>
                  <StateRow>
                    <StateLabel>Status</StateLabel>
                    <StateText>{state.status}</StateText>
                  </StateRow>
                  <StateRow>
                    <StateLabel>Recent Focus</StateLabel>
                    <StateText>{state.recent_focus}</StateText>
                  </StateRow>
                  {state.next_steps.length > 0 && (
                    <StateRow>
                      <StateLabel>Next Steps</StateLabel>
                      <NextStepsList>
                        {state.next_steps.map((s, i) => <li key={i}>{s}</li>)}
                      </NextStepsList>
                    </StateRow>
                  )}
                  {stateUpdated && (
                    <Freshness $stale={isStale}>Updated {relativeTime(stateUpdated)}</Freshness>
                  )}
                </StateCard>
              </Section>
            )}

            {/* Todos */}
            <Section>
              <SectionHeader>
                Todos
                {openTodos.length > 0 && <SectionCount>{openTodos.length}</SectionCount>}
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
                      &times;
                    </TodoDelete>
                  </TodoRow>
                ))}
                {visibleCompleted.map((todo) => (
                  <TodoRow key={todo.id} $done>
                    <Checkbox
                      type="checkbox"
                      checked
                      onChange={() => toggleMutation.mutate({ id: todo.id, completed: false })}
                    />
                    <TodoText $done>{todo.text}</TodoText>
                  </TodoRow>
                ))}
                {doneTodos.length > COMPLETED_PREVIEW && (
                  <CompletedToggle type="button" onClick={() => setShowCompleted((v) => !v)}>
                    {showCompleted
                      ? 'Hide completed'
                      : `Show ${doneTodos.length - COMPLETED_PREVIEW} more completed`}
                  </CompletedToggle>
                )}
                {openTodos.length === 0 && doneTodos.length === 0 && (
                  <Muted>No todos yet.</Muted>
                )}
              </TodoList>
              <AddTodoForm onSubmit={handleAddTodo}>
                <AddTodoInput
                  type="text"
                  placeholder="Add a todo..."
                  value={newTodoText}
                  onChange={(e) => setNewTodoText(e.target.value)}
                />
                <AddTodoButton type="submit" disabled={!newTodoText.trim()}>Add</AddTodoButton>
              </AddTodoForm>
            </Section>

            {/* Activity */}
            <Section>
              <SectionHeader>Activity</SectionHeader>
              {activitiesQuery.isLoading ? (
                <Muted>Loading activity...</Muted>
              ) : activities.length === 0 ? (
                <Muted>No activity recorded yet.</Muted>
              ) : (
                <ActivityTimeline>
                  {groupByDate(activities).map(([dateStr, items]) => (
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
                          {a.details_json && (a.details_json.git_branch || a.details_json.files_modified?.length) && (
                            <ActivityMeta>
                              {a.details_json.git_branch && (
                                <MetaItem>{a.details_json.git_branch}</MetaItem>
                              )}
                              {a.details_json.files_modified?.length ? (
                                <MetaItem>{a.details_json.files_modified.length} files</MetaItem>
                              ) : null}
                            </ActivityMeta>
                          )}
                        </ActivityCard>
                      ))}
                    </ActivityGroup>
                  ))}
                </ActivityTimeline>
              )}
            </Section>
          </Content>
        ) : (
          <EmptyState>Select a project to get started.</EmptyState>
        )}
      </Main>
    </Shell>
  );
}
