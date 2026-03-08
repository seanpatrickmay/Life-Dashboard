import { describe, expect, it } from 'vitest';

import {
  getGuestWorkspaceBacklinks,
  getGuestWorkspaceBootstrap,
  getGuestWorkspaceDatabaseRows,
  getGuestWorkspacePage,
  searchGuestWorkspace
} from './guestWorkspace';

describe('guestWorkspace', () => {
  it('returns a read-only bootstrap payload', async () => {
    const bootstrap = await getGuestWorkspaceBootstrap();

    expect(bootstrap.read_only).toBe(true);
    expect(bootstrap.home_page_id).toBe(1000);
    expect(bootstrap.databases.map((database) => database.name)).toEqual(['Projects', 'Tasks']);
  });

  it('filters the triage task view to suggested and unassigned work', async () => {
    const triageRows = await getGuestWorkspaceDatabaseRows(3002, 4105);

    expect(triageRows.view?.name).toBe('Triage');
    expect(triageRows.rows.map((row) => row.page.title)).toEqual(['Set up homepage like Notion']);
  });

  it('exposes richer view metadata for gallery and open mode flows', async () => {
    const galleryRows = await getGuestWorkspaceDatabaseRows(3001, 4003);

    expect(galleryRows.view?.view_type).toBe('gallery');
    expect((galleryRows.view?.config_json as Record<string, unknown>).open_mode).toBe('center_peek');
  });

  it('returns linked databases on the home page and supports block-text search', async () => {
    const home = await getGuestWorkspacePage(1000);
    const project = await getGuestWorkspacePage(1104);
    const search = await searchGuestWorkspace('unblock future page');
    const backlinks = await getGuestWorkspaceBacklinks(1302);

    expect(home.linked_databases.map((database) => database.name)).toEqual(['Projects', 'Tasks']);
    expect(project.children.map((child) => child.title)).toEqual(['Capital One launch brief']);
    expect(project.children[0]?.kind).toBe('note');
    expect('backlinks' in home).toBe(false);
    expect(backlinks.backlinks[0]?.source_page.title).toBe('Capital One Onboarding');
    expect(backlinks.backlinks[0]?.snippet).toContain('Capital One launch brief');
    expect(search.results.some((result) => result.page.title === 'Capital One launch brief')).toBe(true);
  });
});
