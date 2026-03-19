import { useMemo } from 'react';
import styled from 'styled-components';
import ReactMarkdown from 'react-markdown';

import type { ProjectNote } from '../../services/api';

const NotesWrap = styled.div`
  display: grid;
  gap: 8px;
`;

const NotesHeader = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
`;

const NotesTitle = styled.div`
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.8rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
`;

const NoteCard = styled.div`
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  border-radius: 12px;
  padding: 9px 10px;
  display: grid;
  gap: 6px;
  min-width: 0;
`;

const NoteTopRow = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
`;

const NoteTitle = styled.div`
  font-weight: 600;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
`;

const Badge = styled.span`
  border: 1px solid ${({ theme }) => theme.colors.accentSubtle};
  background: ${({ theme }) => theme.colors.accentSubtle};
  border-radius: 999px;
  padding: 2px 8px;
  font-size: 0.7rem;
  white-space: nowrap;
`;

const Meta = styled.div`
  opacity: 0.72;
  font-size: 0.78rem;
`;

const TagRow = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
`;

const Tag = styled.span`
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  border-radius: 999px;
  padding: 2px 8px;
  font-size: 0.72rem;
  opacity: 0.9;
`;

const MarkdownBody = styled.div`
  font-size: 0.88rem;
  line-height: 1.4;
  overflow-wrap: anywhere;
`;

const Muted = styled.div`
  opacity: 0.75;
  font-size: 0.85rem;
`;

const toTimeText = (iso: string) => {
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) return '';
  return parsed.toLocaleString();
};

export const sortProjectNotes = (notes: ProjectNote[]): ProjectNote[] =>
  [...notes].sort((left, right) => {
    if (left.pinned !== right.pinned) return left.pinned ? -1 : 1;

    const leftDescription = left.title.trim().toLowerCase() === 'description';
    const rightDescription = right.title.trim().toLowerCase() === 'description';
    if (leftDescription !== rightDescription) return leftDescription ? -1 : 1;

    const leftUpdated = new Date(left.updated_at).getTime();
    const rightUpdated = new Date(right.updated_at).getTime();
    return rightUpdated - leftUpdated;
  });

type Props = {
  notes: ProjectNote[];
  isLoading: boolean;
  isError: boolean;
};

export function ProjectNotesSection({ notes, isLoading, isError }: Props) {
  const ordered = useMemo(() => sortProjectNotes(notes), [notes]);

  return (
    <NotesWrap>
      <NotesHeader>
        <NotesTitle data-halo="heading">Notes</NotesTitle>
        <Muted>{ordered.length} total</Muted>
      </NotesHeader>
      {isLoading ? <Muted>Loading notes...</Muted> : null}
      {isError ? <Muted>Could not load notes.</Muted> : null}
      {!isLoading && !isError && ordered.length === 0 ? <Muted>No notes yet</Muted> : null}
      {!isLoading && !isError
        ? ordered.map((note) => (
            <NoteCard key={note.id}>
              <NoteTopRow>
                <NoteTitle title={note.title}>{note.title}</NoteTitle>
                {note.pinned ? <Badge>Pinned</Badge> : null}
              </NoteTopRow>
              <MarkdownBody>
                <ReactMarkdown>{note.body_markdown || ''}</ReactMarkdown>
              </MarkdownBody>
              {note.tags.length ? (
                <TagRow>
                  {note.tags.map((tag) => (
                    <Tag key={`${note.id}-${tag}`}>{tag}</Tag>
                  ))}
                </TagRow>
              ) : null}
              <Meta>Updated {toTimeText(note.updated_at)}</Meta>
            </NoteCard>
          ))
        : null}
    </NotesWrap>
  );
}

