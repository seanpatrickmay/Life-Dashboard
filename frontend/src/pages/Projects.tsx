import { DragEvent, KeyboardEvent, useDeferredValue, useEffect, useMemo, useState } from 'react';
import { useMatch, useNavigate, useSearchParams } from 'react-router-dom';
import styled from 'styled-components';

import {
  useWorkspaceBacklinks,
  useWorkspaceBootstrap,
  useWorkspaceDatabase,
  useWorkspaceMutations,
  useWorkspacePage,
  useWorkspacePageSummary,
  useWorkspacePrefetch,
  useWorkspaceRecentTracker,
  useWorkspaceSearch,
  useWorkspaceTemplates
} from '../hooks/useWorkspace';
import type {
  WorkspaceBlock,
  WorkspaceDatabaseSummary,
  WorkspaceOpenMode,
  WorkspacePageLink,
  WorkspacePageDetail,
  WorkspacePageSummary,
  WorkspacePropertyValue,
  WorkspaceRow,
  WorkspaceTemplate,
  WorkspaceView
} from '../services/workspaceApi';
import { createWorkspaceAssetUpload, uploadWorkspaceAssetContent } from '../services/workspaceApi';

const Root = styled.div`
  --workspace-bg: #f7f6f3;
  --workspace-panel: #fbfbfa;
  --workspace-line: rgba(55, 53, 47, 0.14);
  --workspace-line-strong: rgba(55, 53, 47, 0.24);
  --workspace-text: #37352f;
  --workspace-muted: rgba(55, 53, 47, 0.64);
  --workspace-hover: rgba(55, 53, 47, 0.06);
  --workspace-selected: rgba(46, 170, 220, 0.14);
  --workspace-pill: rgba(55, 53, 47, 0.08);
  --workspace-shadow: 0 18px 42px rgba(24, 25, 23, 0.08);

  min-height: calc(100vh - 180px);
  border-radius: 28px;
  overflow: hidden;
  background:
    radial-gradient(circle at top left, rgba(249, 245, 235, 0.86), transparent 28%),
    linear-gradient(180deg, #fbfaf8 0%, #f6f4ee 100%);
  color: var(--workspace-text);
  border: 1px solid rgba(55, 53, 47, 0.08);
  box-shadow: var(--workspace-shadow);
  font-family: "Avenir Next", "Segoe UI", sans-serif;
`;

const Shell = styled.div<{ $peekOpen: boolean }>`
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr) ${({ $peekOpen }) => ($peekOpen ? '400px' : '0px')};
  min-height: calc(100vh - 180px);

  @media (max-width: 1180px) {
    grid-template-columns: 250px minmax(0, 1fr);
  }

  @media (max-width: 900px) {
    grid-template-columns: 1fr;
  }
`;

const Sidebar = styled.aside`
  background: rgba(251, 251, 250, 0.95);
  border-right: 1px solid var(--workspace-line);
  padding: 18px 14px 18px 16px;
  display: grid;
  gap: 16px;
  align-content: start;
  min-width: 0;

  @media (max-width: 900px) {
    display: none;
  }
`;

const SidebarHeader = styled.div`
  display: grid;
  gap: 8px;
`;

const WorkspaceTitle = styled.div`
  font-size: 0.82rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--workspace-muted);
`;

const SidebarActions = styled.div`
  display: flex;
  gap: 8px;
`;

const SidebarSection = styled.div`
  display: grid;
  gap: 6px;
`;

const SectionTitle = styled.div`
  font-size: 0.76rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--workspace-muted);
  padding: 0 8px;
`;

const SectionHeader = styled.button`
  border: 0;
  background: transparent;
  color: inherit;
  padding: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font: inherit;
`;

const TreeRow = styled.div<{ $depth: number }>`
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  align-items: center;
  gap: 4px;
  padding-left: ${({ $depth }) => $depth * 14}px;
`;

const TreeDisclosure = styled.button`
  border: 0;
  background: transparent;
  color: var(--workspace-muted);
  width: 18px;
  height: 18px;
  cursor: pointer;
  display: grid;
  place-items: center;
  padding: 0;
`;

const SidebarButton = styled.button<{ $active?: boolean; $indented?: boolean }>`
  border: 0;
  background: ${({ $active }) => ($active ? 'var(--workspace-selected)' : 'transparent')};
  color: var(--workspace-text);
  border-radius: 10px;
  padding: 8px 10px ${({ $indented }) => ($indented ? '8px 22px' : '8px 10px')};
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  text-align: left;
  font-size: 0.94rem;

  &:hover {
    background: ${({ $active }) => ($active ? 'var(--workspace-selected)' : 'var(--workspace-hover)')};
  }
`;

const SidebarMeta = styled.span`
  margin-left: auto;
  color: var(--workspace-muted);
  font-size: 0.8rem;
`;

const Main = styled.main`
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  min-width: 0;
  min-height: calc(100vh - 180px);
`;

const Topbar = styled.div`
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
  padding: 14px 18px;
  border-bottom: 1px solid var(--workspace-line);
  background: rgba(251, 251, 250, 0.88);
  position: sticky;
  top: 0;
  z-index: 2;

  @media (max-width: 700px) {
    grid-template-columns: 1fr;
  }
`;

const TopbarLeft = styled.div`
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
`;

const SearchInput = styled.input`
  width: min(420px, 100%);
  border: 1px solid var(--workspace-line);
  background: rgba(255, 255, 255, 0.88);
  color: var(--workspace-text);
  border-radius: 12px;
  padding: 10px 12px;
  min-width: 0;
`;

const PillButton = styled.button`
  border: 1px solid var(--workspace-line-strong);
  background: rgba(255, 255, 255, 0.84);
  color: var(--workspace-text);
  border-radius: 999px;
  padding: 8px 12px;
  cursor: pointer;
  font-size: 0.86rem;

  &:disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }
`;

const Canvas = styled.div`
  overflow: auto;
  min-width: 0;
`;

const CanvasInner = styled.div`
  width: min(980px, calc(100% - 48px));
  margin: 0 auto;
  padding: 28px 0 72px;
  display: grid;
  gap: 18px;

  @media (max-width: 700px) {
    width: calc(100% - 28px);
    padding-top: 20px;
  }
`;

const Cover = styled.div<{ $url?: string | null }>`
  min-height: 180px;
  border-radius: 22px;
  background:
    ${({ $url }) => ($url ? `linear-gradient(rgba(0,0,0,0.08), rgba(0,0,0,0.08)), url(${$url}) center/cover` : 'linear-gradient(135deg, #efe8db 0%, #ece9e1 52%, #ddd8cf 100%)')};
  border: 1px solid var(--workspace-line);
`;

const PageHeader = styled.div`
  display: grid;
  gap: 10px;
`;

const TitleRow = styled.div`
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
`;

const IconButton = styled.button`
  border: 1px solid var(--workspace-line);
  background: rgba(255, 255, 255, 0.84);
  color: var(--workspace-text);
  border-radius: 16px;
  width: 52px;
  height: 52px;
  font-size: 1.6rem;
  cursor: pointer;
`;

const PageTitleInput = styled.input`
  border: 0;
  background: transparent;
  color: var(--workspace-text);
  font-size: clamp(2rem, 4vw, 2.8rem);
  font-weight: 700;
  padding: 0;
  min-width: 0;
  width: 100%;
`;

const Breadcrumbs = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  color: var(--workspace-muted);
  font-size: 0.88rem;
`;

const CrumbButton = styled.button`
  border: 0;
  background: transparent;
  color: inherit;
  cursor: pointer;
  padding: 0;
`;

const MetaRow = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
`;

const MetaPill = styled.span`
  border-radius: 999px;
  padding: 6px 10px;
  background: var(--workspace-pill);
  color: var(--workspace-muted);
  font-size: 0.82rem;
`;

const PropertiesGrid = styled.div`
  display: grid;
  gap: 8px;
  padding: 12px 14px;
  border: 1px solid var(--workspace-line);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.58);
`;

const PropertyRow = styled.label`
  display: grid;
  grid-template-columns: 150px minmax(0, 1fr);
  gap: 12px;
  align-items: center;
  color: var(--workspace-text);
  font-size: 0.94rem;

  @media (max-width: 700px) {
    grid-template-columns: 1fr;
  }
`;

const PropertyLabel = styled.span`
  color: var(--workspace-muted);
`;

const PropertyInput = styled.input`
  border: 1px solid var(--workspace-line);
  background: rgba(255, 255, 255, 0.9);
  border-radius: 10px;
  padding: 9px 11px;
  color: var(--workspace-text);
  min-width: 0;
`;

const PropertySelect = styled.select`
  border: 1px solid var(--workspace-line);
  background: rgba(255, 255, 255, 0.9);
  border-radius: 10px;
  padding: 9px 11px;
  color: var(--workspace-text);
  min-width: 0;
`;

const RelationEditor = styled.div`
  display: grid;
  gap: 8px;
`;

const ChipRow = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
`;

const TokenChip = styled.span`
  border: 1px solid rgba(46, 170, 220, 0.22);
  background: rgba(46, 170, 220, 0.1);
  color: #205f7a;
  border-radius: 999px;
  padding: 6px 10px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
`;

const TokenRemove = styled.button`
  border: 0;
  background: transparent;
  color: inherit;
  cursor: pointer;
  padding: 0;
  font-size: 0.9rem;
`;

const Toggle = styled.input``;

const ChildPages = styled.div`
  display: grid;
  gap: 10px;
`;

const ChildGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 10px;
`;

const ChildCard = styled.button`
  border: 1px solid var(--workspace-line);
  background: rgba(255, 255, 255, 0.88);
  border-radius: 16px;
  padding: 14px;
  text-align: left;
  color: var(--workspace-text);
  cursor: pointer;
  display: grid;
  gap: 6px;
`;

const ChildDescription = styled.div`
  color: var(--workspace-muted);
  font-size: 0.88rem;
`;

const BlockList = styled.div`
  display: grid;
  gap: 4px;
`;

const BlockRow = styled.div<{ $isDragging?: boolean }>`
  position: relative;
  display: grid;
  grid-template-columns: 32px minmax(0, 1fr);
  gap: 10px;
  align-items: start;
  opacity: ${({ $isDragging }) => ($isDragging ? 0.52 : 1)};
`;

const BlockGutter = styled.div<{ $hidden?: boolean }>`
  opacity: 0;
  pointer-events: none;
  display: grid;
  gap: 6px;
  padding-top: 6px;
  transition: opacity 120ms ease;

  ${BlockRow}:hover &,
  ${BlockRow}:focus-within & {
    opacity: ${({ $hidden }) => ($hidden ? 0 : 1)};
    pointer-events: ${({ $hidden }) => ($hidden ? 'none' : 'auto')};
  }
`;

const GutterButton = styled.button<{ $dragging?: boolean }>`
  width: 24px;
  height: 24px;
  border: 1px solid var(--workspace-line);
  background: ${({ $dragging }) => ($dragging ? 'rgba(46, 170, 220, 0.12)' : 'rgba(255, 255, 255, 0.92)')};
  color: var(--workspace-muted);
  border-radius: 8px;
  cursor: ${({ $dragging }) => ($dragging ? 'grabbing' : 'pointer')};
  display: grid;
  place-items: center;
  padding: 0;
  font-size: 0.9rem;
`;

const BlockCard = styled.div`
  position: relative;
  display: grid;
  gap: 8px;
`;

const BlockMenu = styled.div`
  position: absolute;
  top: 30px;
  left: 0;
  z-index: 4;
  width: min(280px, 100%);
  max-height: min(420px, 70vh);
  border: 1px solid var(--workspace-line);
  background: rgba(255, 255, 255, 0.98);
  border-radius: 16px;
  box-shadow: 0 18px 34px rgba(20, 20, 18, 0.12);
  padding: 8px;
  display: grid;
  gap: 4px;
  overflow: auto;
`;

const BlockMenuLabel = styled.div`
  color: var(--workspace-muted);
  font-size: 0.72rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  padding: 6px 8px 2px;
`;

const BlockMenuButton = styled.button`
  border: 0;
  background: transparent;
  color: var(--workspace-text);
  text-align: left;
  padding: 8px 10px;
  border-radius: 10px;
  cursor: pointer;
  font-size: 0.9rem;

  &:hover {
    background: var(--workspace-hover);
  }
`;

const BlockDropIndicator = styled.div<{ $position: 'before' | 'after' }>`
  position: absolute;
  left: 32px;
  right: 0;
  height: 2px;
  border-radius: 999px;
  background: rgba(46, 170, 220, 0.7);
  top: ${({ $position }) => ($position === 'before' ? '-3px' : 'calc(100% + 1px)')};
`;

const BlockEditor = styled.textarea<{ $type: string }>`
  width: 100%;
  border: 0;
  resize: vertical;
  min-height: ${({ $type }) => ($type === 'heading_1' ? '54px' : '42px')};
  background: transparent;
  color: var(--workspace-text);
  font-size: ${({ $type }) =>
    $type === 'heading_1' ? '1.6rem' : $type === 'heading_2' ? '1.18rem' : '1rem'};
  font-weight: ${({ $type }) => ($type.startsWith('heading') ? 700 : 400)};
  line-height: 1.5;
  padding: 8px 0;
  font-family: ${({ $type }) => ($type === 'code' ? '"SFMono-Regular", Consolas, monospace' : 'inherit')};
`;

const TodoBlock = styled.div`
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 10px;
  align-items: start;
`;

const SlashMenu = styled.div`
  border: 1px solid var(--workspace-line);
  background: rgba(255, 255, 255, 0.97);
  border-radius: 14px;
  padding: 8px;
  display: grid;
  gap: 4px;
  box-shadow: 0 18px 34px rgba(20, 20, 18, 0.12);
`;

const SlashMenuButton = styled.button`
  border: 0;
  background: transparent;
  color: var(--workspace-text);
  text-align: left;
  padding: 8px 10px;
  border-radius: 10px;
  cursor: pointer;

  &:hover {
    background: var(--workspace-hover);
  }
`;

const SlashMenuOption = styled(SlashMenuButton)<{ $active?: boolean }>`
  background: ${({ $active }) => ($active ? 'var(--workspace-hover)' : 'transparent')};
`;

const InlineComposer = styled.div`
  border: 1px solid var(--workspace-line);
  background: rgba(255, 255, 255, 0.97);
  border-radius: 16px;
  padding: 10px;
  display: grid;
  gap: 8px;
`;

const InlineComposerInput = styled.input`
  border: 1px solid var(--workspace-line);
  background: rgba(255, 255, 255, 0.92);
  border-radius: 10px;
  padding: 9px 11px;
  color: var(--workspace-text);
`;

const LinkRow = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
`;

const LinkChip = styled.button`
  border: 1px solid rgba(46, 170, 220, 0.24);
  background: rgba(46, 170, 220, 0.1);
  color: #205f7a;
  border-radius: 999px;
  padding: 5px 10px;
  cursor: pointer;
`;

const DatabaseCard = styled.div`
  border: 1px solid var(--workspace-line);
  background: rgba(255, 255, 255, 0.78);
  border-radius: 18px;
  overflow: hidden;
