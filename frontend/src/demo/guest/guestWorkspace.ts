import type {
  WorkspaceAssetUpload,
  WorkspaceBacklinksResponse,
  WorkspaceBlock,
  WorkspaceBootstrap,
  WorkspaceDatabaseRowsResponse,
  WorkspaceDatabaseSummary,
  WorkspacePageDetail,
  WorkspacePageSummary,
  WorkspaceProperty,
  WorkspacePropertyValue,
  WorkspaceRow,
  WorkspaceSearchResponse,
  WorkspaceTemplate,
  WorkspaceView
} from '../../services/workspaceApi';

const now = '2026-03-08T14:00:00Z';
const READ_ONLY_ERROR = 'Projects workspace is read-only in guest mode.';

const pages: WorkspacePageSummary[] = [
  {
    id: 1000,
    parent_page_id: null,
    title: 'Home',
    kind: 'home',
    icon: '🏠',
    cover_url: null,
    description: 'Workspace landing page',
    show_in_sidebar: true,
    sort_order: 0,
    is_home: true,
    trashed_at: null,
    legacy_project_id: null,
    legacy_todo_id: null,
    legacy_note_id: null,
    created_at: now,
    updated_at: now
  },
  {
    id: 1001,
    parent_page_id: null,
    title: 'Projects',
    kind: 'database',
    icon: '📁',
    cover_url: null,
    description: 'Project pages and rollups',
    show_in_sidebar: true,
    sort_order: 10,
    is_home: false,
    trashed_at: null,
    legacy_project_id: null,
    legacy_todo_id: null,
    legacy_note_id: null,
    created_at: now,
    updated_at: now
  },
  {
    id: 1002,
    parent_page_id: null,
    title: 'Tasks',
    kind: 'database',
    icon: '✅',
    cover_url: null,
    description: 'Task database with dates and triage',
    show_in_sidebar: true,
    sort_order: 20,
    is_home: false,
    trashed_at: null,
    legacy_project_id: null,
    legacy_todo_id: null,
    legacy_note_id: null,
    created_at: now,
    updated_at: now
  },
  {
    id: 1101,
    parent_page_id: 1001,
    title: 'Inbox',
    kind: 'database_row',
    icon: '📥',
    cover_url: null,
    description: 'Default landing place for uncategorized work.',
    show_in_sidebar: true,
    sort_order: -100,
    is_home: false,
    trashed_at: null,
    legacy_project_id: 1,
    legacy_todo_id: null,
    legacy_note_id: null,
    created_at: now,
    updated_at: now
  },
  {
    id: 1102,
    parent_page_id: 1001,
    title: 'Health',
    kind: 'database_row',
    icon: '🏃',
    cover_url: null,
    description: 'Training, recovery, and medical admin all live here.',
    show_in_sidebar: true,
    sort_order: 1,
    is_home: false,
    trashed_at: null,
    legacy_project_id: 2,
    legacy_todo_id: null,
    legacy_note_id: null,
    created_at: now,
    updated_at: now
  },
  {
    id: 1103,
    parent_page_id: 1001,
    title: 'Finance',
    kind: 'database_row',
    icon: '💸',
    cover_url: null,
    description: 'Budgeting, reimbursements, and money admin.',
    show_in_sidebar: true,
    sort_order: 2,
    is_home: false,
    trashed_at: null,
    legacy_project_id: 3,
    legacy_todo_id: null,
    legacy_note_id: null,
    created_at: now,
    updated_at: now
  },
  {
    id: 1104,
    parent_page_id: 1001,
    title: 'Capital One Onboarding',
    kind: 'database_row',
    icon: '🏦',
    cover_url: null,
    description: 'This project tracks the onboarding launch surface.',
    show_in_sidebar: true,
    sort_order: 3,
    is_home: false,
    trashed_at: null,
    legacy_project_id: 4,
    legacy_todo_id: null,
    legacy_note_id: null,
    created_at: now,
    updated_at: now
  },
  {
    id: 1201,
    parent_page_id: 1002,
    title: 'Record Loom walkthrough',
    kind: 'database_row',
    icon: '✅',
    cover_url: null,
    description: null,
    show_in_sidebar: false,
    sort_order: 1,
    is_home: false,
    trashed_at: null,
    legacy_project_id: null,
    legacy_todo_id: 106,
    legacy_note_id: null,
    created_at: now,
    updated_at: now
  },
  {
    id: 1202,
    parent_page_id: 1002,
    title: 'Call insurance',
    kind: 'database_row',
    icon: '✅',
    cover_url: null,
    description: null,
    show_in_sidebar: false,
    sort_order: 2,
    is_home: false,
    trashed_at: null,
    legacy_project_id: null,
    legacy_todo_id: 109,
    legacy_note_id: null,
    created_at: now,
    updated_at: now
  },
  {
    id: 1203,
    parent_page_id: 1002,
    title: 'Submit expense reimbursement',
    kind: 'database_row',
    icon: '✅',
    cover_url: null,
    description: null,
    show_in_sidebar: false,
    sort_order: 3,
    is_home: false,
    trashed_at: null,
    legacy_project_id: null,
    legacy_todo_id: 108,
    legacy_note_id: null,
    created_at: now,
    updated_at: now
  },
  {
    id: 1204,
    parent_page_id: 1002,
    title: 'Set up homepage like Notion',
    kind: 'database_row',
    icon: '✅',
    cover_url: null,
    description: null,
    show_in_sidebar: false,
    sort_order: 4,
    is_home: false,
    trashed_at: null,
    legacy_project_id: null,
    legacy_todo_id: 150,
    legacy_note_id: null,
    created_at: now,
    updated_at: now
  },
  {
    id: 1301,
    parent_page_id: 1102,
    title: 'Health operating notes',
    kind: 'note',
    icon: '📝',
    cover_url: null,
    description: 'Primary outcomes: consistent training, one-click scheduling for appointments, and low-friction meal prep.',
    show_in_sidebar: true,
    sort_order: 1,
    is_home: false,
    trashed_at: null,
    legacy_project_id: null,
    legacy_todo_id: null,
    legacy_note_id: 1,
    created_at: now,
    updated_at: now
  },
  {
    id: 1302,
    parent_page_id: 1104,
    title: 'Capital One launch brief',
    kind: 'note',
    icon: '🗒️',
    cover_url: null,
    description: 'Ship the new workspace shell, demo a Notion-like home, and unblock future page/database expansion.',
    show_in_sidebar: true,
    sort_order: 2,
    is_home: false,
    trashed_at: null,
    legacy_project_id: null,
    legacy_todo_id: null,
    legacy_note_id: 2,
    created_at: now,
    updated_at: now
  }
];

