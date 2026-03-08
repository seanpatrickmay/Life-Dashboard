import { api } from './api';
import { isGuestMode } from '../demo/guest/guestMode';
import {
  applyGuestWorkspaceTemplate,
  createGuestWorkspaceAssetUpload,
  createGuestWorkspaceBlock,
  createGuestWorkspacePage,
  createGuestWorkspaceRow,
  createGuestWorkspaceView,
  deleteGuestWorkspacePage,
  deleteGuestWorkspaceBlock,
  getGuestWorkspaceBacklinks,
  getGuestWorkspaceBootstrap,
  getGuestWorkspaceDatabaseRows,
  getGuestWorkspacePage,
  listGuestWorkspaceTemplates,
  markGuestWorkspaceRecent,
  reorderGuestWorkspaceBlocks,
  searchGuestWorkspace,
  updateGuestWorkspaceBlock,
  updateGuestWorkspacePage,
  updateGuestWorkspacePageProperties,
  updateGuestWorkspaceView
} from '../demo/guest/guestWorkspace';

export type WorkspacePageSummary = {
  id: number;
  parent_page_id: number | null;
  title: string;
  kind: string;
  icon: string | null;
  cover_url: string | null;
  description: string | null;
  show_in_sidebar: boolean;
  sort_order: number;
  is_home: boolean;
  trashed_at: string | null;
  legacy_project_id: number | null;
  legacy_todo_id: number | null;
  legacy_note_id: number | null;
  created_at: string;
  updated_at: string;
};

export type WorkspacePropertyOption = {
  id: number;
  label: string;
  value: string;
  color: string | null;
  sort_order: number;
};

export type WorkspaceProperty = {
  id: number;
  name: string;
  slug: string;
  property_type: string;
  sort_order: number;
  required: boolean;
  config_json: Record<string, unknown> | unknown[] | null;
  options: WorkspacePropertyOption[];
};

export type WorkspacePropertyValue = {
  property_id: number;
  property_slug: string;
  property_name: string;
  property_type: string;
  value: unknown;
};

export type WorkspaceView = {
  id: number;
  name: string;
  view_type: string;
  sort_order: number;
  is_default: boolean;
  config_json: Record<string, unknown> | unknown[] | null;
};

export type WorkspaceOpenMode = 'side_peek' | 'center_peek' | 'full_page';

export type WorkspacePageLink = {
  id: number;
  title: string;
  kind: string;
  icon: string | null;
};

export type WorkspaceBlock = {
  id: number;
  page_id: number;
  parent_block_id: number | null;
  block_type: string;
  sort_order: number;
  text_content: string;
  checked: boolean;
  data_json: Record<string, unknown> | unknown[] | null;
  links: WorkspacePageLink[];
};

export type WorkspaceDatabaseSummary = {
  id: number;
  page_id: number;
  name: string;
  description: string | null;
  icon: string | null;
  is_seeded: boolean;
  properties: WorkspaceProperty[];
  views: WorkspaceView[];
};

export type WorkspaceRow = {
  page: WorkspacePageSummary;
  properties: WorkspacePropertyValue[];
};

export type WorkspaceBacklink = {
  source_page: WorkspacePageLink;
  block_id: number | null;
  snippet: string | null;
};

export type WorkspaceBacklinksResponse = {
  backlinks: WorkspaceBacklink[];
};

export type WorkspacePageDetail = {
  page: WorkspacePageSummary;
  breadcrumbs: WorkspacePageSummary[];
  children: WorkspacePageSummary[];
  properties: WorkspacePropertyValue[];
  blocks: WorkspaceBlock[];
  database: WorkspaceDatabaseSummary | null;
  linked_databases: WorkspaceDatabaseSummary[];
  favorite: boolean;
};

export type WorkspaceBootstrap = {
  home_page_id: number;
  read_only: boolean;
  sidebar_pages: WorkspacePageSummary[];
  favorites: WorkspacePageSummary[];
  recent_pages: WorkspacePageSummary[];
  trash_pages: WorkspacePageSummary[];
  databases: WorkspaceDatabaseSummary[];
};

export type WorkspaceSearchResult = {
  page: WorkspacePageSummary;
  match: string | null;
};

export type WorkspaceSearchResponse = {
  results: WorkspaceSearchResult[];
};

export type WorkspaceDatabaseRowsResponse = {
  database: WorkspaceDatabaseSummary;
  view: WorkspaceView | null;
  rows: WorkspaceRow[];
  total_count: number;
  offset: number;
  limit: number;
  has_more: boolean;
};

