import { useState } from 'react';
import styled from 'styled-components';

import { Card } from '../components/common/Card';
import { useAIDigest } from '../hooks/useAIDigest';
import type { DigestItem } from '../services/api';
import { fadeUp, reducedMotion } from '../styles/animations';

/* ─── Category config ─────────────────────────── */

const CATEGORY_COLORS: Record<string, string> = {
  'claude-anthropic': 'rgba(217, 119, 87, 0.85)',
  'openai': 'rgba(116, 184, 134, 0.85)',
  'developer-tools': 'rgba(120, 180, 255, 0.85)',
  'aggregator': 'rgba(180, 160, 220, 0.85)',
  'analysis': 'rgba(220, 180, 120, 0.85)',
  'google-ai': 'rgba(130, 200, 220, 0.85)',
  'open-source': 'rgba(180, 220, 140, 0.85)',
  'frameworks': 'rgba(200, 160, 180, 0.85)',
  'research': 'rgba(160, 190, 220, 0.85)',
  'industry': 'rgba(180, 180, 160, 0.85)',
};

const CATEGORY_LABELS: Record<string, string> = {
  'claude-anthropic': 'Claude & Anthropic',
  'openai': 'OpenAI',
  'developer-tools': 'Dev Tools',
  'aggregator': 'Aggregator',
  'analysis': 'Analysis',
  'google-ai': 'Google AI',
  'open-source': 'Open Source',
  'frameworks': 'Frameworks',
  'research': 'Research',
  'industry': 'Industry',
};

const CATEGORY_ORDER: string[] = [
  'claude-anthropic', 'openai', 'google-ai', 'developer-tools',
  'open-source', 'frameworks', 'aggregator', 'analysis', 'research', 'industry',
];

/* ─── Data helpers ────────────────────────────── */

const COLLAPSE_KEY = 'ld_ai_digest_collapsed';

function loadCollapsed(): Set<string> {
  try {
    const raw = localStorage.getItem(COLLAPSE_KEY);
    return raw ? new Set(JSON.parse(raw)) : new Set();
  } catch { return new Set(); }
}

function saveCollapsed(s: Set<string>): void {
  localStorage.setItem(COLLAPSE_KEY, JSON.stringify([...s]));
}

function extractTopStories(items: DigestItem[], max = 5): { top: DigestItem[]; rest: DigestItem[] } {
  const seen = new Set<number>();
  const top: DigestItem[] = [];
  const byCat: Record<string, DigestItem[]> = {};

  for (const item of items) {
    const cat = item.category || 'industry';
    if (!byCat[cat]) byCat[cat] = [];
    byCat[cat].push(item);
  }

  for (const cat of CATEGORY_ORDER) {
    if (top.length >= max) break;
    const catItems = byCat[cat];
    if (catItems?.length) {
      top.push(catItems[0]);
      seen.add(catItems[0].id);
    }
  }

  return { top, rest: items.filter(i => !seen.has(i.id)) };
}

function groupByCategory(items: DigestItem[]): [string, DigestItem[]][] {
  const groups: Record<string, DigestItem[]> = {};
  for (const item of items) {
    const cat = item.category || 'industry';
    if (!groups[cat]) groups[cat] = [];
    groups[cat].push(item);
  }
  return CATEGORY_ORDER
    .filter(cat => groups[cat]?.length)
    .map(cat => [cat, groups[cat]]);
}

function formatTimeAgo(dateStr: string | null): string {
  if (!dateStr) return '';
  const diff = Date.now() - new Date(dateStr).getTime();
  const hours = Math.floor(diff / (1000 * 60 * 60));
  if (hours < 1) return 'just now';
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days === 1) return 'yesterday';
  return `${days}d ago`;
}

function formatDate(): string {
  return new Date().toLocaleDateString('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
  });
}

function getColor(cat: string | null): string {
  return CATEGORY_COLORS[cat || ''] || 'rgba(160, 160, 160, 0.7)';
}

