import { useQuery } from '@tanstack/react-query';
import {
  fetchProjectActivities,
  fetchAllActivities,
  fetchProjectBoard,
  type ProjectActivity,
  type ProjectStateSummary,
} from '../services/api';

const STALE_TIME = 5 * 60 * 1000;

export const projectActivityKeys = {
  all: ['projectActivities'] as const,
  byProject: (projectId: number) => ['projectActivities', projectId] as const,
  allProjects: () => ['projectActivities', 'all'] as const,
};

export function useProjectActivities(projectId: number | null) {
  return useQuery<ProjectActivity[]>({
    queryKey: projectId
      ? projectActivityKeys.byProject(projectId)
      : projectActivityKeys.allProjects(),
    queryFn: () =>
      projectId ? fetchProjectActivities(projectId) : fetchAllActivities(),
    staleTime: STALE_TIME,
  });
}

export function useProjectState(projectId: number | null) {
  return useQuery<{ state: ProjectStateSummary | null; updatedAt: string | null }>({
    queryKey: ['projectState', projectId],
    queryFn: async () => {
      if (!projectId) return { state: null, updatedAt: null };
      const board = await fetchProjectBoard();
      const project = board.projects.find((p) => p.id === projectId);
      return {
        state: project?.state_summary_json ?? null,
        updatedAt: project?.state_updated_at_utc ?? null,
      };
    },
    staleTime: STALE_TIME,
    enabled: projectId !== null,
  });
}