export type WorkspaceTemplate = {
  id: number;
  database_id: number | null;
  name: string;
  title: string | null;
  icon: string | null;
  cover_url: string | null;
  sort_order: number;
};

export type WorkspaceAssetUpload = {
  asset_id: number;
  upload_url: string;
  public_url: string;
  headers: Record<string, string>;
  status: string;
};

export const fetchWorkspaceBootstrap = async (): Promise<WorkspaceBootstrap> => {
  if (isGuestMode()) return getGuestWorkspaceBootstrap();
  const { data } = await api.get('/api/workspace/bootstrap');
  return data as WorkspaceBootstrap;
};

export const fetchWorkspacePage = async (pageId: number): Promise<WorkspacePageDetail> => {
  if (isGuestMode()) return getGuestWorkspacePage(pageId);
  const { data } = await api.get(`/api/workspace/pages/${pageId}`);
  return data as WorkspacePageDetail;
};

export const fetchWorkspaceBacklinks = async (pageId: number): Promise<WorkspaceBacklinksResponse> => {
  if (isGuestMode()) return getGuestWorkspaceBacklinks(pageId);
  const { data } = await api.get(`/api/workspace/pages/${pageId}/backlinks`);
  return data as WorkspaceBacklinksResponse;
};

export const markWorkspaceRecent = async (pageId: number): Promise<void> => {
  if (isGuestMode()) return markGuestWorkspaceRecent(pageId);
  await api.post(`/api/workspace/pages/${pageId}/recent`);
};

export const createWorkspacePage = async (payload: {
  title: string;
  parent_page_id?: number | null;
  kind?: string;
  icon?: string | null;
  cover_url?: string | null;
  description?: string | null;
  show_in_sidebar?: boolean;
  template_id?: number | null;
  database_page_id?: number | null;
  sort_order?: number | null;
  extra_json?: Record<string, unknown> | unknown[] | null;
}): Promise<WorkspacePageDetail> => {
  if (isGuestMode()) return createGuestWorkspacePage(payload);
  const { data } = await api.post('/api/workspace/pages', payload);
  return data as WorkspacePageDetail;
};

export const updateWorkspacePage = async (
  pageId: number,
  payload: {
    title?: string;
    icon?: string | null;
    cover_url?: string | null;
    description?: string | null;
    parent_page_id?: number | null;
    show_in_sidebar?: boolean;
    sort_order?: number;
    favorite?: boolean;
    trashed?: boolean;
  }
): Promise<WorkspacePageDetail> => {
  if (isGuestMode()) return updateGuestWorkspacePage(pageId, payload);
  const { data } = await api.patch(`/api/workspace/pages/${pageId}`, payload);
  return data as WorkspacePageDetail;
};

export const deleteWorkspacePage = async (pageId: number): Promise<void> => {
  if (isGuestMode()) return deleteGuestWorkspacePage(pageId);
  await api.delete(`/api/workspace/pages/${pageId}`);
};

export const createWorkspaceBlock = async (payload: {
  page_id: number;
  after_block_id?: number | null;
  block_type?: string;
  text_content?: string;
  checked?: boolean;
  data_json?: Record<string, unknown> | unknown[] | null;
}): Promise<WorkspacePageDetail> => {
  if (isGuestMode()) return createGuestWorkspaceBlock(payload);
  const { data } = await api.post('/api/workspace/blocks', payload);
  return data as WorkspacePageDetail;
};

export const updateWorkspaceBlock = async (
  blockId: number,
  payload: {
    block_type?: string;
    text_content?: string;
    checked?: boolean;
    data_json?: Record<string, unknown> | unknown[] | null;
  }
): Promise<WorkspacePageDetail> => {
  if (isGuestMode()) return updateGuestWorkspaceBlock(blockId, payload);
  const { data } = await api.patch(`/api/workspace/blocks/${blockId}`, payload);
  return data as WorkspacePageDetail;
};

export const deleteWorkspaceBlock = async (blockId: number): Promise<void> => {
  if (isGuestMode()) return deleteGuestWorkspaceBlock(blockId);
  await api.delete(`/api/workspace/blocks/${blockId}`);
};

export const reorderWorkspaceBlocks = async (payload: {
  page_id: number;
  ordered_block_ids: number[];
}): Promise<void> => {
  if (isGuestMode()) return reorderGuestWorkspaceBlocks(payload);
  await api.post('/api/workspace/blocks/reorder', payload);
};