const pageById = new Map(pages.map((page) => [page.id, page]));

const projectsProperties: WorkspaceProperty[] = [
  {
    id: 20001,
    name: 'Name',
    slug: 'title',
    property_type: 'title',
    sort_order: 0,
    required: true,
    config_json: {},
    options: []
  },
  {
    id: 20002,
    name: 'Status',
    slug: 'status',
    property_type: 'select',
    sort_order: 1,
    required: false,
    config_json: {},
    options: [
      { id: 1, label: 'Active', value: 'active', color: 'green', sort_order: 0 },
      { id: 2, label: 'Archived', value: 'archived', color: 'gray', sort_order: 1 }
    ]
  },
  {
    id: 20004,
    name: 'Open Tasks',
    slug: 'open_tasks',
    property_type: 'rollup',
    sort_order: 2,
    required: false,
    config_json: {},
    options: []
  },
  {
    id: 20005,
    name: 'Done Tasks',
    slug: 'done_tasks',
    property_type: 'rollup',
    sort_order: 3,
    required: false,
    config_json: {},
    options: []
  }
];

const taskProperties: WorkspaceProperty[] = [
  { id: 21001, name: 'Task', slug: 'title', property_type: 'title', sort_order: 0, required: true, config_json: {}, options: [] },
  { id: 21002, name: 'Project', slug: 'project', property_type: 'relation', sort_order: 1, required: false, config_json: { target_database_key: 'projects' }, options: [] },
  { id: 21003, name: 'Status', slug: 'status', property_type: 'select', sort_order: 2, required: false, config_json: {}, options: [{ id: 3, label: 'Todo', value: 'todo', color: 'default', sort_order: 0 }, { id: 4, label: 'In Progress', value: 'in-progress', color: 'blue', sort_order: 1 }, { id: 5, label: 'Done', value: 'done', color: 'green', sort_order: 2 }] },
  { id: 21004, name: 'Due', slug: 'due', property_type: 'date', sort_order: 3, required: false, config_json: {}, options: [] },
  { id: 21005, name: 'Date Only', slug: 'date_only', property_type: 'checkbox', sort_order: 4, required: false, config_json: {}, options: [] },
  { id: 21006, name: 'Triage', slug: 'triage_state', property_type: 'select', sort_order: 5, required: false, config_json: {}, options: [{ id: 6, label: 'Assigned', value: 'assigned', color: 'green', sort_order: 0 }, { id: 7, label: 'Suggested', value: 'suggested', color: 'yellow', sort_order: 1 }, { id: 8, label: 'Unassigned', value: 'unassigned', color: 'gray', sort_order: 2 }, { id: 9, label: 'Done', value: 'done', color: 'blue', sort_order: 3 }] },
  { id: 21007, name: 'Suggested Project', slug: 'suggested_project', property_type: 'text', sort_order: 6, required: false, config_json: {}, options: [] },
  { id: 21008, name: 'Accomplishment', slug: 'accomplishment', property_type: 'text', sort_order: 7, required: false, config_json: {}, options: [] }
];