`;

const DatabaseHeader = styled.div`
  padding: 12px 14px;
  border-bottom: 1px solid var(--workspace-line);
  display: grid;
  gap: 10px;
`;

const DatabaseHeaderTop = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  justify-content: space-between;
`;

const DatabaseToolbar = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
`;

const ViewTabs = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
`;

const ViewTab = styled.button<{ $active?: boolean }>`
  border: 1px solid ${({ $active }) => ($active ? 'rgba(46, 170, 220, 0.3)' : 'var(--workspace-line)')};
  background: ${({ $active }) => ($active ? 'rgba(46, 170, 220, 0.12)' : 'rgba(255, 255, 255, 0.9)')};
  color: var(--workspace-text);
  border-radius: 999px;
  padding: 7px 11px;
  cursor: pointer;
`;

const DatabaseBody = styled.div`
  padding: 8px 10px 12px;
  overflow: auto;
`;

const Table = styled.table`
  width: 100%;
  border-collapse: collapse;
  font-size: 0.92rem;

  th, td {
    padding: 10px;
    border-bottom: 1px solid var(--workspace-line);
    text-align: left;
    vertical-align: top;
  }

  th {
    color: var(--workspace-muted);
    font-weight: 500;
  }
`;

const RowButton = styled.button`
  border: 0;
  background: transparent;
  color: var(--workspace-text);
  padding: 0;
  cursor: pointer;
  text-align: left;
`;

const Board = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
`;

const BoardColumn = styled.div`
  border: 1px solid var(--workspace-line);
  background: rgba(247, 246, 243, 0.9);
  border-radius: 16px;
  padding: 10px;
  display: grid;
  gap: 8px;
`;

const BoardCard = styled.button`
  border: 1px solid var(--workspace-line);
  background: rgba(255, 255, 255, 0.96);
  border-radius: 14px;
  padding: 12px;
  text-align: left;
  color: var(--workspace-text);
  cursor: pointer;
  display: grid;
  gap: 6px;
`;

const ListView = styled.div`
  display: grid;
  gap: 8px;
`;

const ListRow = styled.button`
  border: 1px solid var(--workspace-line);
  background: rgba(255, 255, 255, 0.96);
  border-radius: 14px;
  padding: 12px 14px;
  color: var(--workspace-text);
  text-align: left;
  cursor: pointer;
  display: grid;
  gap: 4px;
`;

const GalleryGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
`;

const GalleryCard = styled.button`
  border: 1px solid var(--workspace-line);
  background: rgba(255, 255, 255, 0.96);
  border-radius: 18px;
  overflow: hidden;
  padding: 0;
  text-align: left;
  color: var(--workspace-text);
  cursor: pointer;
  display: grid;
`;

const GalleryPreview = styled.div<{ $url?: string | null }>`
  min-height: 132px;
  padding: 16px;
  display: flex;
  align-items: flex-end;
  justify-content: flex-start;
  background:
    ${({ $url }) => ($url ? `linear-gradient(rgba(0,0,0,0.06), rgba(0,0,0,0.16)), url(${$url}) center/cover` : 'linear-gradient(135deg, #efe8db 0%, #ece9e1 52%, #ddd8cf 100%)')};
`;

const GalleryBody = styled.div`
  padding: 14px;
  display: grid;
  gap: 6px;
`;

const CalendarList = styled.div`
  display: grid;
  gap: 10px;
`;

const CalendarBucket = styled.div`
  border: 1px solid var(--workspace-line);
  border-radius: 16px;
  padding: 12px;
  display: grid;
  gap: 8px;
  background: rgba(255, 255, 255, 0.9);
`;

const CalendarGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 8px;
`;

const CalendarHeaderCell = styled.div`
  color: var(--workspace-muted);
  font-size: 0.82rem;
  text-align: center;
  padding: 4px 0;
`;

const CalendarDay = styled.div<{ $muted?: boolean }>`
  min-height: 120px;
  border: 1px solid var(--workspace-line);
  border-radius: 16px;
  padding: 10px;
  background: ${({ $muted }) => ($muted ? 'rgba(247, 246, 243, 0.88)' : 'rgba(255, 255, 255, 0.94)')};
  display: grid;
  align-content: start;
  gap: 8px;
`;

const CalendarDayLabel = styled.div`
  font-size: 0.82rem;
  color: var(--workspace-muted);
`;

const MiniCard = styled.button`
  border: 1px solid var(--workspace-line);
  background: rgba(255, 255, 255, 0.96);
  border-radius: 12px;
  padding: 8px;
  text-align: left;
  color: var(--workspace-text);
  cursor: pointer;
  display: grid;
  gap: 4px;
`;

const Timeline = styled.div`
  display: grid;
  gap: 10px;
`;

const TimelineRow = styled.div`
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr);
  gap: 12px;
  align-items: center;

  @media (max-width: 900px) {
    grid-template-columns: 1fr;
  }
`;

const TimelineTrack = styled.div`
  position: relative;
  min-height: 40px;
  border-radius: 999px;
  background: rgba(55, 53, 47, 0.08);
  overflow: hidden;
`;

const TimelineBar = styled.button<{ $offset: number }>`
  position: absolute;
  top: 6px;
  left: ${({ $offset }) => `${$offset}%`};
  min-width: 120px;
  max-width: calc(100% - ${({ $offset }) => `${$offset}%`});
  border: 1px solid rgba(46, 170, 220, 0.22);
  background: rgba(46, 170, 220, 0.14);
  color: #205f7a;
  border-radius: 999px;
  padding: 8px 10px;
  text-align: left;
  cursor: pointer;
`;

const PeekPanel = styled.aside<{ $open: boolean }>`
  border-left: 1px solid var(--workspace-line);
  background: rgba(251, 251, 250, 0.98);
  overflow: auto;
  display: ${({ $open }) => ($open ? 'block' : 'none')};

  @media (max-width: 1180px) {
    display: none;
  }
`;

const PeekHeader = styled.div`
  position: sticky;
  top: 0;
  z-index: 2;
  padding: 12px 14px;
  border-bottom: 1px solid var(--workspace-line);
  background: rgba(251, 251, 250, 0.98);
  display: flex;
  justify-content: space-between;
  align-items: center;
`;

const StatusBar = styled.div<{ $kind: 'error' | 'info' }>`
  margin: 0 18px;
  padding: 12px 14px;
  border-radius: 14px;
  background: ${({ $kind }) => ($kind === 'error' ? 'rgba(228, 87, 67, 0.1)' : 'rgba(46, 170, 220, 0.12)')};
  color: ${({ $kind }) => ($kind === 'error' ? '#9f2f1f' : '#205f7a')};
  border: 1px solid ${({ $kind }) => ($kind === 'error' ? 'rgba(228, 87, 67, 0.18)' : 'rgba(46, 170, 220, 0.18)')};
`;

const Overlay = styled.div`
  position: fixed;
  inset: 0;
  background: rgba(17, 17, 15, 0.24);
  display: grid;
  place-items: start center;
  padding-top: 12vh;
  z-index: 100;
`;

const DialogCard = styled.div`
  width: min(620px, calc(100vw - 32px));
  border-radius: 22px;
  border: 1px solid var(--workspace-line);
  background: rgba(251, 251, 250, 0.98);
  box-shadow: 0 24px 54px rgba(20, 20, 18, 0.18);
  overflow: hidden;
`;

const DialogBody = styled.form`
  display: grid;
  gap: 16px;
  padding: 18px;
`;

const DialogTitle = styled.h2`
  margin: 0;
  font-size: 1.1rem;
`;

const FieldGrid = styled.div`
  display: grid;
  gap: 12px;
`;

const FieldLabel = styled.label`
  display: grid;
  gap: 6px;
  color: var(--workspace-text);
  font-size: 0.9rem;
`;

const FieldHint = styled.div`
  color: var(--workspace-muted);
  font-size: 0.82rem;
`;

const TextArea = styled.textarea`
  border: 1px solid var(--workspace-line);
  background: rgba(255, 255, 255, 0.9);
  border-radius: 12px;
  padding: 11px 12px;
  color: var(--workspace-text);
  min-width: 0;
  min-height: 88px;
  resize: vertical;
`;

const DialogActions = styled.div`
  display: flex;
  justify-content: flex-end;
  gap: 10px;
`;

const CenterPeekCard = styled.div`
  width: min(980px, calc(100vw - 48px));
  max-height: 84vh;
  border-radius: 24px;
  border: 1px solid var(--workspace-line);
  background: rgba(251, 251, 250, 0.98);
  box-shadow: 0 28px 64px rgba(20, 20, 18, 0.2);
  overflow: hidden;
`;

const Palette = styled.div`
  width: min(720px, calc(100vw - 32px));
  border-radius: 22px;
  border: 1px solid var(--workspace-line);
  background: rgba(251, 251, 250, 0.98);
  box-shadow: 0 24px 54px rgba(20, 20, 18, 0.18);
  overflow: hidden;
`;

const PaletteResults = styled.div`
  max-height: 60vh;
  overflow: auto;
  display: grid;
`;

const PaletteButton = styled.button`
  border: 0;
  border-top: 1px solid var(--workspace-line);
  background: transparent;
  color: var(--workspace-text);
  text-align: left;
  padding: 14px 16px;
  cursor: pointer;
  display: grid;
  gap: 4px;

  &:hover {
    background: var(--workspace-hover);
  }
`;

const Muted = styled.div`
  color: var(--workspace-muted);
`;

const MobileActions = styled.div`
  display: none;

  @media (max-width: 900px) {
    display: flex;
    gap: 8px;
  }