export const fetchWorkspaceDatabaseRows = async (
  databaseId: number,
  viewId?: number | null,
  offset = 0,
  limit = 50,
  relationPropertySlug?: string | null,
  relationPageId?: number | null
): Promise<WorkspaceDatabaseRowsResponse> => {
  if (isGuestMode()) {
    return getGuestWorkspaceDatabaseRows(
      databaseId,
      viewId ?? undefined,
      offset,
      limit,
      relationPropertySlug ?? undefined,
      relationPageId ?? undefined
    );
  }
  const { data } = await api.get(`/api/workspace/databases/${databaseId}/rows`, {
    params: {
      ...(viewId ? { view_id: viewId } : {}),
      ...(relationPropertySlug ? { relation_property_slug: relationPropertySlug } : {}),
      ...(relationPageId ? { relation_page_id: relationPageId } : {}),
      offset,
      limit
    }
  });
  return data as WorkspaceDatabaseRowsResponse;
};

export const createWorkspaceRow = async (
  databaseId: number,
  payload: { title: string; properties?: Record<string, unknown>; template_id?: number | null }
): Promise<WorkspacePageDetail> => {
  if (isGuestMode()) return createGuestWorkspaceRow(databaseId, payload);
  const { data } = await api.post(`/api/workspace/databases/${databaseId}/rows`, payload);
  return data as WorkspacePageDetail;
};

export const updateWorkspacePageProperties = async (
  pageId: number,
  values: Record<string, unknown>
): Promise<WorkspacePageDetail> => {
  if (isGuestMode()) return updateGuestWorkspacePageProperties(pageId, values);
  const { data } = await api.patch(`/api/workspace/pages/${pageId}/properties`, { values });
  return data as WorkspacePageDetail;
};

export const createWorkspaceView = async (
  databaseId: number,
  payload: { name: string; view_type: string; is_default?: boolean; config_json?: Record<string, unknown> | unknown[] | null }
): Promise<WorkspaceDatabaseRowsResponse> => {
  if (isGuestMode()) return createGuestWorkspaceView(databaseId, payload);
  const { data } = await api.post(`/api/workspace/databases/${databaseId}/views`, payload);
  return data as WorkspaceDatabaseRowsResponse;
};

export const updateWorkspaceView = async (
  viewId: number,
  payload: { name?: string; is_default?: boolean; config_json?: Record<string, unknown> | unknown[] | null }
): Promise<WorkspaceView> => {
  if (isGuestMode()) return updateGuestWorkspaceView(viewId, payload);
  const { data } = await api.patch(`/api/workspace/views/${viewId}`, payload);
  return data as WorkspaceView;
};

export const searchWorkspace = async (query: string): Promise<WorkspaceSearchResponse> => {
  if (isGuestMode()) return searchGuestWorkspace(query);
  const { data } = await api.get('/api/workspace/search', { params: { q: query } });
  return data as WorkspaceSearchResponse;
};

export const fetchWorkspaceTemplates = async (databaseId?: number | null): Promise<WorkspaceTemplate[]> => {
  if (isGuestMode()) return listGuestWorkspaceTemplates(databaseId ?? undefined);
  const { data } = await api.get('/api/workspace/templates', {
    params: databaseId ? { database_id: databaseId } : undefined
  });
  return data as WorkspaceTemplate[];
};

export const applyWorkspaceTemplate = async (
  templateId: number,
  payload: { title?: string; properties?: Record<string, unknown> }
): Promise<WorkspacePageDetail> => {
  if (isGuestMode()) return applyGuestWorkspaceTemplate(templateId, payload);
  const { data } = await api.post(`/api/workspace/templates/${templateId}/apply`, payload);
  return data as WorkspacePageDetail;
};

export const createWorkspaceAssetUpload = async (payload: {
  page_id?: number | null;
  block_id?: number | null;
  name: string;
  mime_type?: string | null;
  size_bytes?: number | null;
}): Promise<WorkspaceAssetUpload> => {
  if (isGuestMode()) return createGuestWorkspaceAssetUpload(payload);
  const { data } = await api.post('/api/workspace/assets/sign', payload);
  return data as WorkspaceAssetUpload;
};

export const uploadWorkspaceAssetContent = async (
  uploadUrl: string,
  file: File,
  headers: Record<string, string> = {}
): Promise<void> => {
  const body = new FormData();
  body.append('file', file);
  const response = await fetch(uploadUrl, {
    method: 'PUT',
    body,
    headers,
    credentials: 'include',
  });
  if (!response.ok) {
    throw new Error('Could not upload workspace asset.');
  }
};