const databases: WorkspaceDatabaseSummary[] = [
  {
    id: 3001,
    page_id: 1001,
    name: 'Projects',
    description: 'Project pages and rollups',
    icon: '📁',
    is_seeded: true,
    properties: projectsProperties,
    views: [
      { id: 4001, name: 'All Projects', view_type: 'table', sort_order: 0, is_default: true, config_json: { sort: [{ property: 'title', direction: 'asc' }], open_mode: 'side_peek' } },
      { id: 4002, name: 'By Status', view_type: 'board', sort_order: 1, is_default: false, config_json: { group_by: 'status', open_mode: 'side_peek' } },
      { id: 4003, name: 'Gallery', view_type: 'gallery', sort_order: 2, is_default: false, config_json: { card_preview: 'icon', open_mode: 'center_peek' } }
    ]
  },
  {
    id: 3002,
    page_id: 1002,
    name: 'Tasks',
    description: 'Task database with dates and triage',
    icon: '✅',
    is_seeded: true,
    properties: taskProperties,
    views: [
      { id: 4101, name: 'All Tasks', view_type: 'table', sort_order: 0, is_default: true, config_json: { sort: [{ property: 'due', direction: 'asc' }], open_mode: 'side_peek' } },
      { id: 4102, name: 'Board', view_type: 'board', sort_order: 1, is_default: false, config_json: { group_by: 'status', open_mode: 'side_peek' } },
      { id: 4103, name: 'Calendar', view_type: 'calendar', sort_order: 2, is_default: false, config_json: { date_property: 'due', open_mode: 'full_page' } },
      { id: 4104, name: 'Timeline', view_type: 'timeline', sort_order: 3, is_default: false, config_json: { date_property: 'due', open_mode: 'full_page' } },
      { id: 4105, name: 'Triage', view_type: 'list', sort_order: 4, is_default: false, config_json: { filters: [{ property: 'triage_state', operator: 'in', value: ['suggested', 'unassigned'] }], open_mode: 'side_peek' } }
    ]
  }
];

