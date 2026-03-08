import { useCallback, useEffect } from 'react';
import { QueryClient, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  applyWorkspaceTemplate,
  createWorkspaceBlock,
  createWorkspacePage,
  createWorkspaceRow,
  createWorkspaceView,
  deleteWorkspaceBlock,
  deleteWorkspacePage,
  fetchWorkspaceBacklinks,
  fetchWorkspaceBootstrap,
  fetchWorkspaceDatabaseRows,
  fetchWorkspacePage,
  fetchWorkspaceTemplates,
  markWorkspaceRecent,
  reorderWorkspaceBlocks,
  searchWorkspace,
  updateWorkspaceBlock,
  updateWorkspacePage,
  updateWorkspacePageProperties,
  updateWorkspaceView,
  type WorkspaceBacklinksResponse,
  type WorkspaceBootstrap,
  type WorkspaceDatabaseRowsResponse,
  type WorkspacePageDetail,
  type WorkspacePageLink,
  type WorkspacePageSummary,
  type WorkspaceSearchResponse
} from '../services/workspaceApi';

const WORKSPACE_KEY = ['workspace'] as const;
const STALE_TIME = {
  bootstrap: 5 * 60 * 1000,
  templates: 10 * 60 * 1000,
  page: 30 * 1000,
  database: 20 * 1000,
  search: 15 * 1000,
  backlinks: 30 * 1000,
  summary: 60 * 60 * 1000
} as const;
const GC_TIME = {
  bootstrap: 15 * 60 * 1000,
  templates: 20 * 60 * 1000,
  page: 10 * 60 * 1000,
  database: 10 * 60 * 1000,
  search: 5 * 60 * 1000,
  backlinks: 5 * 60 * 1000,
  summary: 60 * 60 * 1000
} as const;
const RECENT_DEBOUNCE_MS = 350;
const RECENT_SUPPRESSION_MS = 60 * 1000;

type WorkspacePageSummaryRecord = Pick<WorkspacePageSummary, 'id' | 'title' | 'kind' | 'icon'> &
  Partial<WorkspacePageSummary>;

const workspaceKeys = {
  bootstrap: () => [...WORKSPACE_KEY, 'bootstrap'] as const,
  page: (pageId: number | null) => [...WORKSPACE_KEY, 'page', pageId] as const,
  pageSummary: (pageId: number | null) => [...WORKSPACE_KEY, 'pageSummary', pageId] as const,
  backlinks: (pageId: number | null) => [...WORKSPACE_KEY, 'backlinks', pageId] as const,
  database: (
    databaseId: number | null,
    viewId?: number | null,
    offset = 0,
    limit = 50,
    relationPropertySlug?: string | null,
    relationPageId?: number | null
  ) => [...WORKSPACE_KEY, 'database', databaseId, viewId ?? null, offset, limit, relationPropertySlug ?? null, relationPageId ?? null] as const,
  search: (query: string) => [...WORKSPACE_KEY, 'search', query] as const,
  templates: (databaseId?: number | null) => [...WORKSPACE_KEY, 'templates', databaseId ?? null] as const
};

const lastRecentMarkedAt = new Map<number, number>();

function toPageSummaryRecord(
  page: (Pick<WorkspacePageSummary, 'id' | 'title' | 'kind' | 'icon'> & Partial<WorkspacePageSummary>) | WorkspacePageLink
): WorkspacePageSummaryRecord {
  return {
    ...page,
    icon: page.icon ?? null
  };
}

function mergePageSummary(
  current: WorkspacePageSummaryRecord | undefined,
  incoming:
    | (Pick<WorkspacePageSummary, 'id' | 'title' | 'kind' | 'icon'> & Partial<WorkspacePageSummary>)
    | WorkspacePageLink
): WorkspacePageSummaryRecord {
  const next = toPageSummaryRecord(incoming);
  return {
    ...(current ?? {}),
    ...next,
    id: next.id,
    title: next.title ?? current?.title ?? 'Untitled',
    kind: next.kind ?? current?.kind ?? 'page',
    icon: next.icon ?? current?.icon ?? null
  };
}

function seedPageSummary(
  queryClient: QueryClient,
  page:
    | (Pick<WorkspacePageSummary, 'id' | 'title' | 'kind' | 'icon'> & Partial<WorkspacePageSummary>)
    | WorkspacePageLink
    | null
    | undefined
) {
  if (!page) return;
  queryClient.setQueryData<WorkspacePageSummaryRecord | undefined>(
    workspaceKeys.pageSummary(page.id),
    (current) => mergePageSummary(current, page)
  );
}