`;

const BLOCK_OPTIONS = [
  { type: 'paragraph', label: 'Text' },
  { type: 'heading_1', label: 'Heading 1' },
  { type: 'heading_2', label: 'Heading 2' },
  { type: 'bullet_list_item', label: 'Bullet list' },
  { type: 'todo_item', label: 'To-do' },
  { type: 'quote', label: 'Quote' },
  { type: 'code', label: 'Code' },
  { type: 'toggle', label: 'Toggle' },
  { type: 'callout', label: 'Callout' },
  { type: 'image', label: 'Image' },
  { type: 'file', label: 'File' },
  { type: 'bookmark', label: 'Bookmark' },
  { type: 'embed', label: 'Embed' },
  { type: 'child_page', label: 'Child page' },
  { type: 'linked_database', label: 'Linked database' },
  { type: 'divider', label: 'Divider' }
] as const;

type BlockOption = (typeof BLOCK_OPTIONS)[number];

type Status = { kind: 'error' | 'info'; message: string } | null;
type CardPreviewMode = 'cover' | 'icon' | 'none';

type PageComposerState = {
  parentPageId: number | null;
  title: string;
  kind: 'page' | 'note';
  icon: string;
  dialogTitle: string;
  submitLabel: string;
};

type RowComposerState = {
  database: WorkspaceDatabaseSummary;
  title: string;
  templateId: number | null;
  openMode: WorkspaceOpenMode;
  properties: Record<string, unknown>;
};

type ViewComposerState = {
  database: WorkspaceDatabaseSummary;
  viewId: number | null;
  name: string;
  viewType: string;
  openMode: WorkspaceOpenMode;
  groupBy: string;
  dateProperty: string;
  cardPreview: CardPreviewMode;
  isDefault: boolean;
  hiddenProperties: string[];
};

type ChromeEditorState = {
  pageId: number;
  icon: string;
  coverUrl: string;
  coverFile: File | null;
};

type InlineLinkComposerState = {
  blockId: number;
  query: string;
};

type BlockDragTarget = {
  blockId: number;
  position: 'before' | 'after';
};

function reorderBlockIds(blocks: WorkspaceBlock[], draggedBlockId: number, target: BlockDragTarget): number[] | null {
  if (draggedBlockId === target.blockId) return null;
  const ordered = blocks.map((block) => block.id);
  const draggedIndex = ordered.indexOf(draggedBlockId);
  const targetIndex = ordered.indexOf(target.blockId);
  if (draggedIndex < 0 || targetIndex < 0) return null;
  const [removed] = ordered.splice(draggedIndex, 1);
  const nextTargetIndex = ordered.indexOf(target.blockId);
  const insertIndex = nextTargetIndex + (target.position === 'after' ? 1 : 0);
  ordered.splice(insertIndex, 0, removed);
  return ordered;
}

function getPropertyValue(properties: WorkspacePropertyValue[], slug: string) {
  return properties.find((item) => item.property_slug === slug)?.value;
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—';
  if (Array.isArray(value)) return value.join(', ') || '—';
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  return String(value);
}

function buildTree(pages: WorkspacePageSummary[]) {
  const children = new Map<number | null, WorkspacePageSummary[]>();
  for (const page of pages) {
    const bucket = children.get(page.parent_page_id) ?? [];
    bucket.push(page);
    children.set(page.parent_page_id, bucket);
  }
  for (const bucket of children.values()) {
    bucket.sort((left, right) => left.sort_order - right.sort_order || left.title.localeCompare(right.title));
  }
  return children;
}

function getViewConfig(view: WorkspaceView | null | undefined): Record<string, unknown> {
  return typeof view?.config_json === 'object' && view.config_json && !Array.isArray(view.config_json)
    ? (view.config_json as Record<string, unknown>)
    : {};
}

function getOpenMode(view: WorkspaceView | null | undefined): WorkspaceOpenMode {
  const openMode = getViewConfig(view).open_mode;
  if (openMode === 'center_peek' || openMode === 'full_page' || openMode === 'side_peek') {
    return openMode;
  }
  if (view?.view_type === 'gallery' || view?.view_type === 'calendar') {
    return 'center_peek';
  }
  return 'side_peek';
}

function getCardPreview(view: WorkspaceView | null | undefined): CardPreviewMode {
  const preview = getViewConfig(view).card_preview;
  return preview === 'cover' || preview === 'none' || preview === 'icon' ? preview : 'icon';
}

function getTemplateById(templates: WorkspaceTemplate[] | undefined, templateId: number | null) {
  return templates?.find((template) => template.id === templateId) ?? null;
}

function PageIdentity({
  page,
  fallbackIcon = '📄'
}: {
  page: WorkspacePageSummary | WorkspacePageLink;
  fallbackIcon?: string;
}) {
  const summary = useWorkspacePageSummary(page.id, page).data ?? page;
  return (
    <>
      <span>{summary.icon ?? fallbackIcon}</span>
      <span>{summary.title}</span>
    </>
  );
}

function PageTitleText({
  page
}: {
  page: WorkspacePageSummary | WorkspacePageLink;
}) {
  const summary = useWorkspacePageSummary(page.id, page).data ?? page;
  return <>{summary.title}</>;
}

function renderRowMeta(row: WorkspaceRow) {
  const interesting = row.properties.filter((item) => !['title', 'open_tasks', 'done_tasks'].includes(item.property_slug));
  return interesting.slice(0, 3).map((item) => `${item.property_name}: ${formatValue(item.value)}`).join(' · ');
}

function getVisibleProperties(database: WorkspaceDatabaseSummary, view: WorkspaceView | null) {
  const config = getViewConfig(view);
  const visible = Array.isArray(config.visible_properties)
    ? (config.visible_properties as unknown[]).filter((item): item is string => typeof item === 'string')
    : [];
  const hidden = new Set(
    Array.isArray(config.hidden_properties)
      ? (config.hidden_properties as unknown[]).filter((item): item is string => typeof item === 'string')
      : []
  );
  const properties = database.properties.filter((property) =>
    visible.length ? visible.includes(property.slug) : !hidden.has(property.slug)
  );
  return properties.length ? properties : database.properties;
}

function stringifyPropertyValue(value: unknown): string {
  if (Array.isArray(value)) return value.map((item) => stringifyPropertyValue(item)).join(' ');
  if (value === null || value === undefined) return '';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

function filterRowsByQuery(rows: WorkspaceRow[], query: string) {
  const term = query.trim().toLowerCase();
  if (!term) return rows;
  return rows.filter((row) => {
    if (row.page.title.toLowerCase().includes(term)) return true;
    return row.properties.some((property) => stringifyPropertyValue(property.value).toLowerCase().includes(term));
  });
}

function parsePositiveNumber(value: string | null | undefined): number | null {
  if (!value) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

function parseDateValue(value: unknown): Date | null {
  if (!value) return null;
  const parsed = new Date(String(value));
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function startOfMonth(date: Date) {
  return new Date(date.getFullYear(), date.getMonth(), 1);
}

function endOfMonth(date: Date) {
  return new Date(date.getFullYear(), date.getMonth() + 1, 0);
}

function addMonths(date: Date, amount: number) {
  return new Date(date.getFullYear(), date.getMonth() + amount, 1);
}

function DatabaseView({
  database,
  initialViewId,
  relationPropertySlug,
  relationPageId,
  readOnly,
  onOpenPage,
  onPrefetchPage,
  onCreateRow,
  onCreateView,
  onEditView,
  onViewChange
}: {
  database: WorkspaceDatabaseSummary;
  initialViewId?: number | null;
  relationPropertySlug?: string | null;
  relationPageId?: number | null;
  readOnly: boolean;
  onOpenPage: (pageId: number, mode?: WorkspaceOpenMode) => void;
  onPrefetchPage: (pageId: number) => void;
  onCreateRow: (database: WorkspaceDatabaseSummary, view: WorkspaceView | null, initialProperties?: Record<string, unknown>) => void;
  onCreateView: (database: WorkspaceDatabaseSummary) => void;
  onEditView: (database: WorkspaceDatabaseSummary, view: WorkspaceView | null) => void;
  onViewChange?: (viewId: number | null) => void;
}) {
  const [selectedViewId, setSelectedViewId] = useState<number | null>(initialViewId ?? null);
  const [rowLimit, setRowLimit] = useState(50);
  const [viewSearch, setViewSearch] = useState('');
  useEffect(() => {
    setSelectedViewId(initialViewId ?? null);
  }, [initialViewId]);
  useEffect(() => {
    setRowLimit(50);
    setViewSearch('');
  }, [database.id, selectedViewId]);
  const rowsQuery = useWorkspaceDatabase(
    database.id,
    selectedViewId,
    true,
    0,
    rowLimit,
    relationPropertySlug,
    relationPageId
  );
  const view = rowsQuery.data?.view ?? database.views.find((item) => item.is_default) ?? database.views[0] ?? null;
  const visibleProperties = getVisibleProperties(database, view);
  const viewConfig = getViewConfig(view);
  const openMode = getOpenMode(view);
  const groupBy = String(viewConfig.group_by ?? '');
  const dateProperty = String(viewConfig.date_property ?? '');
  const cardPreview = getCardPreview(view);
  const rows = useMemo(
    () => filterRowsByQuery(rowsQuery.data?.rows ?? [], viewSearch),
    [rowsQuery.data?.rows, viewSearch]
  );
  const datedRows = useMemo(
    () =>
      rows
        .map((row) => ({
          row,
          date: parseDateValue(getPropertyValue(row.properties, dateProperty || 'due')),
        }))
        .filter((item): item is { row: WorkspaceRow; date: Date } => item.date instanceof Date)
        .sort((left, right) => left.date.getTime() - right.date.getTime()),
    [dateProperty, rows]
  );
  const [calendarCursor, setCalendarCursor] = useState<Date>(() =>
    startOfMonth(datedRows[0]?.date ?? new Date())
  );
  useEffect(() => {
    setCalendarCursor(startOfMonth(datedRows[0]?.date ?? new Date()));
  }, [selectedViewId]);
  const openRow = (pageId: number) => onOpenPage(pageId, openMode);
  const selectView = (viewId: number | null) => {
    setSelectedViewId(viewId);
    onViewChange?.(viewId);
  };

  const renderTable = () => (
    <Table>
      <thead>
        <tr>
          {visibleProperties.map((property) => (
            <th key={property.id}>{property.name}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.page.id}>
            {visibleProperties.map((property) => (
              <td key={`${row.page.id}-${property.id}`}>
                <RowButton
                  onClick={() => openRow(row.page.id)}
                  onMouseEnter={() => onPrefetchPage(row.page.id)}
                  onFocus={() => onPrefetchPage(row.page.id)}
                >
                  {formatValue(getPropertyValue(row.properties, property.slug))}
                </RowButton>
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </Table>
  );

  const renderBoard = () => {
    const groups = new Map<string, WorkspaceRow[]>();
    for (const row of rows) {
      const key = String(getPropertyValue(row.properties, groupBy || 'status') ?? 'Ungrouped');
      const bucket = groups.get(key) ?? [];
      bucket.push(row);
      groups.set(key, bucket);
    }
    return (
      <Board>
        {[...groups.entries()].map(([group, groupRows]) => (
          <BoardColumn key={group}>
            <strong>{group}</strong>
            {groupRows.map((row) => (
              <BoardCard
                key={row.page.id}
                onClick={() => openRow(row.page.id)}
                onMouseEnter={() => onPrefetchPage(row.page.id)}
                onFocus={() => onPrefetchPage(row.page.id)}
              >
                <strong><PageTitleText page={row.page} /></strong>
                <Muted>{renderRowMeta(row) || 'Open page'}</Muted>
              </BoardCard>
            ))}
          </BoardColumn>
        ))}
      </Board>
    );
  };

  const renderList = () => (
    <ListView>
      {rows.map((row) => (
        <ListRow
          key={row.page.id}
          onClick={() => openRow(row.page.id)}
          onMouseEnter={() => onPrefetchPage(row.page.id)}
          onFocus={() => onPrefetchPage(row.page.id)}
        >
          <strong><PageTitleText page={row.page} /></strong>
          <Muted>{renderRowMeta(row) || 'Open page'}</Muted>
        </ListRow>
      ))}
    </ListView>
  );

  const renderGallery = () => (
    <GalleryGrid>
      {rows.map((row) => (
        <GalleryCard
          key={row.page.id}
          onClick={() => openRow(row.page.id)}
          onMouseEnter={() => onPrefetchPage(row.page.id)}
          onFocus={() => onPrefetchPage(row.page.id)}
        >
          {cardPreview === 'cover' ? (
            <GalleryPreview $url={row.page.cover_url}>
              <MetaPill>{database.icon ?? '📄'} {database.name}</MetaPill>
            </GalleryPreview>
          ) : (
            <GalleryPreview>
              <span style={{ fontSize: '2rem' }}>{cardPreview === 'none' ? '•' : row.page.icon ?? '📄'}</span>
            </GalleryPreview>
          )}
          <GalleryBody>
            <strong><PageTitleText page={row.page} /></strong>
            <Muted>{renderRowMeta(row) || 'Open page'}</Muted>
          </GalleryBody>
        </GalleryCard>
      ))}
    </GalleryGrid>
  );

  const renderCalendar = () => {
    const monthStart = startOfMonth(calendarCursor);
    const monthEnd = endOfMonth(calendarCursor);
    const gridStart = new Date(monthStart);
    gridStart.setDate(gridStart.getDate() - gridStart.getDay());
    const gridEnd = new Date(monthEnd);
    gridEnd.setDate(gridEnd.getDate() + (6 - gridEnd.getDay()));
    const rowsByDay = new Map<string, WorkspaceRow[]>();
    for (const item of datedRows) {
      const key = item.date.toISOString().slice(0, 10);
      const bucket = rowsByDay.get(key) ?? [];
      bucket.push(item.row);
      rowsByDay.set(key, bucket);
    }
    const cells: Date[] = [];
    const cursor = new Date(gridStart);
    while (cursor <= gridEnd) {
      cells.push(new Date(cursor));
      cursor.setDate(cursor.getDate() + 1);
    }
    return (
      <CalendarList>
        <MetaRow>
          <PillButton type="button" onClick={() => setCalendarCursor((current) => addMonths(current, -1))}>
            Previous
          </PillButton>
          <MetaPill>
            {monthStart.toLocaleDateString(undefined, { month: 'long', year: 'numeric' })}
          </MetaPill>
          <PillButton type="button" onClick={() => setCalendarCursor((current) => addMonths(current, 1))}>
            Next
          </PillButton>
        </MetaRow>
        <CalendarGrid>
          {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((label) => (
            <CalendarHeaderCell key={label}>{label}</CalendarHeaderCell>
          ))}
          {cells.map((date) => {
            const key = date.toISOString().slice(0, 10);
            const dayRows = rowsByDay.get(key) ?? [];
            return (
              <CalendarDay
                key={key}
                $muted={date.getMonth() !== monthStart.getMonth()}
              >
                <CalendarDayLabel>{date.getDate()}</CalendarDayLabel>
                {dayRows.map((row) => (
                  <MiniCard
                    key={row.page.id}
                    onClick={() => openRow(row.page.id)}
                    onMouseEnter={() => onPrefetchPage(row.page.id)}
                    onFocus={() => onPrefetchPage(row.page.id)}
                  >
                    <strong><PageTitleText page={row.page} /></strong>
                    <Muted>{renderRowMeta(row) || 'Open page'}</Muted>
                  </MiniCard>
                ))}
              </CalendarDay>
            );
          })}
        </CalendarGrid>
      </CalendarList>
    );
  };

  const renderTimeline = () => {
    if (!datedRows.length) return <Muted>No dated rows in this view.</Muted>;
    const min = datedRows[0].date;
    const max = datedRows[datedRows.length - 1].date;
    const range = Math.max(1, max.getTime() - min.getTime());
    return (
      <Timeline>
        <MetaPill>
          {min.toLocaleDateString()} - {max.toLocaleDateString()}
        </MetaPill>
        {datedRows.map((item) => {
          const offset = ((item.date.getTime() - min.getTime()) / range) * 100;
          return (
            <TimelineRow key={item.row.page.id}>
              <div>
                <strong><PageTitleText page={item.row.page} /></strong>
                <Muted>{renderRowMeta(item.row) || item.date.toLocaleDateString()}</Muted>
              </div>
              <TimelineTrack>
                <TimelineBar
                  $offset={offset}
                  onClick={() => openRow(item.row.page.id)}
                  onMouseEnter={() => onPrefetchPage(item.row.page.id)}
                  onFocus={() => onPrefetchPage(item.row.page.id)}
                >
                  {item.row.page.title}
                </TimelineBar>
              </TimelineTrack>
            </TimelineRow>
          );
        })}
      </Timeline>
    );
  };

  return (
    <DatabaseCard>
      <DatabaseHeader>
        <DatabaseHeaderTop>
          <div>
            <strong>{database.icon} {database.name}</strong>
            <Muted>{database.description}</Muted>
          </div>
          <ViewTabs>
            {database.views.map((item) => (
              <ViewTab key={item.id} $active={view?.id === item.id} onClick={() => selectView(item.id)}>
                {item.name}
              </ViewTab>
            ))}
            {!readOnly ? <ViewTab onClick={() => onCreateView(database)}>+ View</ViewTab> : null}
            {!readOnly ? (
              <ViewTab
                onClick={() =>
                  onCreateRow(
                    database,
                    view,
                    relationPropertySlug && relationPageId ? { [relationPropertySlug]: relationPageId } : undefined
                  )
                }
              >
                + New
              </ViewTab>
            ) : null}
            {!readOnly && view ? <ViewTab onClick={() => onEditView(database, view)}>Edit</ViewTab> : null}
          </ViewTabs>
        </DatabaseHeaderTop>
        <DatabaseToolbar>
          <PropertyInput
            value={viewSearch}
            placeholder="Search this database…"
            onChange={(event) => setViewSearch(event.target.value)}
          />
          <MetaPill>{rows.length} visible</MetaPill>
        </DatabaseToolbar>
      </DatabaseHeader>
      <DatabaseBody>
        {rowsQuery.isLoading ? <Muted>Loading rows…</Muted> : null}
        {!rowsQuery.isLoading && rows.length === 0 ? <Muted>No rows in this view.</Muted> : null}
        {!rowsQuery.isLoading && rows.length > 0
          ? view?.view_type === 'board'
            ? renderBoard()
            : view?.view_type === 'gallery'
              ? renderGallery()
            : view?.view_type === 'calendar'
              ? renderCalendar()
            : view?.view_type === 'timeline'
              ? renderTimeline()
              : view?.view_type === 'list'
                ? renderList()
                : renderTable()
          : null}
        {!rowsQuery.isLoading && rowsQuery.data?.has_more ? (
          <MetaRow style={{ paddingTop: 12 }}>
            <PillButton type="button" onClick={() => setRowLimit((current) => current + 50)}>
              Load more
            </PillButton>
            <Muted>
              Showing {rows.length} of {rowsQuery.data.total_count}
            </Muted>
          </MetaRow>
        ) : null}
      </DatabaseBody>
    </DatabaseCard>
  );
}

function PageProperties({
  detail,
  readOnly,
  relationChoices,
  onSave
}: {
  detail: WorkspacePageDetail;
  readOnly: boolean;
  relationChoices: WorkspacePageSummary[];
  onSave: (values: Record<string, unknown>) => Promise<void>;
}) {
  const [drafts, setDrafts] = useState<Record<string, unknown>>({});
  useEffect(() => {
    const next: Record<string, unknown> = {};
    for (const property of detail.properties) {
      next[property.property_slug] = property.value;
    }
    setDrafts(next);
  }, [detail.page.id, detail.properties]);

  const commit = async (slug: string) => {
    if (readOnly) return;
    await onSave({ [slug]: drafts[slug] });
  };

  if (!detail.properties.length) return null;

  return (
    <PropertiesGrid>
      {detail.properties
        .filter((property) => property.property_slug !== 'title')
        .map((property) => (
          <PropertyRow key={property.property_id}>
            <PropertyLabel>{property.property_name}</PropertyLabel>
            {property.property_type === 'checkbox' ? (
              <Toggle
                type="checkbox"
                checked={Boolean(drafts[property.property_slug])}
                disabled={readOnly}
                onChange={async (event) => {
                  const checked = event.target.checked;
                  setDrafts((current) => ({ ...current, [property.property_slug]: checked }));
                  if (!readOnly) await onSave({ [property.property_slug]: checked });
                }}
              />
            ) : property.property_type === 'select' || property.property_type === 'status' ? (
              <PropertySelect
                value={String(drafts[property.property_slug] ?? '')}
                disabled={readOnly}
                onChange={async (event) => {
                  const value = event.target.value;
                  setDrafts((current) => ({ ...current, [property.property_slug]: value }));
                  if (!readOnly) await onSave({ [property.property_slug]: value });
                }}
              >
                <option value="">None</option>
                {detail.database?.properties
                  .find((item) => item.slug === property.property_slug)
                  ?.options.map((option) => (
                    <option key={option.id} value={option.value}>
                      {option.label}
                    </option>
                  ))}
              </PropertySelect>
            ) : property.property_type === 'relation' ? (
              <RelationEditor>
                <ChipRow>
                  {drafts[property.property_slug] ? (
                    <TokenChip>
                      {relationChoices.find((page) => page.id === Number(drafts[property.property_slug])) ? (
                        <PageIdentity
                          page={relationChoices.find((page) => page.id === Number(drafts[property.property_slug]))!}
                        />
                      ) : (
                        `Page ${drafts[property.property_slug]}`
                      )}
                      {!readOnly ? (
                        <TokenRemove
                          type="button"
                          onClick={async () => {
                            setDrafts((current) => ({ ...current, [property.property_slug]: null }));
                            await onSave({ [property.property_slug]: null });
                          }}
                        >
                          ×
                        </TokenRemove>
                      ) : null}
                    </TokenChip>
                  ) : (
                    <Muted>No linked page</Muted>
                  )}
                </ChipRow>
                <PropertySelect
                  value={String(drafts[property.property_slug] ?? '')}
                  disabled={readOnly}
                  onChange={async (event) => {
                    const raw = event.target.value;
                    const value = raw ? Number(raw) : null;
                    setDrafts((current) => ({ ...current, [property.property_slug]: value }));
                    if (!readOnly) await onSave({ [property.property_slug]: value });
                  }}
                >
                  <option value="">None</option>
                  {relationChoices.map((page) => (
                    <option key={page.id} value={page.id}>
                      {page.title}
                    </option>
                  ))}
                </PropertySelect>
              </RelationEditor>
            ) : property.property_type === 'date' ? (
              <PropertyInput
                type="datetime-local"
                value={toDateTimeLocalValue(drafts[property.property_slug])}
                disabled={readOnly}
                onChange={(event) =>
                  setDrafts((current) => ({ ...current, [property.property_slug]: fromDateTimeLocalValue(event.target.value) }))
                }
                onBlur={() => void commit(property.property_slug)}
              />
            ) : property.property_type === 'multi_select' ? (
              <PropertyInput
                value={Array.isArray(drafts[property.property_slug]) ? String((drafts[property.property_slug] as unknown[]).join(', ')) : ''}
                disabled={readOnly}
                onChange={(event) =>
                  setDrafts((current) => ({
                    ...current,
                    [property.property_slug]: event.target.value
                      .split(',')
                      .map((item) => item.trim())
                      .filter(Boolean)
                  }))
                }
                onBlur={() => void commit(property.property_slug)}
              />
            ) : (
              <PropertyInput
                value={String(drafts[property.property_slug] ?? '')}
                disabled={readOnly}
                onChange={(event) =>
                  setDrafts((current) => ({ ...current, [property.property_slug]: event.target.value }))
                }
                onBlur={() => void commit(property.property_slug)}
              />
            )}
          </PropertyRow>
        ))}
    </PropertiesGrid>
  );
}

function BlocksSection({
  detail,
  bootstrap,
  readOnly,
  onOpenPage,
  onPrefetchPage,
  onCreateBlock,
  onCreateChildPageBlock,
  onCreateRow,
  onCreateView,
  onEditView,
  onUpdateBlock,
  onDeleteBlock,
  onReorderBlocks
}: {
  detail: WorkspacePageDetail;
  bootstrap: ReturnType<typeof useWorkspaceBootstrap>['data'];
  readOnly: boolean;
  onOpenPage: (pageId: number, mode?: WorkspaceOpenMode) => void;
  onPrefetchPage: (pageId: number) => void;
  onCreateBlock: (
    pageId: number,
    afterBlockId?: number | null,
    type?: string,
    payload?: { text_content?: string; checked?: boolean; data_json?: Record<string, unknown> | unknown[] | null }
  ) => Promise<void>;
  onCreateChildPageBlock: (block: WorkspaceBlock, title?: string) => Promise<void>;
  onCreateRow: (database: WorkspaceDatabaseSummary, view: WorkspaceView | null, initialProperties?: Record<string, unknown>) => void;
  onCreateView: (database: WorkspaceDatabaseSummary) => void;
  onEditView: (database: WorkspaceDatabaseSummary, view: WorkspaceView | null) => void;
  onUpdateBlock: (blockId: number, payload: { block_type?: string; text_content?: string; checked?: boolean; data_json?: Record<string, unknown> | unknown[] | null }) => Promise<void>;
  onDeleteBlock: (blockId: number) => Promise<void>;
  onReorderBlocks: (pageId: number, orderedBlockIds: number[]) => Promise<void>;
}) {
  const [drafts, setDrafts] = useState<Record<number, string>>({});
  const [slashSelection, setSlashSelection] = useState<Record<number, number>>({});
  const [linkComposer, setLinkComposer] = useState<InlineLinkComposerState | null>(null);
  const [menuBlockId, setMenuBlockId] = useState<number | null>(null);
  const [draggingBlockId, setDraggingBlockId] = useState<number | null>(null);
  const [dragTarget, setDragTarget] = useState<BlockDragTarget | null>(null);
  const linkSearchQuery = useWorkspaceSearch(linkComposer?.query ?? '', Boolean(linkComposer?.query.trim()));
  useEffect(() => {
    const next: Record<number, string> = {};
    for (const block of detail.blocks) next[block.id] = block.text_content;
    setDrafts(next);
    setLinkComposer(null);
    setMenuBlockId(null);
    setDraggingBlockId(null);
    setDragTarget(null);
  }, [detail.blocks, detail.page.id]);

  const applySlash = async (block: WorkspaceBlock, nextType: string) => {
    const defaultDatabase = bootstrap?.databases[0];
    const defaultView = defaultDatabase?.views.find((item) => item.is_default) ?? defaultDatabase?.views[0];
    if (nextType === 'child_page') {
      await onCreateChildPageBlock(block, block.text_content || 'Untitled');
      return;
    }
    await onUpdateBlock(block.id, {
      block_type: nextType,
      text_content:
        nextType === 'bookmark' || nextType === 'embed'
          ? 'https://'
          : nextType === 'image' || nextType === 'file'
            ? block.text_content
            : '',
      data_json:
        nextType === 'linked_database' && defaultDatabase && defaultView
          ? { database_id: defaultDatabase.id, view_id: defaultView.id }
          : nextType === 'toggle'
            ? { collapsed: false }
          : null
    });
  };

  const duplicateBlock = async (block: WorkspaceBlock) =>
    onCreateBlock(block.page_id, block.id, block.block_type, {
      text_content: block.text_content,
      checked: block.checked,
      data_json: block.data_json
    });

  const moveBlock = async (blockId: number, direction: -1 | 1) => {
    const ordered = detail.blocks.map((item) => item.id);
    const index = ordered.indexOf(blockId);
    const nextIndex = index + direction;
    if (index < 0 || nextIndex < 0 || nextIndex >= ordered.length) return;
    [ordered[index], ordered[nextIndex]] = [ordered[nextIndex], ordered[index]];
    await onReorderBlocks(detail.page.id, ordered);
  };

  const uploadAsset = async (block: WorkspaceBlock, file: File) => {
    const asset = await createWorkspaceAssetUpload({
      page_id: detail.page.id,
      block_id: block.id,
      name: file.name,
      mime_type: file.type || null,
      size_bytes: file.size
    });
    await uploadWorkspaceAssetContent(asset.upload_url, file, asset.headers);
    await onUpdateBlock(block.id, {
      data_json: {
        ...(typeof block.data_json === 'object' && block.data_json && !Array.isArray(block.data_json)
          ? block.data_json
          : {}),
        asset_id: asset.asset_id,
        url: asset.public_url,
        name: file.name,
        mime_type: file.type || null
      },
      text_content: block.text_content || file.name
    });
  };

  const insertPageLink = async (block: WorkspaceBlock, title: string) => {
    const current = drafts[block.id] ?? block.text_content;
    const separator = current.trim() ? ' ' : '';
    const nextText = `${current}${separator}[[${title}]]`.trim();
    setDrafts((currentDrafts) => ({ ...currentDrafts, [block.id]: nextText }));
    setLinkComposer(null);
    await onUpdateBlock(block.id, { text_content: nextText });
  };

  const handleDragOver = (event: DragEvent<HTMLDivElement>, blockId: number) => {
    if (readOnly || draggingBlockId === null) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
    const rect = event.currentTarget.getBoundingClientRect();
    const position = event.clientY < rect.top + rect.height / 2 ? 'before' : 'after';
    setDragTarget((current) =>
      current?.blockId === blockId && current.position === position ? current : { blockId, position }
    );
  };

  const handleDrop = async (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    if (readOnly || draggingBlockId === null || dragTarget === null) {
      setDraggingBlockId(null);
      setDragTarget(null);
      return;
    }
    const ordered = reorderBlockIds(detail.blocks, draggingBlockId, dragTarget);
    setDraggingBlockId(null);
    setDragTarget(null);
    if (ordered) await onReorderBlocks(detail.page.id, ordered);
  };

  return (
    <BlockList>
      {detail.blocks.map((block) => {
        const text = drafts[block.id] ?? block.text_content;
        const showSlash = !readOnly && text.startsWith('/');
        const slashOptions = BLOCK_OPTIONS.filter((option) => option.label.toLowerCase().includes(text.slice(1).toLowerCase()));
        const activeSlashIndex = Math.min(slashSelection[block.id] ?? 0, Math.max(slashOptions.length - 1, 0));
        const linkedDatabaseId =
          typeof block.data_json === 'object' && block.data_json && !Array.isArray(block.data_json)
            ? Number((block.data_json as Record<string, unknown>).database_id ?? NaN)
            : null;
        const linkedViewId =
          typeof block.data_json === 'object' && block.data_json && !Array.isArray(block.data_json)
            ? Number((block.data_json as Record<string, unknown>).view_id ?? NaN)
            : null;
        const relationPropertySlug =
          typeof block.data_json === 'object' && block.data_json && !Array.isArray(block.data_json)
            ? String((block.data_json as Record<string, unknown>).filter_property_slug ?? '')
            : '';
        const rawRelationPageId =
          typeof block.data_json === 'object' && block.data_json && !Array.isArray(block.data_json)
            ? (block.data_json as Record<string, unknown>).filter_page_id
            : null;
        const relationPageId =
          rawRelationPageId === 'current_page'
            ? detail.page.id
            : typeof rawRelationPageId === 'number'
              ? rawRelationPageId
              : null;
        const blockData =
          typeof block.data_json === 'object' && block.data_json && !Array.isArray(block.data_json)
            ? (block.data_json as Record<string, unknown>)
            : {};
        const linkedDatabase = bootstrap?.databases.find((database) => database.id === linkedDatabaseId) ?? null;
        const linkComposerOpen = linkComposer?.blockId === block.id;
        const menuOpen = menuBlockId === block.id;
        const canLinkPage = !['linked_database', 'divider', 'image', 'file', 'child_page'].includes(block.block_type);
        return (
          <BlockRow
            key={block.id}
            data-block-id={block.id}
            $isDragging={draggingBlockId === block.id}
            onDragOver={(event) => handleDragOver(event, block.id)}
            onDrop={(event) => void handleDrop(event)}
          >
            <BlockGutter $hidden={readOnly}>
              <GutterButton
                type="button"
                title="Drag to move"
                draggable={!readOnly}
                $dragging={draggingBlockId === block.id}
                onDragStart={(event) => {
                  if (readOnly) return;
                  event.dataTransfer.effectAllowed = 'move';
                  event.dataTransfer.setData('text/plain', String(block.id));
                  setDraggingBlockId(block.id);
                  setDragTarget(null);
                }}
                onDragEnd={() => {
                  setDraggingBlockId(null);
                  setDragTarget(null);
                }}
              >
                ⋮⋮
              </GutterButton>
              <GutterButton
                type="button"
                title="Insert block below"
                onClick={() => void onCreateBlock(block.page_id, block.id, 'paragraph')}
              >
                +
              </GutterButton>
              <GutterButton
                type="button"
                title="Block menu"
                onClick={() => {
                  setLinkComposer(null);
                  setMenuBlockId((current) => (current === block.id ? null : block.id));
                }}
              >
                ⋯
              </GutterButton>
            </BlockGutter>
            <BlockCard>
              {dragTarget?.blockId === block.id && draggingBlockId !== null && draggingBlockId !== block.id ? (
                <BlockDropIndicator $position={dragTarget.position} />
              ) : null}
              {menuOpen ? (
                <BlockMenu>
                  <BlockMenuLabel>Turn Into</BlockMenuLabel>
                  {BLOCK_OPTIONS.map((option) => (
                    <BlockMenuButton
                      key={option.type}
                      type="button"
                      onClick={() => {
                        setMenuBlockId(null);
                        void applySlash(block, option.type);
                      }}
                    >
                      {option.type === block.block_type ? '✓ ' : ''}
                      {option.label}
                    </BlockMenuButton>
                  ))}
                  <BlockMenuLabel>Actions</BlockMenuLabel>
                  {canLinkPage ? (
                    <BlockMenuButton
                      type="button"
                      onClick={() => {
                        setMenuBlockId(null);
                        setLinkComposer({ blockId: block.id, query: '' });
                      }}
                    >
                      Link page
                    </BlockMenuButton>
                  ) : null}
                  <BlockMenuButton
                    type="button"
                    onClick={() => {
                      setMenuBlockId(null);
                      void duplicateBlock(block);
                    }}
                  >
                    Duplicate
                  </BlockMenuButton>
                  <BlockMenuButton
                    type="button"
                    onClick={() => {
                      setMenuBlockId(null);
                      void moveBlock(block.id, -1);
                    }}
                  >
                    Move up
                  </BlockMenuButton>
                  <BlockMenuButton
                    type="button"
                    onClick={() => {
                      setMenuBlockId(null);
                      void moveBlock(block.id, 1);
                    }}
                  >
                    Move down
                  </BlockMenuButton>
                  <BlockMenuButton
                    type="button"
                    onClick={() => {
                      setMenuBlockId(null);
                      void onDeleteBlock(block.id);
                    }}
                  >
                    Delete
                  </BlockMenuButton>
                </BlockMenu>
              ) : null}
              {block.block_type === 'linked_database' && linkedDatabase ? (
                <>
                  {!readOnly ? (
                    <MetaRow>
                      <PropertySelect
                        value={String(linkedDatabase.id)}
                        onChange={async (event) => {
                          const database = bootstrap?.databases.find((item) => item.id === Number(event.target.value));
                          const nextView = database?.views.find((item) => item.is_default) ?? database?.views[0];
                          await onUpdateBlock(block.id, {
                            data_json: database && nextView ? { database_id: database.id, view_id: nextView.id } : null
                          });
                        }}
                      >
                        {bootstrap?.databases.map((database) => (
                          <option key={database.id} value={database.id}>
                            {database.name}
                          </option>
                        ))}
                      </PropertySelect>
                    </MetaRow>
                  ) : null}
                  <DatabaseView
                    database={linkedDatabase}
                    initialViewId={Number.isFinite(linkedViewId) ? linkedViewId : null}
                    relationPropertySlug={relationPropertySlug || null}
                    relationPageId={relationPageId}
                    readOnly={readOnly}
                    onOpenPage={onOpenPage}
                    onPrefetchPage={onPrefetchPage}
                    onCreateRow={onCreateRow}
                    onCreateView={onCreateView}
                    onEditView={onEditView}
                    onViewChange={async (viewId) => {
                      await onUpdateBlock(block.id, {
                        data_json: {
                          ...blockData,
                          database_id: linkedDatabase.id,
                          view_id: viewId
                        }
                      });
                    }}
                  />
                </>
              ) : block.block_type === 'image' ? (
                <ChildPages>
                  {blockData.url ? <img src={String(blockData.url)} alt={text || 'Workspace image'} style={{ maxWidth: '100%', borderRadius: 18 }} /> : <Muted>No image uploaded yet.</Muted>}
                  {!readOnly ? (
                    <MetaRow>
                      <PropertyInput
                        value={text}
                        placeholder="Caption"
                        onChange={(event) => setDrafts((current) => ({ ...current, [block.id]: event.target.value }))}
                        onBlur={() => void onUpdateBlock(block.id, { text_content: drafts[block.id] ?? text })}
                      />
                      <PropertyInput
                        type="file"
                        accept="image/*"
                        onChange={(event) => {
                          const file = event.target.files?.[0];
                          if (file) void uploadAsset(block, file);
                        }}
                      />
                    </MetaRow>
                  ) : null}
                </ChildPages>
              ) : block.block_type === 'file' ? (
                <ChildPages>
                  {blockData.url ? (
                    <ChildCard as="a" href={String(blockData.url)} target="_blank" rel="noreferrer">
                      <strong>{String(blockData.name ?? (text || 'File'))}</strong>
                      <ChildDescription>{String(blockData.mime_type ?? 'File asset')}</ChildDescription>
                    </ChildCard>
                  ) : (
                    <Muted>No file uploaded yet.</Muted>
                  )}
                  {!readOnly ? (
                    <MetaRow>
                      <PropertyInput
                        type="file"
                        onChange={(event) => {
                          const file = event.target.files?.[0];
                          if (file) void uploadAsset(block, file);
                        }}
                      />
                    </MetaRow>
                  ) : null}
                </ChildPages>
              ) : block.block_type === 'bookmark' || block.block_type === 'embed' ? (
                <ChildPages>
                  <PropertyInput
                    value={text}
                    readOnly={readOnly}
                    placeholder="https://"
                    onChange={(event) => setDrafts((current) => ({ ...current, [block.id]: event.target.value }))}
                    onBlur={() => void onUpdateBlock(block.id, { text_content: drafts[block.id] ?? text })}
                  />
                  {text.trim() ? (
                    <ChildCard as="a" href={text.trim()} target="_blank" rel="noreferrer">
                      <strong>{block.block_type === 'embed' ? 'Embedded link' : 'Bookmark'}</strong>
                      <ChildDescription>{text.trim()}</ChildDescription>
                    </ChildCard>
                  ) : null}
                </ChildPages>
              ) : block.block_type === 'child_page' ? (
                blockData.page_id ? (
                  <ChildCard
                    onClick={() => onOpenPage(Number(blockData.page_id))}
                    onMouseEnter={() => onPrefetchPage(Number(blockData.page_id))}
                    onFocus={() => onPrefetchPage(Number(blockData.page_id))}
                  >
                    <strong>
                      <PageIdentity
                        page={{
                          id: Number(blockData.page_id),
                          title: text || 'Untitled',
                          kind: 'page',
                          icon: String(blockData.icon ?? '📄')
                        }}
                      />
                    </strong>
                    <ChildDescription>Child page</ChildDescription>
                  </ChildCard>
                ) : (
                  <PillButton type="button" onClick={() => void onCreateChildPageBlock(block, text || 'Untitled')}>
                    Create child page
                  </PillButton>
                )
              ) : block.block_type === 'toggle' ? (
                <ChildPages>
                  <PillButton
                    type="button"
                    onClick={() =>
                      void onUpdateBlock(block.id, {
                        data_json: { ...blockData, collapsed: !Boolean(blockData.collapsed) }
                      })
                    }
                  >
                    {Boolean(blockData.collapsed) ? '▸' : '▾'} Toggle
                  </PillButton>
                  {!Boolean(blockData.collapsed) ? (
                    <BlockEditor
                      as="textarea"
                      rows={2}
                      $type="paragraph"
                      value={text}
                      readOnly={readOnly}
                      placeholder="Toggle contents"
                      onChange={(event) => setDrafts((current) => ({ ...current, [block.id]: event.target.value }))}
                      onBlur={() => void onUpdateBlock(block.id, { text_content: text })}
                    />
                  ) : null}
                </ChildPages>
              ) : block.block_type === 'favorites' ? (
                <ChildPages>
                  <SectionTitle>Favorites</SectionTitle>
                  <ChildGrid>
                    {(bootstrap?.favorites ?? []).map((page) => (
                      <ChildCard
                        key={page.id}
                        onClick={() => onOpenPage(page.id)}
                        onMouseEnter={() => onPrefetchPage(page.id)}
                        onFocus={() => onPrefetchPage(page.id)}
                      >
                        <strong><PageIdentity page={page} /></strong>
                        <ChildDescription>{page.kind}</ChildDescription>
                      </ChildCard>
                    ))}
                  </ChildGrid>
                </ChildPages>
              ) : block.block_type === 'recent_pages' ? (
                <ChildPages>
                  <SectionTitle>Recent</SectionTitle>
                  <ChildGrid>
                    {(bootstrap?.recent_pages ?? []).map((page) => (
                      <ChildCard
                        key={page.id}
                        onClick={() => onOpenPage(page.id)}
                        onMouseEnter={() => onPrefetchPage(page.id)}
                        onFocus={() => onPrefetchPage(page.id)}
                      >
                        <strong><PageIdentity page={page} /></strong>
                        <ChildDescription>{page.kind}</ChildDescription>
                      </ChildCard>
                    ))}
                  </ChildGrid>
                </ChildPages>
              ) : block.block_type === 'divider' ? (
                <hr />
              ) : block.block_type === 'todo_item' ? (
                <TodoBlock>
                  <Toggle
                    type="checkbox"
                    checked={block.checked}
                    disabled={readOnly}
                    onChange={(event) => void onUpdateBlock(block.id, { checked: event.target.checked })}
                  />
                  <BlockEditor
                    as="textarea"
                    rows={1}
                    $type="paragraph"
                    value={text}
                    readOnly={readOnly}
                    onChange={(event) => setDrafts((current) => ({ ...current, [block.id]: event.target.value }))}
                    onBlur={() => void onUpdateBlock(block.id, { text_content: text })}
                    onKeyDown={(event) => {
                      if (readOnly) return;
                      if (showSlash && slashOptions.length) {
                        if (event.key === 'ArrowDown') {
                          event.preventDefault();
                          setSlashSelection((current) => ({ ...current, [block.id]: Math.min(activeSlashIndex + 1, slashOptions.length - 1) }));
                          return;
                        }
                        if (event.key === 'ArrowUp') {
                          event.preventDefault();
                          setSlashSelection((current) => ({ ...current, [block.id]: Math.max(activeSlashIndex - 1, 0) }));
                          return;
                        }
                        if (event.key === 'Enter') {
                          event.preventDefault();
                          void applySlash(block, slashOptions[activeSlashIndex].type);
                          return;
                        }
                        if (event.key === 'Escape') {
                          event.preventDefault();
                          setDrafts((current) => ({ ...current, [block.id]: '' }));
                          return;
                        }
                      }
                      if (event.key === 'Enter' && !event.shiftKey) {
                        event.preventDefault();
                        void onUpdateBlock(block.id, { text_content: text });
                        void onCreateBlock(block.page_id, block.id, 'paragraph');
                      }
                      if (event.key === 'Backspace' && !text.trim()) {
                        event.preventDefault();
                        void onDeleteBlock(block.id);
                      }
                    }}
                  />
                </TodoBlock>
              ) : (
                <BlockEditor
                  as="textarea"
                  rows={block.block_type === 'heading_1' ? 1 : 2}
                  $type={block.block_type}
                  value={text}
                  readOnly={readOnly}
                  placeholder="Type '/' for commands"
                  onChange={(event) => setDrafts((current) => ({ ...current, [block.id]: event.target.value }))}
                  onBlur={() => void onUpdateBlock(block.id, { text_content: text })}
                  onKeyDown={(event) => {
                    if (readOnly) return;
                    if (showSlash && slashOptions.length) {
                      if (event.key === 'ArrowDown') {
                        event.preventDefault();
                        setSlashSelection((current) => ({ ...current, [block.id]: Math.min(activeSlashIndex + 1, slashOptions.length - 1) }));
                        return;
                      }
                      if (event.key === 'ArrowUp') {
                        event.preventDefault();
                        setSlashSelection((current) => ({ ...current, [block.id]: Math.max(activeSlashIndex - 1, 0) }));
                        return;
                      }
                      if (event.key === 'Enter') {
                        event.preventDefault();
                        void applySlash(block, slashOptions[activeSlashIndex].type);
                        return;
                      }
                      if (event.key === 'Escape') {
                        event.preventDefault();
                        setDrafts((current) => ({ ...current, [block.id]: '' }));
                        return;
                      }
                    }
                    if (event.key === 'Enter' && !event.shiftKey && block.block_type !== 'code') {
                      event.preventDefault();
                      void onUpdateBlock(block.id, { text_content: text });
                      void onCreateBlock(block.page_id, block.id, 'paragraph');
                    }
                    if (event.key === 'Backspace' && !text.trim()) {
                      event.preventDefault();
                      void onDeleteBlock(block.id);
                    }
                  }}
                />
              )}
              {showSlash ? (
                <SlashMenu>
                  {slashOptions.map((option, index) => (
                    <SlashMenuOption
                      key={option.type}
                      $active={index === activeSlashIndex}
                      onClick={() => void applySlash(block, option.type)}
                    >
                      {option.label}
                    </SlashMenuOption>
                  ))}
                </SlashMenu>
              ) : null}
              {linkComposerOpen ? (
                <InlineComposer>
                  <InlineComposerInput
                    autoFocus
                    value={linkComposer.query}
                    placeholder="Search pages to link…"
                    onChange={(event) =>
                      setLinkComposer((current) =>
                        current ? { ...current, query: event.target.value } : current
                      )
                    }
                  />
                  {linkSearchQuery.data?.results.map((result) => (
                    <SlashMenuOption
                      key={result.page.id}
                      onClick={() => void insertPageLink(block, result.page.title)}
                    >
                      <PageIdentity page={result.page} />
                    </SlashMenuOption>
                  ))}
                  {!linkSearchQuery.data?.results.length ? <Muted>No pages found.</Muted> : null}
                </InlineComposer>
              ) : null}
              {block.links.length ? (
                <LinkRow>
                  {block.links.map((link) => (
                    <LinkChip
                      key={`${block.id}-${link.id}`}
                      onClick={() => onOpenPage(link.id, 'side_peek')}
                      onMouseEnter={() => onPrefetchPage(link.id)}
                      onFocus={() => onPrefetchPage(link.id)}
                    >
                      <PageIdentity page={link} />
                    </LinkChip>
                  ))}
                </LinkRow>
              ) : null}
            </BlockCard>
          </BlockRow>
        );
      })}
    </BlockList>
  );
}

function toDateTimeLocalValue(value: unknown) {
  if (!value) return '';
  const iso = String(value);
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  const pad = (input: number) => String(input).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function fromDateTimeLocalValue(value: string) {
  if (!value) return null;
  return new Date(value).toISOString();
}

function parsePageIdParam(value: string | null | undefined): number | null {
  if (!value) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

export function ProjectsPage() {
  const bootstrapQuery = useWorkspaceBootstrap();
  const workspaceMutations = useWorkspaceMutations();
  const { prefetchWorkspacePage } = useWorkspacePrefetch();
  const trackRecent = useWorkspaceRecentTracker();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const pageMatch = useMatch('/projects/page/:pageId');
  const routePageId = parsePageIdParam(pageMatch?.params.pageId);
  const activePageId = pageMatch?.params.pageId ? routePageId : bootstrapQuery.data?.home_page_id ?? null;
  const activeViewId = parsePositiveNumber(searchParams.get('view'));
  const activeAnchorBlockId = parsePositiveNumber(searchParams.get('block'));
  const peekPageId = parsePageIdParam(searchParams.get('peek'));
  const peekAnchorBlockId = parsePositiveNumber(searchParams.get('peek_block'));
  const rawPeekMode = searchParams.get('peek_mode');
  const peekMode: WorkspaceOpenMode =
    rawPeekMode === 'center_peek' || rawPeekMode === 'full_page' || rawPeekMode === 'side_peek'
      ? rawPeekMode
      : 'side_peek';
  const pageQuery = useWorkspacePage(activePageId);
  const peekQuery = useWorkspacePage(peekPageId);
  const detail = pageQuery.data;
  const peekDetail = peekQuery.data;
  const activeBacklinksQuery = useWorkspaceBacklinks(activePageId, Boolean(detail));
  const peekBacklinksQuery = useWorkspaceBacklinks(
    peekPageId,
    Boolean(peekDetail) && (peekMode === 'side_peek' || peekMode === 'center_peek')
  );
  const templatesQuery = useWorkspaceTemplates(null);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [paletteQuery, setPaletteQuery] = useState('');
  const deferredPaletteQuery = useDeferredValue(paletteQuery);
  const searchQuery = useWorkspaceSearch(deferredPaletteQuery, paletteOpen);
  const [status, setStatus] = useState<Status>(null);
  const [titleDrafts, setTitleDrafts] = useState<Record<number, string>>({});
  const [collapsedSections, setCollapsedSections] = useState({
    favorites: false,
    workspace: false,
    templates: false,
    recent: false,
    trash: false
  });
  const [collapsedPages, setCollapsedPages] = useState<Record<number, boolean>>({});
  const [pageComposer, setPageComposer] = useState<PageComposerState | null>(null);
  const [rowComposer, setRowComposer] = useState<RowComposerState | null>(null);
  const [viewComposer, setViewComposer] = useState<ViewComposerState | null>(null);
  const [chromeEditor, setChromeEditor] = useState<ChromeEditorState | null>(null);
  const [trashQuery, setTrashQuery] = useState('');
  const rowTemplateQuery = useWorkspaceTemplates(rowComposer?.database.id);
  const workspaceTree = useMemo(
    () => buildTree(bootstrapQuery.data?.sidebar_pages ?? []),
    [bootstrapQuery.data?.sidebar_pages]
  );
  const isPeekOpen = Boolean(peekPageId && peekDetail && peekMode === 'side_peek');
  const isCenterPeekOpen = Boolean(peekPageId && peekDetail && peekMode === 'center_peek');
  const needsProjectChoices =
    Boolean(detail?.properties.some((property) => property.property_type === 'relation')) ||
    Boolean(peekDetail?.properties.some((property) => property.property_type === 'relation'));
  const projectsDatabase = bootstrapQuery.data?.databases.find((database) => database.name === 'Projects') ?? null;
  const projectChoicesQuery = useWorkspaceDatabase(
    projectsDatabase?.id ?? null,
    projectsDatabase?.views.find((item) => item.is_default)?.id ?? null,
    needsProjectChoices
  );
  const projectChoices = projectChoicesQuery.data?.rows.map((row) => row.page) ?? [];
  const allTemplates = templatesQuery.data ?? [];
  const rowTemplates = rowTemplateQuery.data ?? [];
  const activePageError =
    pageMatch?.params.pageId && routePageId === null
      ? 'Invalid page link.'
      : pageQuery.error instanceof Error
        ? pageQuery.error.message
        : null;

  useEffect(() => {
    if (detail) {
      setTitleDrafts((current) => ({ ...current, [detail.page.id]: detail.page.title }));
    }
  }, [detail?.page.id, detail?.page.title]);

  useEffect(() => {
    if (peekDetail) {
      setTitleDrafts((current) => ({ ...current, [peekDetail.page.id]: peekDetail.page.title }));
    }
  }, [peekDetail?.page.id, peekDetail?.page.title]);

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        setPaletteOpen(true);
      }
      if (event.key === 'Escape') {
        setPaletteOpen(false);
        if (peekPageId) {
          const next = new URLSearchParams(searchParams);
          next.delete('peek');
          next.delete('peek_mode');
          setSearchParams(next);
        }
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [peekPageId, searchParams, setSearchParams]);

  useEffect(() => {
    if (bootstrapQuery.data?.read_only || !detail || detail.page.id !== activePageId) return;
    trackRecent(detail.page.id);
  }, [activePageId, bootstrapQuery.data?.read_only, detail, trackRecent]);

  useEffect(() => {
    if (bootstrapQuery.data?.read_only || peekPageId === null || !peekDetail || peekDetail.page.id !== peekPageId) return;
    if (!isPeekOpen && !isCenterPeekOpen) return;
    trackRecent(peekDetail.page.id);
  }, [bootstrapQuery.data?.read_only, isCenterPeekOpen, isPeekOpen, peekDetail, peekPageId, trackRecent]);

  useEffect(() => {
    const blockId =
      isPeekOpen || isCenterPeekOpen ? peekAnchorBlockId : activeAnchorBlockId;
    if (!blockId) return;
    const frame = window.requestAnimationFrame(() => {
      const element = document.querySelector<HTMLElement>(`[data-block-id="${blockId}"]`);
      if (!element) return;
      element.scrollIntoView({ block: 'center', behavior: 'smooth' });
      element.animate(
        [
          { backgroundColor: 'rgba(46, 170, 220, 0.18)' },
          { backgroundColor: 'transparent' },
        ],
        { duration: 1400, easing: 'ease-out' }
      );
    });
    return () => window.cancelAnimationFrame(frame);
  }, [activeAnchorBlockId, isCenterPeekOpen, isPeekOpen, peekAnchorBlockId, detail?.page.id, peekDetail?.page.id]);

  const closePeek = () => {
    const next = new URLSearchParams(searchParams);
    next.delete('peek');
    next.delete('peek_mode');
    next.delete('peek_block');
    setSearchParams(next);
  };

  const toggleSection = (section: keyof typeof collapsedSections) =>
    setCollapsedSections((current) => ({ ...current, [section]: !current[section] }));

  const togglePageTree = (pageId: number) =>
    setCollapsedPages((current) => ({ ...current, [pageId]: !current[pageId] }));

  const openPage = (
    pageId: number,
    mode: WorkspaceOpenMode = 'full_page',
    options?: { viewId?: number | null; blockId?: number | null }
  ) => {
    if (mode === 'side_peek' && window.innerWidth <= 1180) {
      mode = 'full_page';
    }
    if (mode === 'center_peek' && window.innerWidth <= 900) {
      mode = 'full_page';
    }
    if (mode !== 'full_page') {
      const next = new URLSearchParams(searchParams);
      next.set('peek', String(pageId));
      next.set('peek_mode', mode);
      if (options?.blockId) next.set('peek_block', String(options.blockId));
      else next.delete('peek_block');
      setSearchParams(next);
      return;
    }
    const next = new URLSearchParams();
    if (options?.viewId) next.set('view', String(options.viewId));
    if (options?.blockId) next.set('block', String(options.blockId));
    const suffix = next.toString() ? `?${next}` : '';
    navigate(pageId === bootstrapQuery.data?.home_page_id ? `/projects${suffix}` : `/projects/page/${pageId}${suffix}`);
  };

  const openDatabaseView = (pageId: number, viewId: number | null) => {
    openPage(pageId, 'full_page', { viewId });
  };

  const openCreatePageDialog = (parentPageId?: number | null) =>
    setPageComposer({
      parentPageId: parentPageId ?? null,
      title: '',
      kind: 'page',
      icon: '',
      dialogTitle: 'Create page',
      submitLabel: 'Create page'
    });

  const openCreateNoteDialog = (parentPageId: number) =>
    setPageComposer({
      parentPageId,
      title: '',
      kind: 'note',
      icon: '📝',
      dialogTitle: 'Create note',
      submitLabel: 'Create note'
    });

  const openCreateRowDialog = (
    database: WorkspaceDatabaseSummary,
    view: WorkspaceView | null,
    initialProperties?: Record<string, unknown>
  ) => {
    const viewConfig = getViewConfig(view);
    const templateId = typeof viewConfig.default_template_id === 'number' ? viewConfig.default_template_id : null;
    const template = getTemplateById(templatesQuery.data, templateId);
    setRowComposer({
      database,
      title: template?.title ?? template?.name ?? '',
      templateId,
      openMode: getOpenMode(view),
      properties: initialProperties ?? {}
    });
  };

  const openCreateViewDialog = (database: WorkspaceDatabaseSummary) => {
    setViewComposer({
      database,
      viewId: null,
      name: '',
      viewType: 'table',
      openMode: 'side_peek',
      groupBy: '',
      dateProperty: '',
      cardPreview: 'icon',
      isDefault: database.views.length === 0,
      hiddenProperties: []
    });
  };

  const openEditViewDialog = (database: WorkspaceDatabaseSummary, view: WorkspaceView | null) => {
    if (!view) return;
    const viewConfig = getViewConfig(view);
    setViewComposer({
      database,
      viewId: view.id,
      name: view.name,
      viewType: view.view_type,
      openMode: getOpenMode(view),
      groupBy: String(viewConfig.group_by ?? ''),
      dateProperty: String(viewConfig.date_property ?? ''),
      cardPreview: getCardPreview(view),
      isDefault: view.is_default,
      hiddenProperties: Array.isArray(viewConfig.hidden_properties)
        ? (viewConfig.hidden_properties as unknown[]).filter((item): item is string => typeof item === 'string')
        : []
    });
  };

  const createPage = async () => {
    if (!pageComposer?.title.trim()) return;
    try {
      const created = await workspaceMutations.createPage({
        title: pageComposer.title.trim(),
        parent_page_id: pageComposer.parentPageId,
        kind: pageComposer.kind,
        icon: pageComposer.icon.trim() || null,
        show_in_sidebar: true
      });
      setPageComposer(null);
      openPage(created.page.id);
    } catch (error) {
      setStatus({ kind: 'error', message: error instanceof Error ? error.message : 'Could not create page.' });
    }
  };

  const createRow = async () => {
    if (!rowComposer) return;
    const selectedTemplate = getTemplateById(rowTemplates, rowComposer.templateId);
    const title = rowComposer.title.trim() || selectedTemplate?.title || selectedTemplate?.name;
    if (!title) return;
    try {
      const created = rowComposer.templateId
        ? await workspaceMutations.applyTemplate({
            templateId: rowComposer.templateId,
            payload: { title, properties: rowComposer.properties }
          })
        : await workspaceMutations.createRow({
            databaseId: rowComposer.database.id,
            payload: { title, properties: rowComposer.properties }
          });
      setRowComposer(null);
      openPage(created.page.id, rowComposer.openMode);
    } catch (error) {
      setStatus({ kind: 'error', message: error instanceof Error ? error.message : 'Could not create row.' });
    }
  };

  const createView = async () => {
    if (!viewComposer?.name.trim()) return;
    const configJson: Record<string, unknown> = {
      open_mode: viewComposer.openMode
    };
    if (viewComposer.groupBy.trim()) configJson.group_by = viewComposer.groupBy.trim();
    if (viewComposer.dateProperty.trim()) configJson.date_property = viewComposer.dateProperty.trim();
    if (viewComposer.cardPreview) configJson.card_preview = viewComposer.cardPreview;
    if (viewComposer.hiddenProperties.length) configJson.hidden_properties = viewComposer.hiddenProperties;
    try {
      if (viewComposer.viewId) {
        await workspaceMutations.updateView({
          viewId: viewComposer.viewId,
          payload: {
            name: viewComposer.name.trim(),
            is_default: viewComposer.isDefault,
            config_json: configJson
          }
        });
      } else {
        await workspaceMutations.createView({
          databaseId: viewComposer.database.id,
          payload: {
            name: viewComposer.name.trim(),
            view_type: viewComposer.viewType.trim() || 'table',
            is_default: viewComposer.isDefault,
            config_json: configJson
          }
        });
      }
      setViewComposer(null);
    } catch (error) {
      setStatus({ kind: 'error', message: error instanceof Error ? error.message : 'Could not create view.' });
    }
  };

  const saveChrome = async () => {
    if (!chromeEditor) return;
    try {
      let coverUrl = chromeEditor.coverUrl.trim() || null;
      if (chromeEditor.coverFile) {
        const asset = await createWorkspaceAssetUpload({
          page_id: chromeEditor.pageId,
          name: chromeEditor.coverFile.name,
          mime_type: chromeEditor.coverFile.type || null,
          size_bytes: chromeEditor.coverFile.size
        });
        await uploadWorkspaceAssetContent(asset.upload_url, chromeEditor.coverFile, asset.headers);
        coverUrl = asset.public_url;
      }
      await workspaceMutations.updatePage({
        pageId: chromeEditor.pageId,
        payload: {
          icon: chromeEditor.icon.trim() || null,
          cover_url: coverUrl
        }
      });
      setChromeEditor(null);
    } catch (error) {
      setStatus({ kind: 'error', message: error instanceof Error ? error.message : 'Could not update page chrome.' });
    }
  };

  const saveTitle = async (pageDetail: WorkspacePageDetail) => {
    if (bootstrapQuery.data?.read_only) return;
    const titleDraft = titleDrafts[pageDetail.page.id] ?? pageDetail.page.title;
    if (!titleDraft.trim() || titleDraft === pageDetail.page.title) return;
    try {
      await workspaceMutations.updatePage({ pageId: pageDetail.page.id, payload: { title: titleDraft.trim() } });
    } catch (error) {
      setStatus({ kind: 'error', message: error instanceof Error ? error.message : 'Could not update title.' });
    }
  };

  const saveProperties = async (pageId: number, values: Record<string, unknown>) => {
    if (bootstrapQuery.data?.read_only) return;
    try {
      await workspaceMutations.updateProperties({ pageId, values });
    } catch (error) {
      setStatus({ kind: 'error', message: error instanceof Error ? error.message : 'Could not update properties.' });
    }
  };

  const saveBlock = async (
    blockId: number,
    payload: { block_type?: string; text_content?: string; checked?: boolean; data_json?: Record<string, unknown> | unknown[] | null }
  ) => {
    if (bootstrapQuery.data?.read_only) return;
    try {
      await workspaceMutations.updateBlock({ blockId, payload });
    } catch (error) {
      setStatus({ kind: 'error', message: error instanceof Error ? error.message : 'Could not update block.' });
    }
  };

  const createBlock = async (pageId: number, afterBlockId?: number | null, type = 'paragraph') => {
    if (bootstrapQuery.data?.read_only) return;
    try {
      await workspaceMutations.createBlock({
        page_id: pageId,
        after_block_id: afterBlockId ?? null,
        block_type: type,
        text_content: ''
      });
    } catch (error) {
      setStatus({ kind: 'error', message: error instanceof Error ? error.message : 'Could not create block.' });
    }
  };

  const createBlockWithPayload = async (
    pageId: number,
    afterBlockId?: number | null,
    type = 'paragraph',
    payload?: { text_content?: string; checked?: boolean; data_json?: Record<string, unknown> | unknown[] | null }
  ) => {
    if (bootstrapQuery.data?.read_only) return;
    try {
      await workspaceMutations.createBlock({
        page_id: pageId,
        after_block_id: afterBlockId ?? null,
        block_type: type,
        text_content: payload?.text_content ?? '',
        checked: payload?.checked ?? false,
        data_json: payload?.data_json ?? null
      });
    } catch (error) {
      setStatus({ kind: 'error', message: error instanceof Error ? error.message : 'Could not create block.' });
    }
  };

  const deleteBlock = async (blockId: number) => {
    if (bootstrapQuery.data?.read_only) return;
    try {
      await workspaceMutations.deleteBlock(blockId);
    } catch (error) {
      setStatus({ kind: 'error', message: error instanceof Error ? error.message : 'Could not delete block.' });
    }
  };

  const reorderBlocks = async (pageId: number, orderedBlockIds: number[]) => {
    if (bootstrapQuery.data?.read_only) return;
    try {
      await workspaceMutations.reorderBlocks({ page_id: pageId, ordered_block_ids: orderedBlockIds });
    } catch (error) {
      setStatus({ kind: 'error', message: error instanceof Error ? error.message : 'Could not reorder blocks.' });
    }
  };

  const createChildPageBlock = async (block: WorkspaceBlock, title?: string) => {
    if (bootstrapQuery.data?.read_only) return;
    try {
      const created = await workspaceMutations.createPage({
        title: title?.trim() || 'Untitled page',
        parent_page_id: block.page_id,
        kind: 'page',
        show_in_sidebar: true
      });
      await saveBlock(block.id, {
        block_type: 'child_page',
        text_content: created.page.title,
        data_json: {
          page_id: created.page.id,
          icon: created.page.icon ?? '📄'
        }
      });
    } catch (error) {
      setStatus({ kind: 'error', message: error instanceof Error ? error.message : 'Could not create child page.' });
    }
  };

  const renderSidebarTree = (parentId: number | null, depth = 0): JSX.Element[] =>
    (workspaceTree.get(parentId) ?? []).map((page) => (
      <div key={page.id}>
        <TreeRow $depth={depth}>
          {(workspaceTree.get(page.id)?.length ?? 0) > 0 ? (
            <TreeDisclosure type="button" onClick={() => togglePageTree(page.id)}>
              {collapsedPages[page.id] ? '▸' : '▾'}
            </TreeDisclosure>
          ) : (
            <span />
          )}
          <SidebarButton
            $active={activePageId === page.id}
            onClick={() => openPage(page.id, 'full_page', page.kind === 'database' ? { viewId: activePageId === page.id ? activeViewId : null } : undefined)}
            onMouseEnter={() => void prefetchWorkspacePage(page.id)}
            onFocus={() => void prefetchWorkspacePage(page.id)}
          >
            <PageIdentity page={page} />
            {page.kind === 'database' ? <SidebarMeta>DB</SidebarMeta> : null}
          </SidebarButton>
        </TreeRow>
        {!collapsedPages[page.id] && page.kind === 'database'
          ? (bootstrapQuery.data?.databases.find((database) => database.page_id === page.id)?.views ?? []).map((view) => (
              <TreeRow key={view.id} $depth={depth + 1}>
                <span />
                <SidebarButton
                  $active={activePageId === page.id && activeViewId === view.id}
                  $indented
                  onClick={() => openDatabaseView(page.id, view.id)}
                >
                  <span>↳</span>
                  <span>{view.name}</span>
                </SidebarButton>
              </TreeRow>
            ))
          : null}
        {!collapsedPages[page.id] ? renderSidebarTree(page.id, depth + 1) : null}
      </div>
    ));

  const renderCanvas = (pageDetail: WorkspacePageDetail | undefined, compact = false) => {
    if (!pageDetail) return <Muted>Loading page…</Muted>;
    const backlinksQuery =
      pageDetail.page.id === detail?.page.id ? activeBacklinksQuery : pageDetail.page.id === peekDetail?.page.id ? peekBacklinksQuery : null;
    const backlinks = backlinksQuery?.data?.backlinks ?? [];
    const titleDraft = titleDrafts[pageDetail.page.id] ?? pageDetail.page.title;
    const isProjectPage =
      pageDetail.page.kind === 'database_row' && pageDetail.database?.name === 'Projects';
    const noteChildren = isProjectPage
      ? pageDetail.children.filter((child) => child.kind === 'note')
      : [];
    const otherChildren = isProjectPage
      ? pageDetail.children.filter((child) => child.kind !== 'note')
      : pageDetail.children;
    return (
      <CanvasInner style={compact ? { width: 'calc(100% - 28px)', paddingTop: 16 } : undefined}>
        {pageDetail.page.cover_url ? <Cover $url={pageDetail.page.cover_url} /> : null}
        <PageHeader>
          <Breadcrumbs>
            {pageDetail.breadcrumbs.map((item) => (
              <CrumbButton
                key={item.id}
                onClick={() => openPage(item.id)}
                onMouseEnter={() => void prefetchWorkspacePage(item.id)}
                onFocus={() => void prefetchWorkspacePage(item.id)}
              >
                <PageTitleText page={item} /> /
              </CrumbButton>
            ))}
            <span>{pageDetail.page.title}</span>
          </Breadcrumbs>
          <TitleRow>
            <IconButton
              type="button"
              disabled={bootstrapQuery.data?.read_only}
              onClick={() =>
                setChromeEditor({
                  pageId: pageDetail.page.id,
                  icon: pageDetail.page.icon ?? '',
                  coverUrl: pageDetail.page.cover_url ?? '',
                  coverFile: null
                })
              }
            >
              {pageDetail.page.icon ?? '📄'}
            </IconButton>
            <PageTitleInput
              value={titleDraft}
              readOnly={bootstrapQuery.data?.read_only}
              onChange={(event) =>
                setTitleDrafts((current) => ({ ...current, [pageDetail.page.id]: event.target.value }))
              }
              onBlur={() => void saveTitle(pageDetail)}
            />
          </TitleRow>
          <MetaRow>
            <MetaPill>{pageDetail.page.kind.replace('_', ' ')}</MetaPill>
            {pageDetail.page.kind === 'database' && pageDetail.database ? (
              <MetaPill>{pageDetail.database.views.length} views</MetaPill>
            ) : null}
            {pageDetail.page.trashed_at ? <MetaPill>In trash</MetaPill> : null}
            {backlinks.length ? <MetaPill>{backlinks.length} backlinks</MetaPill> : null}
            <PillButton
              type="button"
              disabled={bootstrapQuery.data?.read_only}
              onClick={async () => {
                if (!pageDetail) return;
                await workspaceMutations.updatePage({
                  pageId: pageDetail.page.id,
                  payload: { favorite: !pageDetail.favorite }
                });
              }}
            >
              {pageDetail.favorite ? '★ Favorited' : '☆ Favorite'}
            </PillButton>
            {!bootstrapQuery.data?.read_only ? (
              <>
                <PillButton
                  type="button"
                  onClick={() =>
                    setChromeEditor({
                      pageId: pageDetail.page.id,
                      icon: pageDetail.page.icon ?? '',
                      coverUrl: pageDetail.page.cover_url ?? '',
                      coverFile: null
                    })
                  }
                >
                  Edit chrome
                </PillButton>
                {pageDetail.page.trashed_at ? (
                  <>
                    <PillButton
                      type="button"
                      onClick={async () => {
                        try {
                          await workspaceMutations.updatePage({
                            pageId: pageDetail.page.id,
                            payload: { trashed: false }
                          });
                          setStatus({ kind: 'info', message: 'Page restored from trash.' });
                        } catch (error) {
                          setStatus({
                            kind: 'error',
                            message: error instanceof Error ? error.message : 'Could not restore page.'
                          });
                        }
                      }}
                    >
                      Restore
                    </PillButton>
                    <PillButton
                      type="button"
                      onClick={async () => {
                        try {
                          await workspaceMutations.deletePage(pageDetail.page.id);
                          setStatus({ kind: 'info', message: 'Page permanently deleted.' });
                          navigate('/projects');
                        } catch (error) {
                          setStatus({
                            kind: 'error',
                            message: error instanceof Error ? error.message : 'Could not permanently delete page.'
                          });
                        }
                      }}
                    >
                      Delete forever
                    </PillButton>
                  </>
                ) : (
                  <PillButton
                    type="button"
                    onClick={async () => {
                      try {
                        await workspaceMutations.updatePage({
                          pageId: pageDetail.page.id,
                          payload: { trashed: true }
                        });
                        setStatus({ kind: 'info', message: 'Page moved to trash.' });
                        navigate('/projects');
                      } catch (error) {
                        setStatus({
                          kind: 'error',
                          message: error instanceof Error ? error.message : 'Could not move page to trash.'
                        });
                      }
                    }}
                  >
                    Move to trash
                  </PillButton>
                )}
              </>
            ) : null}
          </MetaRow>
        </PageHeader>

        {pageDetail.page.kind === 'database_row' ? (
          <PageProperties
            detail={pageDetail}
            readOnly={Boolean(bootstrapQuery.data?.read_only)}
            relationChoices={projectChoices}
            onSave={(values) => saveProperties(pageDetail.page.id, values)}
          />
        ) : null}

        {pageDetail.page.kind === 'database' && pageDetail.database ? (
          <DatabaseView
            database={pageDetail.database}
            initialViewId={pageDetail.page.id === activePageId ? activeViewId : null}
            readOnly={Boolean(bootstrapQuery.data?.read_only)}
            onOpenPage={openPage}
            onPrefetchPage={(pageId) => void prefetchWorkspacePage(pageId)}
            onCreateRow={openCreateRowDialog}
            onCreateView={openCreateViewDialog}
            onEditView={openEditViewDialog}
            onViewChange={(viewId) => openDatabaseView(pageDetail.page.id, viewId)}
          />
        ) : null}

        <BlocksSection
          detail={pageDetail}
          bootstrap={bootstrapQuery.data}
          readOnly={Boolean(bootstrapQuery.data?.read_only)}
          onOpenPage={openPage}
          onPrefetchPage={(pageId) => void prefetchWorkspacePage(pageId)}
          onCreateBlock={createBlockWithPayload}
          onCreateChildPageBlock={createChildPageBlock}
          onCreateRow={openCreateRowDialog}
          onCreateView={openCreateViewDialog}
          onEditView={openEditViewDialog}
          onUpdateBlock={saveBlock}
          onDeleteBlock={deleteBlock}
          onReorderBlocks={reorderBlocks}
        />

        {!bootstrapQuery.data?.read_only ? (
          <PillButton type="button" onClick={() => void createBlock(pageDetail.page.id, pageDetail.blocks.at(-1)?.id ?? null)}>
            + Add block
          </PillButton>
        ) : null}

        {isProjectPage ? (
          <ChildPages>
            <MetaRow style={{ justifyContent: 'space-between', alignItems: 'center' }}>
              <SectionTitle>Notes</SectionTitle>
              {!bootstrapQuery.data?.read_only ? (
                <PillButton type="button" onClick={() => openCreateNoteDialog(pageDetail.page.id)}>
                  New note
                </PillButton>
              ) : null}
            </MetaRow>
            {noteChildren.length ? (
              <ChildGrid>
                {noteChildren.map((child) => (
                  <ChildCard
                    key={child.id}
                    onClick={() => openPage(child.id)}
                    onMouseEnter={() => void prefetchWorkspacePage(child.id)}
                    onFocus={() => void prefetchWorkspacePage(child.id)}
                  >
                    <strong><PageIdentity page={child} /></strong>
                    <ChildDescription>{child.description || 'Note'}</ChildDescription>
                  </ChildCard>
                ))}
              </ChildGrid>
            ) : (
              <Muted>No notes yet.</Muted>
            )}
          </ChildPages>
        ) : null}

        {otherChildren.length ? (
          <ChildPages>
            <SectionTitle>{isProjectPage ? 'Child Pages' : 'Child Pages'}</SectionTitle>
            <ChildGrid>
              {otherChildren.map((child) => (
                <ChildCard
                  key={child.id}
                  onClick={() => openPage(child.id)}
                  onMouseEnter={() => void prefetchWorkspacePage(child.id)}
                  onFocus={() => void prefetchWorkspacePage(child.id)}
                >
                  <strong><PageIdentity page={child} /></strong>
                  <ChildDescription>{child.description || child.kind}</ChildDescription>
                </ChildCard>
              ))}
            </ChildGrid>
          </ChildPages>
        ) : null}

        {backlinksQuery?.isLoading ? <Muted>Loading backlinks…</Muted> : null}

        {backlinks.length ? (
          <ChildPages>
            <SectionTitle>Backlinks</SectionTitle>
            <ListView>
              {backlinks.map((backlink) => (
                <ListRow
                  key={`${backlink.source_page.id}-${backlink.block_id}`}
                  onClick={() => openPage(backlink.source_page.id, 'side_peek', { blockId: backlink.block_id })}
                  onMouseEnter={() => void prefetchWorkspacePage(backlink.source_page.id)}
                  onFocus={() => void prefetchWorkspacePage(backlink.source_page.id)}
                >
                  <strong><PageIdentity page={backlink.source_page} /></strong>
                  <Muted>{backlink.snippet || 'Referenced from this page'}</Muted>
                </ListRow>
              ))}
            </ListView>
          </ChildPages>
        ) : null}
      </CanvasInner>
    );
  };

  return (
    <Root>
      <Shell $peekOpen={isPeekOpen}>
        <Sidebar>
          <SidebarHeader>
            <WorkspaceTitle>Projects Workspace</WorkspaceTitle>
            <SidebarActions>
              <PillButton type="button" onClick={() => setPaletteOpen(true)}>
                Search
              </PillButton>
              {!bootstrapQuery.data?.read_only ? (
                <PillButton type="button" onClick={() => openCreatePageDialog(null)}>
                  New page
                </PillButton>
              ) : null}
            </SidebarActions>
          </SidebarHeader>

          <SidebarSection>
            <SectionHeader type="button" onClick={() => toggleSection('favorites')}>
              <SectionTitle>Favorites</SectionTitle>
              <SidebarMeta>{collapsedSections.favorites ? 'Show' : 'Hide'}</SidebarMeta>
            </SectionHeader>
            {!collapsedSections.favorites
              ? (bootstrapQuery.data?.favorites ?? []).map((page) => (
                  <SidebarButton
                    key={page.id}
                    $active={activePageId === page.id}
                    onClick={() => openPage(page.id)}
                    onMouseEnter={() => void prefetchWorkspacePage(page.id)}
                    onFocus={() => void prefetchWorkspacePage(page.id)}
                  >
                    <PageIdentity page={page} />
                  </SidebarButton>
                ))
              : null}
          </SidebarSection>

          <SidebarSection>
            <SectionHeader type="button" onClick={() => toggleSection('workspace')}>
              <SectionTitle>Workspace</SectionTitle>
              <SidebarMeta>{collapsedSections.workspace ? 'Show' : 'Hide'}</SidebarMeta>
            </SectionHeader>
            {!collapsedSections.workspace ? renderSidebarTree(null) : null}
          </SidebarSection>

          {allTemplates.length ? (
            <SidebarSection>
              <SectionHeader type="button" onClick={() => toggleSection('templates')}>
                <SectionTitle>Templates</SectionTitle>
                <SidebarMeta>{collapsedSections.templates ? 'Show' : 'Hide'}</SidebarMeta>
              </SectionHeader>
              {!collapsedSections.templates
                ? allTemplates.map((template) => (
                    <SidebarButton
                      key={template.id}
                      onClick={() => {
                        if (bootstrapQuery.data?.read_only) return;
                        const database = bootstrapQuery.data?.databases.find((item) => item.id === template.database_id);
                        if (!database) return;
                        setRowComposer({
                          database,
                          title: template.title ?? template.name,
                          templateId: template.id,
                          openMode: getOpenMode(database.views.find((item) => item.is_default) ?? database.views[0] ?? null),
                          properties: {}
                        });
                      }}
                    >
                      <span>{template.icon ?? '🧩'}</span>
                      <span>{template.name}</span>
                      <SidebarMeta>{bootstrapQuery.data?.databases.find((item) => item.id === template.database_id)?.name ?? 'Template'}</SidebarMeta>
                    </SidebarButton>
                  ))
                : null}
            </SidebarSection>
          ) : null}

          <SidebarSection>
            <SectionHeader type="button" onClick={() => toggleSection('recent')}>
              <SectionTitle>Recent</SectionTitle>
              <SidebarMeta>{collapsedSections.recent ? 'Show' : 'Hide'}</SidebarMeta>
            </SectionHeader>
            {!collapsedSections.recent
              ? (bootstrapQuery.data?.recent_pages ?? []).map((page) => (
                  <SidebarButton
                    key={page.id}
                    onClick={() => openPage(page.id)}
                    onMouseEnter={() => void prefetchWorkspacePage(page.id)}
                    onFocus={() => void prefetchWorkspacePage(page.id)}
                  >
                    <PageIdentity page={page} />
                  </SidebarButton>
                ))
              : null}
          </SidebarSection>

          {(bootstrapQuery.data?.trash_pages.length ?? 0) > 0 ? (
            <SidebarSection>
              <SectionHeader type="button" onClick={() => toggleSection('trash')}>
                <SectionTitle>Trash</SectionTitle>
                <SidebarMeta>{collapsedSections.trash ? 'Show' : 'Hide'}</SidebarMeta>
              </SectionHeader>
              {!collapsedSections.trash ? (
                <>
                  <PropertyInput
                    value={trashQuery}
                    placeholder="Search trash…"
                    onChange={(event) => setTrashQuery(event.target.value)}
                  />
                  {bootstrapQuery.data?.trash_pages
                    .filter((page) => page.title.toLowerCase().includes(trashQuery.trim().toLowerCase()))
                    .map((page) => (
                    <SidebarButton
                      key={page.id}
                      onClick={() => openPage(page.id)}
                      onMouseEnter={() => void prefetchWorkspacePage(page.id)}
                      onFocus={() => void prefetchWorkspacePage(page.id)}
                    >
                      <span>🗑️</span>
                      <PageTitleText page={page} />
                    </SidebarButton>
                    ))}
                </>
              ) : null}
            </SidebarSection>
          ) : null}
        </Sidebar>

        <Main>
          <Topbar>
            <TopbarLeft>
              <SearchInput
                value={paletteQuery}
                placeholder="Search or jump to a page…"
                onFocus={() => setPaletteOpen(true)}
                onChange={(event) => {
                  setPaletteQuery(event.target.value);
                  if (!paletteOpen) setPaletteOpen(true);
                }}
              />
              <MobileActions>
                <PillButton type="button" onClick={() => navigate('/projects')}>
                  Home
                </PillButton>
              </MobileActions>
            </TopbarLeft>
            <MetaRow>
              {bootstrapQuery.data?.read_only ? <MetaPill>Guest mode: read only</MetaPill> : null}
              {!bootstrapQuery.data?.read_only && detail ? (
                <PillButton type="button" onClick={() => openCreatePageDialog(detail.page.id)}>
                  New subpage
                </PillButton>
              ) : null}
            </MetaRow>
          </Topbar>

          {status ? <StatusBar $kind={status.kind}>{status.message}</StatusBar> : null}

          <Canvas>
            {activePageError ? (
              <CanvasInner>
                <StatusBar $kind="error">{activePageError}</StatusBar>
                <PillButton type="button" onClick={() => navigate('/projects')}>
                  Go to Home
                </PillButton>
              </CanvasInner>
            ) : (
              renderCanvas(detail)
            )}
          </Canvas>
        </Main>

        <PeekPanel $open={isPeekOpen}>
          {peekDetail ? (
            <>
              <PeekHeader>
                <strong>{peekDetail.page.title}</strong>
                <PillButton type="button" onClick={closePeek}>Close</PillButton>
              </PeekHeader>
              <Canvas>{renderCanvas(peekDetail, true)}</Canvas>
            </>
          ) : null}
        </PeekPanel>
      </Shell>

      {isCenterPeekOpen && peekDetail ? (
        <Overlay onClick={closePeek}>
          <CenterPeekCard onClick={(event) => event.stopPropagation()}>
            <PeekHeader>
              <strong>{peekDetail.page.title}</strong>
              <PillButton type="button" onClick={closePeek}>Close</PillButton>
            </PeekHeader>
            <Canvas>{renderCanvas(peekDetail, true)}</Canvas>
          </CenterPeekCard>
        </Overlay>
      ) : null}

      {pageComposer ? (
        <Overlay onClick={() => setPageComposer(null)}>
          <DialogCard onClick={(event) => event.stopPropagation()}>
            <DialogBody
              onSubmit={(event) => {
                event.preventDefault();
                void createPage();
              }}
            >
              <DialogTitle>{pageComposer.dialogTitle}</DialogTitle>
              <FieldGrid>
                <FieldLabel>
                  Title
                  <PropertyInput
                    autoFocus
                    value={pageComposer.title}
                    onChange={(event) => setPageComposer((current) => (current ? { ...current, title: event.target.value } : current))}
                  />
                </FieldLabel>
                <FieldLabel>
                  Icon
                  <PropertyInput
                    value={pageComposer.icon}
                    placeholder="📄"
                    onChange={(event) => setPageComposer((current) => (current ? { ...current, icon: event.target.value } : current))}
                  />
                </FieldLabel>
              </FieldGrid>
              <DialogActions>
                <PillButton type="button" onClick={() => setPageComposer(null)}>
                  Cancel
                </PillButton>
                <PillButton type="submit">{pageComposer.submitLabel}</PillButton>
              </DialogActions>
            </DialogBody>
          </DialogCard>
        </Overlay>
      ) : null}

      {rowComposer ? (
        <Overlay onClick={() => setRowComposer(null)}>
          <DialogCard onClick={(event) => event.stopPropagation()}>
            <DialogBody
              onSubmit={(event) => {
                event.preventDefault();
                void createRow();
              }}
            >
              <DialogTitle>Create {rowComposer.database.name.slice(0, -1) || 'row'}</DialogTitle>
              <FieldGrid>
                <FieldLabel>
                  Template
                  <PropertySelect
                    value={String(rowComposer.templateId ?? '')}
                    onChange={(event) => {
                      const templateId = event.target.value ? Number(event.target.value) : null;
                      const template = getTemplateById(rowTemplates, templateId);
                      setRowComposer((current) =>
                        current
                          ? {
                              ...current,
                              templateId,
                              title: template?.title ?? template?.name ?? current.title
                            }
                          : current
                      );
                    }}
                  >
                    <option value="">Blank</option>
                    {rowTemplates.map((template) => (
                      <option key={template.id} value={template.id}>
                        {template.name}
                      </option>
                    ))}
                  </PropertySelect>
                  <FieldHint>Templates apply starter blocks and default properties.</FieldHint>
                </FieldLabel>
                <FieldLabel>
                  Title
                  <PropertyInput
                    autoFocus
                    value={rowComposer.title}
                    onChange={(event) => setRowComposer((current) => (current ? { ...current, title: event.target.value } : current))}
                  />
                </FieldLabel>
                <FieldLabel>
                  Open mode
                  <PropertySelect
                    value={rowComposer.openMode}
                    onChange={(event) =>
                      setRowComposer((current) =>
                        current ? { ...current, openMode: event.target.value as WorkspaceOpenMode } : current
                      )
                    }
                  >
                    <option value="side_peek">Side peek</option>
                    <option value="center_peek">Center peek</option>
                    <option value="full_page">Full page</option>
                  </PropertySelect>
                </FieldLabel>
              </FieldGrid>
              <DialogActions>
                <PillButton type="button" onClick={() => setRowComposer(null)}>
                  Cancel
                </PillButton>
                <PillButton type="submit">Create row</PillButton>
              </DialogActions>
            </DialogBody>
          </DialogCard>
        </Overlay>
      ) : null}

      {viewComposer ? (
        <Overlay onClick={() => setViewComposer(null)}>
          <DialogCard onClick={(event) => event.stopPropagation()}>
            <DialogBody
              onSubmit={(event) => {
                event.preventDefault();
                void createView();
              }}
            >
              <DialogTitle>{viewComposer.viewId ? 'Edit view' : 'Create view'}</DialogTitle>
              <FieldGrid>
                <FieldLabel>
                  Name
                  <PropertyInput
                    autoFocus
                    value={viewComposer.name}
                    onChange={(event) => setViewComposer((current) => (current ? { ...current, name: event.target.value } : current))}
                  />
                </FieldLabel>
                <FieldLabel>
                  View type
                  <PropertySelect
                    value={viewComposer.viewType}
                    disabled={Boolean(viewComposer.viewId)}
                    onChange={(event) =>
                      setViewComposer((current) => (current ? { ...current, viewType: event.target.value } : current))
                    }
                  >
                    <option value="table">Table</option>
                    <option value="list">List</option>
                    <option value="board">Board</option>
                    <option value="calendar">Calendar</option>
                    <option value="timeline">Timeline</option>
                    <option value="gallery">Gallery</option>
                  </PropertySelect>
                </FieldLabel>
                <FieldLabel>
                  Open mode
                  <PropertySelect
                    value={viewComposer.openMode}
                    onChange={(event) =>
                      setViewComposer((current) =>
                        current ? { ...current, openMode: event.target.value as WorkspaceOpenMode } : current
                      )
                    }
                  >
                    <option value="side_peek">Side peek</option>
                    <option value="center_peek">Center peek</option>
                    <option value="full_page">Full page</option>
                  </PropertySelect>
                </FieldLabel>
                <FieldLabel>
                  Group by
                  <PropertySelect
                    value={viewComposer.groupBy}
                    onChange={(event) =>
                      setViewComposer((current) => (current ? { ...current, groupBy: event.target.value } : current))
                    }
                  >
                    <option value="">None</option>
                    {viewComposer.database.properties.map((property) => (
                      <option key={property.id} value={property.slug}>
                        {property.name}
                      </option>
                    ))}
                  </PropertySelect>
                </FieldLabel>
                <FieldLabel>
                  Date property
                  <PropertySelect
                    value={viewComposer.dateProperty}
                    onChange={(event) =>
                      setViewComposer((current) => (current ? { ...current, dateProperty: event.target.value } : current))
                    }
                  >
                    <option value="">None</option>
                    {viewComposer.database.properties
                      .filter((property) => property.property_type === 'date')
                      .map((property) => (
                        <option key={property.id} value={property.slug}>
                          {property.name}
                        </option>
                      ))}
                  </PropertySelect>
                </FieldLabel>
                <FieldLabel>
                  Card preview
                  <PropertySelect
                    value={viewComposer.cardPreview}
                    onChange={(event) =>
                      setViewComposer((current) =>
                        current ? { ...current, cardPreview: event.target.value as CardPreviewMode } : current
                      )
                    }
                  >
                    <option value="icon">Icon</option>
                    <option value="cover">Cover</option>
                    <option value="none">None</option>
                  </PropertySelect>
                </FieldLabel>
                <FieldLabel>
                  Hidden properties
                  <PropertyInput
                    value={viewComposer.hiddenProperties.join(', ')}
                    placeholder="status, due"
                    onChange={(event) =>
                      setViewComposer((current) =>
                        current
                          ? {
                              ...current,
                              hiddenProperties: event.target.value
                                .split(',')
                                .map((item) => item.trim())
                                .filter(Boolean)
                            }
                          : current
                      )
                    }
                  />
                  <FieldHint>Use property slugs to hide columns/cards in this view.</FieldHint>
                </FieldLabel>
                <FieldLabel>
                  <MetaRow>
                    <Toggle
                      type="checkbox"
                      checked={viewComposer.isDefault}
                      onChange={(event) =>
                        setViewComposer((current) => (current ? { ...current, isDefault: event.target.checked } : current))
                      }
                    />
                    <span>Set as default view</span>
                  </MetaRow>
                </FieldLabel>
              </FieldGrid>
              <DialogActions>
                <PillButton type="button" onClick={() => setViewComposer(null)}>
                  Cancel
                </PillButton>
                <PillButton type="submit">{viewComposer.viewId ? 'Save view' : 'Create view'}</PillButton>
              </DialogActions>
            </DialogBody>
          </DialogCard>
        </Overlay>
      ) : null}

      {chromeEditor ? (
        <Overlay onClick={() => setChromeEditor(null)}>
          <DialogCard onClick={(event) => event.stopPropagation()}>
            <DialogBody
              onSubmit={(event) => {
                event.preventDefault();
                void saveChrome();
              }}
            >
              <DialogTitle>Edit page chrome</DialogTitle>
              <FieldGrid>
                <FieldLabel>
                  Icon
                  <PropertyInput
                    autoFocus
                    value={chromeEditor.icon}
                    placeholder="📄"
                    onChange={(event) => setChromeEditor((current) => (current ? { ...current, icon: event.target.value } : current))}
                  />
                </FieldLabel>
                <FieldLabel>
                  Cover URL
                  <PropertyInput
                    value={chromeEditor.coverUrl}
                    placeholder="https://…"
                    onChange={(event) =>
                      setChromeEditor((current) => (current ? { ...current, coverUrl: event.target.value } : current))
                    }
                  />
                  <FieldHint>Paste a URL or upload a file. Save applies the uploaded file first.</FieldHint>
                </FieldLabel>
                <FieldLabel>
                  Upload cover
                  <PropertyInput
                    type="file"
                    accept="image/*"
                    onChange={(event) =>
                      setChromeEditor((current) =>
                        current ? { ...current, coverFile: event.target.files?.[0] ?? null } : current
                      )
                    }
                  />
                </FieldLabel>
              </FieldGrid>
              <DialogActions>
                <PillButton type="button" onClick={() => setChromeEditor(null)}>
                  Cancel
                </PillButton>
                <PillButton type="submit">Save</PillButton>
              </DialogActions>
            </DialogBody>
          </DialogCard>
        </Overlay>
      ) : null}

      {paletteOpen ? (
        <Overlay onClick={() => setPaletteOpen(false)}>
          <Palette onClick={(event) => event.stopPropagation()}>
            <Topbar>
              <TopbarLeft>
                <SearchInput
                  autoFocus
                  value={paletteQuery}
                  placeholder="Search pages or type a title to create one…"
                  onChange={(event) => setPaletteQuery(event.target.value)}
                />
              </TopbarLeft>
              {!bootstrapQuery.data?.read_only ? (
                <PillButton
                  type="button"
                  onClick={async () => {
                    if (!paletteQuery.trim()) return;
                    try {
                      const created = await workspaceMutations.createPage({
                        title: paletteQuery.trim(),
                        kind: 'page',
                        show_in_sidebar: true
                      });
                      setPaletteOpen(false);
                      setPaletteQuery('');
                      openPage(created.page.id);
                    } catch (error) {
                      setStatus({ kind: 'error', message: error instanceof Error ? error.message : 'Could not create page.' });
                    }
                  }}
                >
                  Create page
                </PillButton>
              ) : null}
            </Topbar>
            <PaletteResults>
              {searchQuery.isLoading ? <PaletteButton as="div">Searching…</PaletteButton> : null}
              {!searchQuery.isLoading && !paletteQuery.trim() ? (
                <PaletteButton as="div">Type to search pages or create one.</PaletteButton>
              ) : null}
              {!searchQuery.isLoading && Boolean(paletteQuery.trim()) && (searchQuery.data?.results.length ?? 0) === 0 ? (
                <PaletteButton as="div">No matching pages.</PaletteButton>
              ) : null}
              {searchQuery.data?.results.map((result) => (
                <PaletteButton
                  key={result.page.id}
                  onClick={() => {
                    setPaletteOpen(false);
                    openPage(result.page.id);
                  }}
                  onMouseEnter={() => void prefetchWorkspacePage(result.page.id)}
                  onFocus={() => void prefetchWorkspacePage(result.page.id)}
                >
                  <strong><PageIdentity page={result.page} /></strong>
                  <Muted>{result.match || result.page.kind}</Muted>
                </PaletteButton>
              ))}
            </PaletteResults>
          </Palette>
        </Overlay>
      ) : null}
    </Root>
  );
}