const databaseById = new Map(databases.map((database) => [database.id, database]));
const databaseByPageId = new Map(databases.map((database) => [database.page_id, database]));

const rowProperties = new Map<number, WorkspacePropertyValue[]>();
rowProperties.set(1101, [
  { property_id: 20001, property_slug: 'title', property_name: 'Name', property_type: 'title', value: 'Inbox' },
  { property_id: 20002, property_slug: 'status', property_name: 'Status', property_type: 'select', value: 'active' },
  { property_id: 20004, property_slug: 'open_tasks', property_name: 'Open Tasks', property_type: 'rollup', value: 0 },
  { property_id: 20005, property_slug: 'done_tasks', property_name: 'Done Tasks', property_type: 'rollup', value: 0 }
]);
rowProperties.set(1102, [
  { property_id: 20001, property_slug: 'title', property_name: 'Name', property_type: 'title', value: 'Health' },
  { property_id: 20002, property_slug: 'status', property_name: 'Status', property_type: 'select', value: 'active' },
  { property_id: 20004, property_slug: 'open_tasks', property_name: 'Open Tasks', property_type: 'rollup', value: 1 },
  { property_id: 20005, property_slug: 'done_tasks', property_name: 'Done Tasks', property_type: 'rollup', value: 1 }
]);
rowProperties.set(1103, [
  { property_id: 20001, property_slug: 'title', property_name: 'Name', property_type: 'title', value: 'Finance' },
  { property_id: 20002, property_slug: 'status', property_name: 'Status', property_type: 'select', value: 'active' },
  { property_id: 20004, property_slug: 'open_tasks', property_name: 'Open Tasks', property_type: 'rollup', value: 1 },
  { property_id: 20005, property_slug: 'done_tasks', property_name: 'Done Tasks', property_type: 'rollup', value: 0 }
]);
rowProperties.set(1104, [
  { property_id: 20001, property_slug: 'title', property_name: 'Name', property_type: 'title', value: 'Capital One Onboarding' },
  { property_id: 20002, property_slug: 'status', property_name: 'Status', property_type: 'select', value: 'active' },
  { property_id: 20004, property_slug: 'open_tasks', property_name: 'Open Tasks', property_type: 'rollup', value: 2 },
  { property_id: 20005, property_slug: 'done_tasks', property_name: 'Done Tasks', property_type: 'rollup', value: 0 }
]);
rowProperties.set(1201, [
  { property_id: 21001, property_slug: 'title', property_name: 'Task', property_type: 'title', value: 'Record Loom walkthrough' },
  { property_id: 21002, property_slug: 'project', property_name: 'Project', property_type: 'relation', value: 1104 },
  { property_id: 21003, property_slug: 'status', property_name: 'Status', property_type: 'select', value: 'todo' },
  { property_id: 21004, property_slug: 'due', property_name: 'Due', property_type: 'date', value: '2026-03-08T19:00:00Z' },
  { property_id: 21005, property_slug: 'date_only', property_name: 'Date Only', property_type: 'checkbox', value: false },
  { property_id: 21006, property_slug: 'triage_state', property_name: 'Triage', property_type: 'select', value: 'assigned' },
  { property_id: 21007, property_slug: 'suggested_project', property_name: 'Suggested Project', property_type: 'text', value: '' },
  { property_id: 21008, property_slug: 'accomplishment', property_name: 'Accomplishment', property_type: 'text', value: '' }
]);
rowProperties.set(1202, [
  { property_id: 21001, property_slug: 'title', property_name: 'Task', property_type: 'title', value: 'Call insurance' },
  { property_id: 21002, property_slug: 'project', property_name: 'Project', property_type: 'relation', value: 1102 },
  { property_id: 21003, property_slug: 'status', property_name: 'Status', property_type: 'select', value: 'todo' },
  { property_id: 21004, property_slug: 'due', property_name: 'Due', property_type: 'date', value: '2026-03-08T09:30:00Z' },
  { property_id: 21005, property_slug: 'date_only', property_name: 'Date Only', property_type: 'checkbox', value: false },
  { property_id: 21006, property_slug: 'triage_state', property_name: 'Triage', property_type: 'select', value: 'assigned' },
  { property_id: 21007, property_slug: 'suggested_project', property_name: 'Suggested Project', property_type: 'text', value: '' },
  { property_id: 21008, property_slug: 'accomplishment', property_name: 'Accomplishment', property_type: 'text', value: '' }
]);
rowProperties.set(1203, [
  { property_id: 21001, property_slug: 'title', property_name: 'Task', property_type: 'title', value: 'Submit expense reimbursement' },
  { property_id: 21002, property_slug: 'project', property_name: 'Project', property_type: 'relation', value: 1103 },
  { property_id: 21003, property_slug: 'status', property_name: 'Status', property_type: 'select', value: 'todo' },
  { property_id: 21004, property_slug: 'due', property_name: 'Due', property_type: 'date', value: '2026-03-06T17:00:00Z' },
  { property_id: 21005, property_slug: 'date_only', property_name: 'Date Only', property_type: 'checkbox', value: false },
  { property_id: 21006, property_slug: 'triage_state', property_name: 'Triage', property_type: 'select', value: 'assigned' },
  { property_id: 21007, property_slug: 'suggested_project', property_name: 'Suggested Project', property_type: 'text', value: '' },
  { property_id: 21008, property_slug: 'accomplishment', property_name: 'Accomplishment', property_type: 'text', value: '' }
]);
rowProperties.set(1204, [
  { property_id: 21001, property_slug: 'title', property_name: 'Task', property_type: 'title', value: 'Set up homepage like Notion' },
  { property_id: 21002, property_slug: 'project', property_name: 'Project', property_type: 'relation', value: 1104 },
  { property_id: 21003, property_slug: 'status', property_name: 'Status', property_type: 'select', value: 'in-progress' },
  { property_id: 21004, property_slug: 'due', property_name: 'Due', property_type: 'date', value: '2026-03-10T14:00:00Z' },
  { property_id: 21005, property_slug: 'date_only', property_name: 'Date Only', property_type: 'checkbox', value: false },
  { property_id: 21006, property_slug: 'triage_state', property_name: 'Triage', property_type: 'select', value: 'suggested' },
  { property_id: 21007, property_slug: 'suggested_project', property_name: 'Suggested Project', property_type: 'text', value: 'Product' },
  { property_id: 21008, property_slug: 'accomplishment', property_name: 'Accomplishment', property_type: 'text', value: '' }
]);