function seedPageSummaries(
  queryClient: QueryClient,
  pages: Array<(Pick<WorkspacePageSummary, 'id' | 'title' | 'kind' | 'icon'> & Partial<WorkspacePageSummary>) | WorkspacePageLink | null | undefined>
) {
  for (const page of pages) seedPageSummary(queryClient, page);
}

function patchPageInList<T extends WorkspacePageSummary | WorkspacePageLink>(
  pages: T[],
  summary: WorkspacePageSummaryRecord
): T[] {
  return pages.map((page) =>
    page.id === summary.id
      ? ({
          ...page,
          ...summary,
          icon: summary.icon ?? page.icon ?? null
        } as T)
      : page
  );
}

function patchPageSummaryAcrossWorkspace(queryClient: QueryClient, summary: WorkspacePageSummaryRecord) {
  seedPageSummary(queryClient, summary);
  queryClient.setQueriesData({ queryKey: WORKSPACE_KEY }, (current) => {
    if (!current || typeof current !== 'object') return current;

    if ('home_page_id' in current && 'sidebar_pages' in current) {
      const bootstrap = current as WorkspaceBootstrap;
      return {
        ...bootstrap,
        sidebar_pages: patchPageInList(bootstrap.sidebar_pages, summary),
        favorites: patchPageInList(bootstrap.favorites, summary),
        recent_pages: patchPageInList(bootstrap.recent_pages, summary),
        trash_pages: patchPageInList(bootstrap.trash_pages, summary)
      };
    }

    if ('page' in current && 'blocks' in current) {
      const detail = current as WorkspacePageDetail;
      return {
        ...detail,
        page: detail.page.id === summary.id ? { ...detail.page, ...summary } : detail.page,
        breadcrumbs: patchPageInList(detail.breadcrumbs, summary),
        children: patchPageInList(detail.children, summary),
        blocks: detail.blocks.map((block) => ({
          ...block,
          links: patchPageInList(block.links, summary)
        }))
      };
    }

    if ('rows' in current && 'database' in current) {
      const rowsResponse = current as WorkspaceDatabaseRowsResponse;
      return {
        ...rowsResponse,
        rows: rowsResponse.rows.map((row) =>
          row.page.id === summary.id
            ? {
                ...row,
                page: { ...row.page, ...summary },
                properties: row.properties.map((property) =>
                  property.property_slug === 'title' ? { ...property, value: summary.title } : property
                )
              }
            : row
        )
      };
    }

    if ('results' in current) {
      const searchResponse = current as WorkspaceSearchResponse;
      return {
        ...searchResponse,
        results: searchResponse.results.map((result) =>
          result.page.id === summary.id ? { ...result, page: { ...result.page, ...summary } } : result
        )
      };
    }

    if ('backlinks' in current) {
      const backlinksResponse = current as WorkspaceBacklinksResponse;
      return {
        ...backlinksResponse,
        backlinks: backlinksResponse.backlinks.map((backlink) =>
          backlink.source_page.id === summary.id
            ? {
                ...backlink,
                source_page: {
                  ...backlink.source_page,
                  title: summary.title,
                  kind: summary.kind,
                  icon: summary.icon ?? backlink.source_page.icon ?? null
                }
              }
            : backlink
        )
      };
    }

    return current;
  });
}

function removePageFromWorkspaceCaches(queryClient: QueryClient, pageId: number) {
  queryClient.removeQueries({ queryKey: workspaceKeys.page(pageId) });
  queryClient.removeQueries({ queryKey: workspaceKeys.backlinks(pageId) });
  queryClient.removeQueries({ queryKey: workspaceKeys.pageSummary(pageId) });
  queryClient.setQueriesData({ queryKey: WORKSPACE_KEY }, (current) => {
    if (!current || typeof current !== 'object') return current;

    if ('home_page_id' in current && 'sidebar_pages' in current) {
      const bootstrap = current as WorkspaceBootstrap;
      return {
        ...bootstrap,
        sidebar_pages: bootstrap.sidebar_pages.filter((page) => page.id !== pageId),
        favorites: bootstrap.favorites.filter((page) => page.id !== pageId),
        recent_pages: bootstrap.recent_pages.filter((page) => page.id !== pageId),
        trash_pages: bootstrap.trash_pages.filter((page) => page.id !== pageId)
      };
    }

    if ('rows' in current && 'database' in current) {
      const rowsResponse = current as WorkspaceDatabaseRowsResponse;
      return {
        ...rowsResponse,
        rows: rowsResponse.rows.filter((row) => row.page.id !== pageId),
        total_count: Math.max(0, rowsResponse.rows.filter((row) => row.page.id !== pageId).length)
      };
    }

    if ('results' in current) {
      const searchResponse = current as WorkspaceSearchResponse;
      return {
        ...searchResponse,
        results: searchResponse.results.filter((result) => result.page.id !== pageId)
      };
    }

    if ('backlinks' in current) {
      const backlinksResponse = current as WorkspaceBacklinksResponse;
      return {
        ...backlinksResponse,
        backlinks: backlinksResponse.backlinks.filter((backlink) => backlink.source_page.id !== pageId)
      };
    }

    return current;
  });
}

