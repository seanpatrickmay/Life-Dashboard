// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/react';
import { ThemeProvider } from 'styled-components';
import { describe, expect, it } from 'vitest';

import type { ProjectNote } from '../../services/api';
import { ProjectNotesSection, sortProjectNotes } from './ProjectNotesSection';

const theme = {
  fonts: { heading: 'sans-serif' },
  colors: { textPrimary: '#fff' }
};

const buildNote = (override: Partial<ProjectNote>): ProjectNote => ({
  id: 1,
  user_id: 1,
  project_id: 1,
  title: 'Note',
  body_markdown: 'Body',
  tags: [],
  archived: false,
  pinned: false,
  created_at: '2026-01-01T12:00:00Z',
  updated_at: '2026-01-01T12:00:00Z',
  ...override
});

describe('sortProjectNotes', () => {
  it('orders pinned first, then Description, then updated_at desc', () => {
    const notes = [
      buildNote({ id: 1, title: 'General', pinned: false, updated_at: '2026-01-01T12:00:00Z' }),
      buildNote({ id: 2, title: 'Description', pinned: false, updated_at: '2026-01-01T11:00:00Z' }),
      buildNote({ id: 3, title: 'Pinned old', pinned: true, updated_at: '2026-01-01T09:00:00Z' }),
      buildNote({ id: 4, title: 'Pinned new', pinned: true, updated_at: '2026-01-02T09:00:00Z' })
    ];

    const sorted = sortProjectNotes(notes);

    expect(sorted.map((note) => note.id)).toEqual([4, 3, 2, 1]);
  });
});

describe('ProjectNotesSection', () => {
  it('renders empty state', () => {
    render(
      <ThemeProvider theme={theme}>
        <ProjectNotesSection notes={[]} isLoading={false} isError={false} />
      </ThemeProvider>
    );

    expect(screen.getByText('No notes yet')).toBeInTheDocument();
  });

  it('renders note metadata and markdown text', () => {
    render(
      <ThemeProvider theme={theme}>
        <ProjectNotesSection
          notes={[
            buildNote({
              id: 9,
              title: 'Description',
              body_markdown: '**Hello** world',
              tags: ['project', 'context'],
              pinned: true,
              updated_at: '2026-01-03T12:00:00Z'
            })
          ]}
          isLoading={false}
          isError={false}
        />
      </ThemeProvider>
    );

    expect(screen.getByText('Description')).toBeInTheDocument();
    expect(screen.getByText('Hello')).toBeInTheDocument();
    expect(screen.getByText('world')).toBeInTheDocument();
    expect(screen.getByText('Pinned')).toBeInTheDocument();
    expect(screen.getByText('project')).toBeInTheDocument();
    expect(screen.getByText('context')).toBeInTheDocument();
  });
});