const blocksByPageId = new Map<number, WorkspaceBlock[]>([
  [
    1000,
    [
      { id: 5001, page_id: 1000, parent_block_id: null, block_type: 'callout', sort_order: 0, text_content: 'Guest workspace is browse-only. Sign in to edit pages, create notes, and save views.', checked: false, data_json: null, links: [] },
      { id: 5002, page_id: 1000, parent_block_id: null, block_type: 'heading_1', sort_order: 1, text_content: 'Quick access', checked: false, data_json: null, links: [] },
      { id: 5003, page_id: 1000, parent_block_id: null, block_type: 'favorites', sort_order: 2, text_content: '', checked: false, data_json: null, links: [] },
      { id: 5004, page_id: 1000, parent_block_id: null, block_type: 'recent_pages', sort_order: 3, text_content: '', checked: false, data_json: null, links: [] },
      { id: 5005, page_id: 1000, parent_block_id: null, block_type: 'linked_database', sort_order: 4, text_content: 'Projects', checked: false, data_json: { database_id: 3001, view_id: 4001 }, links: [] },
      { id: 5006, page_id: 1000, parent_block_id: null, block_type: 'linked_database', sort_order: 5, text_content: 'Task triage', checked: false, data_json: { database_id: 3002, view_id: 4105 }, links: [] }
    ]
  ],
  [
    1101,
    [
      { id: 5100, page_id: 1101, parent_block_id: null, block_type: 'paragraph', sort_order: 0, text_content: 'Default landing place for uncategorized work.', checked: false, data_json: null, links: [] }
    ]
  ],
  [
    1102,
    [
      { id: 5102, page_id: 1102, parent_block_id: null, block_type: 'paragraph', sort_order: 0, text_content: 'Training, recovery, and medical admin all live here. See [[Health operating notes]] for the current baseline.', checked: false, data_json: null, links: [{ id: 1301, title: 'Health operating notes', kind: 'note', icon: '📝' }] }
    ]
  ],
  [
    1103,
    [
      { id: 5104, page_id: 1103, parent_block_id: null, block_type: 'paragraph', sort_order: 0, text_content: 'Budgeting, reimbursements, and money admin.', checked: false, data_json: null, links: [] }
    ]
  ],
  [
    1104,
    [
      { id: 5106, page_id: 1104, parent_block_id: null, block_type: 'paragraph', sort_order: 0, text_content: 'This project tracks the onboarding launch surface. Start with [[Capital One launch brief]] and use the task section below to prioritize launch work.', checked: false, data_json: null, links: [{ id: 1302, title: 'Capital One launch brief', kind: 'note', icon: '🗒️' }] }
    ]
  ],
  [
    1204,
    [
      { id: 5201, page_id: 1204, parent_block_id: null, block_type: 'todo_item', sort_order: 0, text_content: 'Mirror Notion homepage information architecture', checked: true, data_json: null, links: [] },
      { id: 5202, page_id: 1204, parent_block_id: null, block_type: 'paragraph', sort_order: 1, text_content: 'The end state should feel like Notion home: sidebar, recents, favorites, searchable pages, and linked databases.', checked: false, data_json: null, links: [] }
    ]
  ],
  [
    1301,
    [
      { id: 5301, page_id: 1301, parent_block_id: null, block_type: 'paragraph', sort_order: 0, text_content: 'Primary outcomes: consistent training, one-click scheduling for appointments, and low-friction meal prep.', checked: false, data_json: null, links: [] }
    ]
  ],
  [
    1302,
    [
      { id: 5302, page_id: 1302, parent_block_id: null, block_type: 'paragraph', sort_order: 0, text_content: 'Ship the new workspace shell, demo a Notion-like home, and unblock future page/database expansion.', checked: false, data_json: null, links: [] }
    ]
  ]
]);