function normalizeBootstrap(queryClient: QueryClient, bootstrap: WorkspaceBootstrap) {
  seedPageSummaries(queryClient, [
    ...bootstrap.sidebar_pages,
    ...bootstrap.favorites,
    ...bootstrap.recent_pages,
    ...bootstrap.trash_pages
  ]);
}

function normalizePageDetail(queryClient: QueryClient, detail: WorkspacePageDetail) {
  seedPageSummaries(queryClient, [
    detail.page,
    ...detail.breadcrumbs,
    ...detail.children,
    ...detail.blocks.flatMap((block) => block.links)
  ]);
}

function normalizeDatabaseRows(queryClient: QueryClient, response: WorkspaceDatabaseRowsResponse) {
  seedPageSummaries(queryClient, response.rows.map((row) => row.page));
}

function normalizeSearch(queryClient: QueryClient, response: WorkspaceSearchResponse) {
  seedPageSummaries(queryClient, response.results.map((result) => result.page));
}

function normalizeBacklinks(queryClient: QueryClient, response: WorkspaceBacklinksResponse) {
  seedPageSummaries(queryClient, response.backlinks.map((backlink) => backlink.source_page));
}

function getBootstrapData(queryClient: QueryClient) {
  return queryClient.getQueryData<WorkspaceBootstrap>(workspaceKeys.bootstrap());
}

function findDatabaseIdByName(queryClient: QueryClient, name: string): number | null {
  const bootstrap = getBootstrapData(queryClient);
  return bootstrap?.databases.find((database) => database.name === name)?.id ?? null;
}

async function invalidateDatabaseQueries(queryClient: QueryClient, databaseId: number | null | undefined) {
  if (!databaseId) return;
  await queryClient.invalidateQueries({
    predicate: (query) =>
      Array.isArray(query.queryKey) &&
      query.queryKey[0] === WORKSPACE_KEY[0] &&
      query.queryKey[1] === 'database' &&
      query.queryKey[2] === databaseId
  });
}

async function invalidateSearchQueries(queryClient: QueryClient) {
  await queryClient.invalidateQueries({
    predicate: (query) =>
      Array.isArray(query.queryKey) &&
      query.queryKey[0] === WORKSPACE_KEY[0] &&
      query.queryKey[1] === 'search'
  });
}

function patchBootstrapRecent(queryClient: QueryClient, pageId: number) {
  const summary = queryClient.getQueryData<WorkspacePageSummaryRecord>(workspaceKeys.pageSummary(pageId));
  if (!summary) return;
  queryClient.setQueryData<WorkspaceBootstrap | undefined>(workspaceKeys.bootstrap(), (current) => {
    if (!current) return current;
    const nextRecents = [
      summary as WorkspacePageSummary,
      ...current.recent_pages.filter((page) => page.id !== summary.id)
    ].slice(0, 15);
    return {
      ...current,
      recent_pages: nextRecents
    };
  });
}

function getCachedPageDetail(queryClient: QueryClient, pageId: number) {
  return queryClient.getQueryData<WorkspacePageDetail>(workspaceKeys.page(pageId));
}

export const useWorkspaceBootstrap = () => {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: workspaceKeys.bootstrap(),
    queryFn: fetchWorkspaceBootstrap,
    staleTime: STALE_TIME.bootstrap,
    gcTime: GC_TIME.bootstrap
  });

  useEffect(() => {
    if (query.data) normalizeBootstrap(queryClient, query.data);
  }, [query.data, queryClient]);

  return query;
};