function getLabel(cat: string | null): string {
  return CATEGORY_LABELS[cat || ''] || cat || 'General';
}

/* ─── Styled: Layout ──────────────────────────── */

const Page = styled.div`
  display: flex;
  flex-direction: column;
  gap: clamp(20px, 4vw, 36px);
  max-width: 680px;
  margin: 0 auto;
  animation: ${fadeUp} 0.45s ease-out both;
  ${reducedMotion}
`;

const Header = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
`;

const TitleGroup = styled.div`
  display: flex;
  flex-direction: column;
  gap: 2px;
`;

const Title = styled.h1`
  margin: 0;
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: clamp(1.2rem, 2.5vw, 1.5rem);
  letter-spacing: 0.2em;
  text-transform: uppercase;
`;

const DateLine = styled.span`
  font-size: 0.65rem;
  letter-spacing: 0.08em;
  opacity: 0.4;
  text-transform: uppercase;
`;

const HeaderActions = styled.div`
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
`;

const CountPill = styled.span`
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.62rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  padding: 4px 10px;
  border-radius: 999px;
  background: ${({ theme }) => theme.palette?.pond?.['200'] ?? '#7ED7C4'}22;
  color: ${({ theme }) => theme.palette?.pond?.['200'] ?? '#7ED7C4'};
  white-space: nowrap;
`;

const RefreshBtn = styled.button`
  background: ${({ theme }) => theme.colors.overlay};
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  border-radius: 8px;
  color: inherit;
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.68rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  padding: 6px 12px;
  cursor: pointer;
  transition: background 0.15s ease;
  &:hover:not(:disabled) { background: ${({ theme }) => theme.colors.overlayActive}; }
  &:disabled { opacity: 0.4; cursor: default; }
`;

/* ─── Styled: Narrative ───────────────────────── */

const NarrativeCard = styled(Card)`
  font-size: 0.82rem;
  line-height: 1.7;
  opacity: 0.8;
  cursor: pointer;
  transition: opacity 0.15s ease;
  &:hover { opacity: 0.9; }
`;

const NarrativeLabel = styled.div`
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.6rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  opacity: 0.4;
  margin-bottom: 10px;
`;

const NarrativeText = styled.div<{ $expanded: boolean }>`
  white-space: pre-wrap;
  ${({ $expanded }) => !$expanded && `
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
  `}
`;

const ExpandHint = styled.span`
  display: inline-block;
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.58rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  opacity: 0.35;
  margin-top: 8px;
`;

/* ─── Styled: Top Stories ─────────────────────── */

const SectionLabel = styled.div`
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.72rem;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  opacity: 0.45;
`;

const TopStoriesGrid = styled.div`
  display: flex;
  flex-direction: column;
  gap: 12px;
`;

const StoryCard = styled(Card)`
  display: flex;
  flex-direction: column;
  gap: 6px;
  cursor: pointer;
  text-decoration: none;
  color: inherit;
  transition: transform 0.15s ease;
  &:hover { transform: translateY(-1px); }
`;

const StoryMeta = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
`;

const Dot = styled.span<{ $color: string }>`
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: ${({ $color }) => $color};
  flex-shrink: 0;
`;

const MetaText = styled.span`
  font-size: 0.58rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  opacity: 0.4;
`;

const TimeMeta = styled.span`
  font-size: 0.55rem;
  letter-spacing: 0.06em;
  opacity: 0.28;
`;

const StoryTitle = styled.div`
  font-size: 1rem;
  line-height: 1.4;
  font-weight: 500;
`;

const StorySummary = styled.div`
  font-size: 0.82rem;
  line-height: 1.55;
  opacity: 0.55;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
`;

/* ─── Styled: Category Sections ───────────────── */

const CategoriesWrap = styled.div`
  display: flex;
  flex-direction: column;
  gap: 24px;
`;

const CategoryBlock = styled.div`
  display: flex;
  flex-direction: column;
`;