const templates: WorkspaceTemplate[] = [
  { id: 6001, database_id: 3001, name: 'Project kickoff', title: 'New Project', icon: '🚀', cover_url: null, sort_order: 0 }
];

const favorites = [pageById.get(1000), pageById.get(1104)].filter(Boolean) as WorkspacePageSummary[];
const recents = [pageById.get(1204), pageById.get(1104), pageById.get(1302)].filter(Boolean) as WorkspacePageSummary[];

const getBlocks = (pageId: number) =>
  blocksByPageId.get(pageId) ?? [{
    id: pageId * 10,
    page_id: pageId,
    parent_block_id: null,
    block_type: 'paragraph',
    sort_order: 0,
    text_content: '',
    checked: false,
    data_json: null,
    links: []
  }];

const getBacklinks = (pageId: number) =>
  [...blocksByPageId.values()].flatMap((blocks) =>
    blocks
      .filter((block) => block.links.some((link) => link.id === pageId))
      .map((block) => {
        const source = pageById.get(block.page_id)!;
        return {
          source_page: { id: source.id, title: source.title, kind: source.kind, icon: source.icon },
          block_id: block.id,
          snippet: block.text_content || null
        };
      })
  );

const getBreadcrumbs = (page: WorkspacePageSummary) => {
  const items: WorkspacePageSummary[] = [];
  let current = page.parent_page_id;
  while (current) {
    const parent = pageById.get(current);
    if (!parent) break;
    items.unshift(parent);
    current = parent.parent_page_id;
  }
  return items;
};