export const useWorkspacePage = (pageId: number | null) => {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: workspaceKeys.page(pageId),
    queryFn: async () => {
      const detail = await fetchWorkspacePage(pageId!);
      normalizePageDetail(queryClient, detail);
      return detail;
    },
    enabled: pageId !== null && Number.isFinite(pageId),
    staleTime: STALE_TIME.page,
    gcTime: GC_TIME.page
  });

  useEffect(() => {
    if (query.data) normalizePageDetail(queryClient, query.data);
  }, [query.data, queryClient]);

  return query;
};

export const useWorkspaceBacklinks = (pageId: number | null, enabled = true) => {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: workspaceKeys.backlinks(pageId),
    queryFn: async () => {
      const backlinks = await fetchWorkspaceBacklinks(pageId!);
      normalizeBacklinks(queryClient, backlinks);
      return backlinks;
    },
    enabled: enabled && pageId !== null && Number.isFinite(pageId),
    staleTime: STALE_TIME.backlinks,
    gcTime: GC_TIME.backlinks
  });

  useEffect(() => {
    if (query.data) normalizeBacklinks(queryClient, query.data);
  }, [query.data, queryClient]);

  return query;
};

export const useWorkspacePageSummary = (
  pageId: number | null,
  fallback?: (Pick<WorkspacePageSummary, 'id' | 'title' | 'kind' | 'icon'> & Partial<WorkspacePageSummary>) | WorkspacePageLink | null
) => {
  const queryClient = useQueryClient();

  useEffect(() => {
    if (fallback) seedPageSummary(queryClient, fallback);
  }, [
    fallback?.id,
    fallback?.title,
    fallback?.kind,
    fallback?.icon,
    queryClient
  ]);

  return useQuery({
    queryKey: workspaceKeys.pageSummary(pageId),
    queryFn: async () => null,
    enabled: false,
    initialData:
      pageId !== null && Number.isFinite(pageId)
        ? queryClient.getQueryData<WorkspacePageSummaryRecord>(workspaceKeys.pageSummary(pageId)) ??
          (fallback ? mergePageSummary(undefined, fallback) : undefined)
        : undefined,
    staleTime: STALE_TIME.summary,
    gcTime: GC_TIME.summary
  });
};

export const useWorkspaceDatabase = (
  databaseId: number | null,
  viewId?: number | null,
  enabled = true,
  offset = 0,
  limit = 50,
  relationPropertySlug?: string | null,
  relationPageId?: number | null
) => {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: workspaceKeys.database(databaseId, viewId, offset, limit, relationPropertySlug, relationPageId),
    queryFn: async () => {
      const response = await fetchWorkspaceDatabaseRows(
        databaseId!,
        viewId,
        offset,
        limit,
        relationPropertySlug,
        relationPageId
      );
      normalizeDatabaseRows(queryClient, response);
      return response;
    },
    enabled: enabled && databaseId !== null && Number.isFinite(databaseId),
    staleTime: STALE_TIME.database,
    gcTime: GC_TIME.database
  });

  useEffect(() => {
    if (query.data) normalizeDatabaseRows(queryClient, query.data);
  }, [query.data, queryClient]);

  return query;
};

export const useWorkspaceSearch = (query: string, enabled = true) => {
  const queryClient = useQueryClient();
  const searchQuery = useQuery({
    queryKey: workspaceKeys.search(query),
    queryFn: async () => {
      const response = await searchWorkspace(query);
      normalizeSearch(queryClient, response);
      return response;
    },
    enabled: enabled && query.trim().length > 0,
    staleTime: STALE_TIME.search,
    gcTime: GC_TIME.search
  });

  useEffect(() => {
    if (searchQuery.data) normalizeSearch(queryClient, searchQuery.data);
  }, [searchQuery.data, queryClient]);

  return searchQuery;
};

export const useWorkspaceTemplates = (databaseId?: number | null) =>
  useQuery({
    queryKey: workspaceKeys.templates(databaseId),
    queryFn: () => fetchWorkspaceTemplates(databaseId),
    enabled: databaseId !== undefined,
    staleTime: STALE_TIME.templates,
    gcTime: GC_TIME.templates
  });

export function useWorkspacePrefetch() {
  const queryClient = useQueryClient();

  return {
    prefetchWorkspacePage: useCallback((pageId: number) =>
      queryClient.prefetchQuery({
        queryKey: workspaceKeys.page(pageId),
        queryFn: async () => {
          const detail = await fetchWorkspacePage(pageId);
          normalizePageDetail(queryClient, detail);
          return detail;
        },
        staleTime: STALE_TIME.page,
        gcTime: GC_TIME.page
      }), [queryClient])
  };
}