const CatHeader = styled.button`
  display: flex;
  align-items: center;
  gap: 8px;
  background: none;
  border: none;
  padding: 6px 0;
  cursor: pointer;
  color: inherit;
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: clamp(0.72rem, 1.4vw, 0.82rem);
  letter-spacing: 0.14em;
  text-transform: uppercase;
  opacity: 0.5;
  transition: opacity 0.15s ease;
  &:hover { opacity: 0.8; }
  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: 2px;
  }
`;

const Chevron = styled.span<{ $open: boolean }>`
  display: inline-block;
  transition: transform 0.2s ease;
  transform: rotate(${({ $open }) => ($open ? '90deg' : '0deg')});
  font-size: 0.65rem;
`;

const CatCount = styled.span`
  font-size: 0.58rem;
  opacity: 0.4;
`;

const CatItems = styled.div`
  display: flex;
  flex-direction: column;
`;

const CompactRow = styled.div<{ $expandable: boolean }>`
  display: flex;
  flex-direction: column;
  padding: 8px 10px;
  border-radius: 8px;
  cursor: ${({ $expandable }) => ($expandable ? 'pointer' : 'default')};
  transition: background 0.12s ease;
  &:hover { background: ${({ theme }) => theme.colors.overlayHover}; }
`;

const CompactMain = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
`;

const CompactTitle = styled.a`
  flex: 1;
  min-width: 0;
  font-size: 0.84rem;
  line-height: 1.35;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  text-decoration: none;
  color: inherit;
  &:hover { text-decoration: underline; }
`;

const CompactSource = styled.span`
  font-size: 0.52rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  opacity: 0.3;
  flex-shrink: 0;
`;

const CompactTime = styled.span`
  font-size: 0.5rem;
  letter-spacing: 0.06em;
  opacity: 0.22;
  flex-shrink: 0;
`;

const ExpandedSummary = styled.div`
  font-size: 0.78rem;
  line-height: 1.55;
  opacity: 0.5;
  padding: 6px 0 4px 14px;
`;

/* ─── Styled: States ──────────────────────────── */

const LoadingState = styled.div`
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 64px 24px;
  font-size: 1rem;
  opacity: 0.4;
`;

const EmptyState = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
  padding: 64px 24px;
  text-align: center;
`;

const EmptyHeading = styled.span`
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 1rem;
  letter-spacing: 0.15em;
  text-transform: uppercase;
  opacity: 0.5;
`;

const EmptySubtext = styled.span`
  font-size: 0.78rem;
  opacity: 0.32;
  max-width: 300px;
`;

const Footer = styled.div`
  font-size: 0.58rem;
  opacity: 0.25;
  text-align: center;
`;

const Divider = styled.hr`
  border: none;
  border-top: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  opacity: 0.4;
  margin: 0;
`;

/* ─── Page Component ──────────────────────────── */