const getChildren = (pageId: number) =>
  pages.filter((page) => page.parent_page_id === pageId && !page.trashed_at);

const mapRowToDatabase = (page: WorkspacePageSummary): WorkspaceDatabaseSummary | null =>
  page.parent_page_id ? databaseByPageId.get(page.parent_page_id) ?? null : null;

const applyViewFilters = (rows: WorkspaceRow[], view: WorkspaceView | null) => {
  const filters = Array.isArray(view?.config_json) ? [] : ((view?.config_json as Record<string, unknown> | null)?.filters as Record<string, unknown>[] | undefined);
  if (!filters?.length) return rows;
  return rows.filter((row) =>
    filters.every((filter) => {
      const property = row.properties.find((item) => item.property_slug === filter.property);
      if (!property) return true;
      if (filter.operator === 'in' && Array.isArray(filter.value)) {
        return (filter.value as unknown[]).includes(property.value);
      }
      return true;
    })
  );
};

const applyRelationFilter = (
  rows: WorkspaceRow[],
  relationPropertySlug?: string,
  relationPageId?: number
) => {
  if (!relationPropertySlug || relationPageId === undefined) return rows;
  return rows.filter((row) => row.properties.find((item) => item.property_slug === relationPropertySlug)?.value === relationPageId);
};

const sortRows = (rows: WorkspaceRow[], view: WorkspaceView | null) => {
  const firstSort = Array.isArray(view?.config_json)
    ? null
    : ((view?.config_json as Record<string, unknown> | null)?.sort as Record<string, unknown>[] | undefined)?.[0];
  if (!firstSort) return rows;
  const propertySlug = String(firstSort.property ?? 'title');
  const direction = firstSort.direction === 'desc' ? -1 : 1;
  return [...rows].sort((left, right) => {
    const leftValue =
      propertySlug === 'title'
        ? left.page.title
        : left.properties.find((item) => item.property_slug === propertySlug)?.value;
    const rightValue =
      propertySlug === 'title'
        ? right.page.title
        : right.properties.find((item) => item.property_slug === propertySlug)?.value;
    return String(leftValue ?? '').localeCompare(String(rightValue ?? '')) * direction;
  });
};

const buildRows = (databaseId: number): WorkspaceRow[] => {
  const database = databaseById.get(databaseId);
  if (!database) return [];
  return pages
    .filter((page) => page.parent_page_id === database.page_id)
    .map((page) => ({
      page,
      properties: rowProperties.get(page.id) ?? []
    }));
};

export const getGuestWorkspaceBootstrap = async (): Promise<WorkspaceBootstrap> => ({
  home_page_id: 1000,
  read_only: true,
  sidebar_pages: pages.filter((page) => page.show_in_sidebar && !page.trashed_at),
  favorites,
  recent_pages: recents,
  trash_pages: [],
  databases
});

export const getGuestWorkspacePage = async (pageId: number): Promise<WorkspacePageDetail> => {
  const page = pageById.get(pageId);
  if (!page) throw new Error('Workspace page not found');
  const database = databaseByPageId.get(page.id) ?? null;
  const linkedDatabases =
    getBlocks(page.id)
      .map((block) => databaseById.get(Number((block.data_json as Record<string, unknown> | null)?.database_id ?? -1)) ?? null)
      .filter(Boolean) as WorkspaceDatabaseSummary[];
  return {
    page,
    breadcrumbs: getBreadcrumbs(page),
    children: getChildren(page.id),
    properties: rowProperties.get(page.id) ?? [],
    blocks: getBlocks(page.id),
    database,
    linked_databases: linkedDatabases,
    favorite: favorites.some((item) => item.id === page.id)
  };
};

export const getGuestWorkspaceBacklinks = async (pageId: number): Promise<WorkspaceBacklinksResponse> => ({
  backlinks: getBacklinks(pageId)
});