export function useWorkspaceRecentTracker() {
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: markWorkspaceRecent
  });

  return useCallback((pageId: number) => {
    const now = Date.now();
    const lastMarked = lastRecentMarkedAt.get(pageId) ?? 0;
    if (now - lastMarked < RECENT_SUPPRESSION_MS) return;
    lastRecentMarkedAt.set(pageId, now);
    patchBootstrapRecent(queryClient, pageId);
    window.setTimeout(() => {
      void mutation.mutateAsync(pageId).catch(() => {
        lastRecentMarkedAt.delete(pageId);
      });
    }, RECENT_DEBOUNCE_MS);
  }, [mutation, queryClient]);
}

export function useWorkspaceMutations() {
  const queryClient = useQueryClient();

  return {
    createPage: useMutation({
      mutationFn: createWorkspacePage,
      onSuccess: async (data, variables) => {
        normalizePageDetail(queryClient, data);
        queryClient.setQueryData(workspaceKeys.page(data.page.id), data);
        if (variables.show_in_sidebar !== false) {
          await queryClient.invalidateQueries({ queryKey: workspaceKeys.bootstrap() });
        }
        await invalidateSearchQueries(queryClient);
      }
    }).mutateAsync,
    updatePage: useMutation({
      mutationFn: ({ pageId, payload }: { pageId: number; payload: Parameters<typeof updateWorkspacePage>[1] }) =>
        updateWorkspacePage(pageId, payload),
      onSuccess: async (data, variables) => {
        normalizePageDetail(queryClient, data);
        queryClient.setQueryData(workspaceKeys.page(data.page.id), data);
        patchPageSummaryAcrossWorkspace(queryClient, data.page);
        if (data.database?.id) {
          await invalidateDatabaseQueries(queryClient, data.database.id);
          if (data.database.name === 'Tasks' && variables.payload.trashed !== undefined) {
            await invalidateDatabaseQueries(queryClient, findDatabaseIdByName(queryClient, 'Projects'));
          }
        }
        if (
          variables.payload.favorite !== undefined ||
          variables.payload.trashed !== undefined ||
          variables.payload.show_in_sidebar !== undefined ||
          variables.payload.parent_page_id !== undefined ||
          variables.payload.sort_order !== undefined
        ) {
          await queryClient.invalidateQueries({ queryKey: workspaceKeys.bootstrap() });
        }
        if (variables.payload.title !== undefined) {
          await invalidateSearchQueries(queryClient);
        }
      }
    }).mutateAsync,
    createBlock: useMutation({
      mutationFn: createWorkspaceBlock,
      onSuccess: async (data) => {
        normalizePageDetail(queryClient, data);
        queryClient.setQueryData(workspaceKeys.page(data.page.id), data);
        await invalidateSearchQueries(queryClient);
      }
    }).mutateAsync,
    updateBlock: useMutation({
      mutationFn: ({ blockId, payload }: { blockId: number; payload: Parameters<typeof updateWorkspaceBlock>[1] }) =>
        updateWorkspaceBlock(blockId, payload),
      onSuccess: async (data, variables) => {
        normalizePageDetail(queryClient, data);
        queryClient.setQueryData(workspaceKeys.page(data.page.id), data);
        if (variables.payload.text_content !== undefined || variables.payload.block_type !== undefined) {
          await invalidateSearchQueries(queryClient);
        }
      }
    }).mutateAsync,
    deleteBlock: useMutation({
      mutationFn: async (blockId: number) => {
        const affectedPageIds = queryClient
          .getQueriesData<WorkspacePageDetail>({ queryKey: WORKSPACE_KEY })
          .flatMap(([, data]) => (data?.blocks?.some((block) => block.id === blockId) ? [data.page.id] : []));
        await deleteWorkspaceBlock(blockId);
        return affectedPageIds;
      },
      onSuccess: async (affectedPageIds) => {
        for (const pageId of affectedPageIds) {
          await queryClient.invalidateQueries({ queryKey: workspaceKeys.page(pageId) });
        }
        await invalidateSearchQueries(queryClient);
      }
    }).mutateAsync,
    deletePage: useMutation({
      mutationFn: async (pageId: number) => {
        const cachedDetail = getCachedPageDetail(queryClient, pageId);
        await deleteWorkspacePage(pageId);
        return { pageId, cachedDetail };
      },
      onSuccess: async ({ pageId, cachedDetail }) => {
        removePageFromWorkspaceCaches(queryClient, pageId);
        await queryClient.invalidateQueries({ queryKey: workspaceKeys.bootstrap() });
        if (cachedDetail?.database?.id) {
          await invalidateDatabaseQueries(queryClient, cachedDetail.database.id);
          if (cachedDetail.database.name === 'Tasks') {
            await invalidateDatabaseQueries(queryClient, findDatabaseIdByName(queryClient, 'Projects'));
          }
        }
        await invalidateSearchQueries(queryClient);
      }
    }).mutateAsync,
    reorderBlocks: useMutation({
      mutationFn: reorderWorkspaceBlocks,
      onSuccess: async (_, variables) => {
        await queryClient.invalidateQueries({ queryKey: workspaceKeys.page(variables.page_id) });
      }
    }).mutateAsync,
    createRow: useMutation({
      mutationFn: ({ databaseId, payload }: { databaseId: number; payload: Parameters<typeof createWorkspaceRow>[1] }) =>
        createWorkspaceRow(databaseId, payload),
      onSuccess: async (data) => {
        normalizePageDetail(queryClient, data);
        queryClient.setQueryData(workspaceKeys.page(data.page.id), data);
        if (data.database?.id) {
          await invalidateDatabaseQueries(queryClient, data.database.id);
          if (data.database.name === 'Projects') {
            await queryClient.invalidateQueries({ queryKey: workspaceKeys.bootstrap() });
          }
          if (data.database.name === 'Tasks') {
            await invalidateDatabaseQueries(queryClient, findDatabaseIdByName(queryClient, 'Projects'));
          }
        }
        await invalidateSearchQueries(queryClient);
      }
    }).mutateAsync,
    updateProperties: useMutation({
      mutationFn: ({ pageId, values }: { pageId: number; values: Record<string, unknown> }) =>
        updateWorkspacePageProperties(pageId, values),
      onSuccess: async (data, variables) => {
        normalizePageDetail(queryClient, data);
        queryClient.setQueryData(workspaceKeys.page(data.page.id), data);
        patchPageSummaryAcrossWorkspace(queryClient, data.page);
        if (data.database?.id) {
          await invalidateDatabaseQueries(queryClient, data.database.id);
          if (data.database.name === 'Tasks' && ('project' in variables.values || 'status' in variables.values)) {
            await invalidateDatabaseQueries(queryClient, findDatabaseIdByName(queryClient, 'Projects'));
          }
        }
        if ('title' in variables.values) {
          await invalidateSearchQueries(queryClient);
        }
      }
    }).mutateAsync,
    createView: useMutation({
      mutationFn: ({ databaseId, payload }: { databaseId: number; payload: Parameters<typeof createWorkspaceView>[1] }) =>
        createWorkspaceView(databaseId, payload),
      onSuccess: async (data) => {
        normalizeDatabaseRows(queryClient, data);
        await invalidateDatabaseQueries(queryClient, data.database.id);
      }
    }).mutateAsync,
    updateView: useMutation({
      mutationFn: ({ viewId, payload }: { viewId: number; payload: Parameters<typeof updateWorkspaceView>[1] }) =>
        updateWorkspaceView(viewId, payload),
      onSuccess: async (_, variables) => {
        await queryClient.invalidateQueries({
          predicate: (query) =>
            Array.isArray(query.queryKey) &&
            query.queryKey[0] === WORKSPACE_KEY[0] &&
            query.queryKey[1] === 'database' &&
            query.queryKey[3] === variables.viewId
        });
      }
    }).mutateAsync,
    applyTemplate: useMutation({
      mutationFn: ({ templateId, payload }: { templateId: number; payload: Parameters<typeof applyWorkspaceTemplate>[1] }) =>
        applyWorkspaceTemplate(templateId, payload),
      onSuccess: async (data) => {
        normalizePageDetail(queryClient, data);
        queryClient.setQueryData(workspaceKeys.page(data.page.id), data);
        if (data.database?.id) {
          await invalidateDatabaseQueries(queryClient, data.database.id);
          if (data.database.name === 'Projects') {
            await queryClient.invalidateQueries({ queryKey: workspaceKeys.bootstrap() });
          }
        }
        await invalidateSearchQueries(queryClient);
      }
    }).mutateAsync
  };
}