export function AIDigestPage() {
  const { digestQuery, refreshDigest: doRefresh, isRefreshing } = useAIDigest();
  const [sectionCollapsed, setSectionCollapsed] = useState<Set<string>>(loadCollapsed);
  const [expandedItems, setExpandedItems] = useState<Set<number>>(new Set());
  const [narrativeExpanded, setNarrativeExpanded] = useState(false);

  const data = digestQuery.data;
  const items = data?.items ?? [];
  const narrative = data?.narrative ?? null;

  const { top, rest } = extractTopStories(items);
  const grouped = groupByCategory(rest);

  function toggleSection(cat: string) {
    setSectionCollapsed(prev => {
      const next = new Set(prev);
      if (next.has(cat)) next.delete(cat);
      else next.add(cat);
      saveCollapsed(next);
      return next;
    });
  }

  function toggleItem(id: number) {
    setExpandedItems(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <Page>
      {/* ── Header ──────────────────────────── */}
      <Header>
        <TitleGroup>
          <Title data-halo="heading">AI Digest</Title>
          <DateLine>{formatDate()}</DateLine>
        </TitleGroup>
        <HeaderActions>
          {items.length > 0 && <CountPill>{items.length} items</CountPill>}
          <RefreshBtn onClick={doRefresh} disabled={isRefreshing}>
            {isRefreshing ? 'Refreshing...' : 'Refresh'}
          </RefreshBtn>
        </HeaderActions>
      </Header>

      {/* ── Loading / Empty ─────────────────── */}
      {digestQuery.isLoading ? (
        <LoadingState>Fetching your AI briefing...</LoadingState>
      ) : items.length === 0 ? (
        <EmptyState>
          <EmptyHeading data-halo="heading">No items yet</EmptyHeading>
          <EmptySubtext>Hit refresh to fetch your first AI digest.</EmptySubtext>
        </EmptyState>
      ) : (
        <>
          {/* ── Narrative ─────────────────────── */}
          {narrative && (
            <NarrativeCard onClick={() => setNarrativeExpanded(e => !e)}>
              <NarrativeLabel>Today's Overview</NarrativeLabel>
              <NarrativeText $expanded={narrativeExpanded}>
                {narrative}
              </NarrativeText>
              <ExpandHint>{narrativeExpanded ? 'Collapse' : 'Read more'}</ExpandHint>
            </NarrativeCard>
          )}

          {/* ── Top Stories ───────────────────── */}
          {top.length > 0 && (
            <>
              <SectionLabel>Top Stories</SectionLabel>
              <TopStoriesGrid>
                {top.map(item => {
                  const color = getColor(item.category);
                  const summary = item.llm_summary || item.summary;
                  return (
                    <StoryCard
                      key={item.id}
                      as="a"
                      href={item.url}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      <StoryMeta>
                        <Dot $color={color} />
                        <MetaText>{item.source_name}</MetaText>
                        <TimeMeta>{formatTimeAgo(item.published_at || item.fetched_at)}</TimeMeta>
                      </StoryMeta>
                      <StoryTitle data-halo="body">{item.title}</StoryTitle>
                      {summary && <StorySummary>{summary}</StorySummary>}
                    </StoryCard>
                  );
                })}
              </TopStoriesGrid>
            </>
          )}

          {/* ── Divider ───────────────────────── */}
          {grouped.length > 0 && <Divider />}

          {/* ── Category Sections ─────────────── */}
          <CategoriesWrap>
            {grouped.map(([category, catItems]) => {
              const isOpen = !sectionCollapsed.has(category);
              const color = getColor(category);
              return (
                <CategoryBlock key={category}>
                  <CatHeader
                    onClick={() => toggleSection(category)}
                    aria-expanded={isOpen}
                  >
                    <Chevron $open={isOpen}>›</Chevron>
                    {getLabel(category)}
                    <CatCount>{catItems.length}</CatCount>
                  </CatHeader>
                  {isOpen && (
                    <CatItems>
                      {catItems.map(item => {
                        const isExpanded = expandedItems.has(item.id);
                        const summary = item.llm_summary || item.summary;
                        const hasDetail = !!summary;
                        return (
                          <CompactRow
                            key={item.id}
                            $expandable={hasDetail}
                            onClick={() => hasDetail && toggleItem(item.id)}
                          >
                            <CompactMain>
                              <Dot $color={color} />
                              <CompactTitle
                                href={item.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                onClick={e => e.stopPropagation()}
                              >
                                {item.title}
                              </CompactTitle>
                              <CompactSource>{item.source_name}</CompactSource>
                              <CompactTime>{formatTimeAgo(item.published_at || item.fetched_at)}</CompactTime>
                            </CompactMain>
                            {isExpanded && summary && (
                              <ExpandedSummary>{summary}</ExpandedSummary>
                            )}
                          </CompactRow>
                        );
                      })}
                    </CatItems>
                  )}
                </CategoryBlock>
              );
            })}
          </CategoriesWrap>

          {/* ── Footer ────────────────────────── */}
          {data?.last_refreshed && (
            <Footer>Last updated: {formatTimeAgo(data.last_refreshed)}</Footer>
          )}
        </>
      )}
    </Page>
  );
}