export const markGuestWorkspaceRecent = async (_pageId: number): Promise<void> => Promise.resolve();

export const getGuestWorkspaceDatabaseRows = async (
  databaseId: number,
  viewId?: number,
  offset = 0,
  limit = 50,
  relationPropertySlug?: string,
  relationPageId?: number
): Promise<WorkspaceDatabaseRowsResponse> => {
  const database = databaseById.get(databaseId);
  if (!database) throw new Error('Workspace database not found');
  const view = database.views.find((item) => item.id === viewId) ?? database.views.find((item) => item.is_default) ?? null;
  const rows = sortRows(
    applyRelationFilter(applyViewFilters(buildRows(databaseId), view), relationPropertySlug, relationPageId),
    view
  );
  const pagedRows = rows.slice(offset, offset + limit);
  return {
    database,
    view,
    rows: pagedRows,
    total_count: rows.length,
    offset,
    limit,
    has_more: offset + pagedRows.length < rows.length
  };
};

export const searchGuestWorkspace = async (query: string): Promise<WorkspaceSearchResponse> => {
  const term = query.trim().toLowerCase();
  if (!term) return { results: [] };
  const results = pages
    .filter((page) => page.title.toLowerCase().includes(term))
    .slice(0, 10)
    .map((page) => ({ page, match: page.title }));
  if (results.length < 10) {
    for (const [pageId, blocks] of blocksByPageId.entries()) {
      if (results.some((item) => item.page.id === pageId)) continue;
      const match = blocks.find((block) => block.text_content.toLowerCase().includes(term));
      if (!match) continue;
      const page = pageById.get(pageId);
      if (!page) continue;
      results.push({ page, match: match.text_content });
      if (results.length >= 10) break;
    }
  }
  return { results };
};

export const listGuestWorkspaceTemplates = async (databaseId?: number): Promise<WorkspaceTemplate[]> =>
  templates.filter((template) => (databaseId ? template.database_id === databaseId : true));

const rejectReadOnly = () => Promise.reject(new Error(READ_ONLY_ERROR));

export const createGuestWorkspacePage = async (_payload: unknown): Promise<WorkspacePageDetail> => rejectReadOnly();
export const updateGuestWorkspacePage = async (_pageId: number, _payload: unknown): Promise<WorkspacePageDetail> => rejectReadOnly();
export const deleteGuestWorkspacePage = async (_pageId: number): Promise<void> => rejectReadOnly();
export const createGuestWorkspaceBlock = async (_payload: unknown): Promise<WorkspacePageDetail> => rejectReadOnly();
export const updateGuestWorkspaceBlock = async (_blockId: number, _payload: unknown): Promise<WorkspacePageDetail> => rejectReadOnly();
export const deleteGuestWorkspaceBlock = async (_blockId: number): Promise<void> => rejectReadOnly();
export const reorderGuestWorkspaceBlocks = async (_payload: unknown): Promise<void> => rejectReadOnly();
export const createGuestWorkspaceRow = async (_databaseId: number, _payload: unknown): Promise<WorkspacePageDetail> => rejectReadOnly();
export const updateGuestWorkspacePageProperties = async (_pageId: number, _values: unknown): Promise<WorkspacePageDetail> => rejectReadOnly();
export const createGuestWorkspaceView = async (_databaseId: number, _payload: unknown): Promise<WorkspaceDatabaseRowsResponse> => rejectReadOnly();
export const updateGuestWorkspaceView = async (_viewId: number, _payload: unknown): Promise<WorkspaceView> => rejectReadOnly();
export const applyGuestWorkspaceTemplate = async (_templateId: number, _payload: unknown): Promise<WorkspacePageDetail> => rejectReadOnly();
export const createGuestWorkspaceAssetUpload = async (_payload: unknown): Promise<WorkspaceAssetUpload> => rejectReadOnly();
