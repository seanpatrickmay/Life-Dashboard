import { useState } from 'react';
import styled from 'styled-components';

import { useAIDigest } from '../hooks/useAIDigest';
import type { DigestItem } from '../services/api';
import { fadeUp, reducedMotion } from '../styles/animations';

/* ─── Category colors ─────────────────────────── */

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

const COLLAPSE_STORAGE_KEY = 'ld_ai_digest_collapsed';

function loadCollapsedState(): Set<string> {
  try {
    const raw = localStorage.getItem(COLLAPSE_STORAGE_KEY);
    return raw ? new Set(JSON.parse(raw)) : new Set();
  } catch { return new Set(); }
}

function saveCollapsedState(collapsed: Set<string>): void {
  localStorage.setItem(COLLAPSE_STORAGE_KEY, JSON.stringify([...collapsed]));
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

/* ─── Styled components ───────────────────────── */

const Page = styled.div`
  display: flex;
  flex-direction: column;
  gap: clamp(16px, 3vw, 28px);
  animation: ${fadeUp} 0.45s ease-out both;
  ${reducedMotion}
`;

const TopBar = styled.div`
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

const RefreshButton = styled.button`
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
  flex-shrink: 0;

  &:hover:not(:disabled) {
    background: ${({ theme }) => theme.colors.overlayActive};
  }
  &:disabled {
    opacity: 0.4;
    cursor: default;
  }
`;

const ItemRow = styled.a`
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 10px;
  text-decoration: none;
  color: inherit;
  transition: background 0.15s ease;

  &:hover {
    background: ${({ theme }) => theme.colors.overlayHover};
  }
  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: 2px;
  }
`;

const Dot = styled.span<{ $color: string }>`
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: ${({ $color }) => $color};
  flex-shrink: 0;
`;

const ItemContent = styled.div`
  flex: 1;
  min-width: 0;
`;

const ItemTitle = styled.div`
  font-size: 0.88rem;
  line-height: 1.35;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
`;

const ItemSummary = styled.div`
  font-size: 0.72rem;
  line-height: 1.4;
  opacity: 0.45;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  margin-top: 2px;
`;

const ItemMeta = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
`;

const SourceBadge = styled.span<{ $color: string }>`
  font-size: 0.55rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  padding: 2px 6px;
  border-radius: 4px;
  background: ${({ $color }) => $color.replace(/[\d.]+\)$/, '0.12)')};
  color: ${({ $color }) => $color};
  white-space: nowrap;
`;

const TimeAgo = styled.span`
  font-size: 0.55rem;
  letter-spacing: 0.06em;
  opacity: 0.3;
  white-space: nowrap;
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

const LoadingState = styled.div`
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px;
  font-size: 1rem;
  opacity: 0.45;
`;

const EmptyState = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 48px 24px;
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
  opacity: 0.35;
  max-width: 300px;
`;

const Footer = styled.div`
  font-size: 0.6rem;
  opacity: 0.3;
  text-align: center;
  padding-top: 8px;
`;

const SectionHeader = styled.button`
  display: flex;
  align-items: center;
  gap: 8px;
  background: none;
  border: none;
  padding: 4px 0;
  cursor: pointer;
  color: inherit;
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: clamp(0.8rem, 1.6vw, 0.92rem);
  letter-spacing: 0.14em;
  text-transform: uppercase;
  opacity: 0.6;
  transition: opacity 0.15s ease;

  &:hover { opacity: 1; }
  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: 2px;
  }
`;

const Chevron = styled.span<{ $open: boolean }>`
  display: inline-block;
  transition: transform 0.2s ease;
  transform: rotate(${({ $open }) => ($open ? '90deg' : '0deg')});
  font-size: 0.7rem;
`;

const SectionCount = styled.span`
  font-size: 0.6rem;
  opacity: 0.4;
`;

const Section = styled.div`
  display: flex;
  flex-direction: column;
  gap: 2px;
`;

/* ─── Helpers ──────────────────────────────────── */

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

function getCategoryColor(category: string | null): string {
  return CATEGORY_COLORS[category || ''] || 'rgba(160, 160, 160, 0.7)';
}

function getCategoryLabel(category: string | null): string {
  return CATEGORY_LABELS[category || ''] || category || 'General';
}

/* ─── Page component ──────────────────────────── */

export function AIDigestPage() {
  const { digestQuery, refreshDigest: doRefresh, isRefreshing } = useAIDigest();
  const [collapsed, setCollapsed] = useState<Set<string>>(loadCollapsedState);
  const data = digestQuery.data;
  const items = data?.items ?? [];
  const grouped = groupByCategory(items);

  function toggleSection(category: string) {
    setCollapsed(prev => {
      const next = new Set(prev);
      if (next.has(category)) next.delete(category);
      else next.add(category);
      saveCollapsedState(next);
      return next;
    });
  }

  return (
    <Page>
      <TopBar>
        <TitleGroup>
          <Title data-halo="heading">AI Digest</Title>
          <DateLine>{formatDate()}</DateLine>
        </TitleGroup>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {items.length > 0 && <CountPill>{items.length} items</CountPill>}
          <RefreshButton onClick={doRefresh} disabled={isRefreshing}>
            {isRefreshing ? 'Refreshing...' : 'Refresh'}
          </RefreshButton>
        </div>
      </TopBar>

      {digestQuery.isLoading ? (
        <LoadingState>Fetching your AI briefing...</LoadingState>
      ) : items.length === 0 ? (
        <EmptyState>
          <EmptyHeading data-halo="heading">No items yet</EmptyHeading>
          <EmptySubtext>Hit refresh to fetch your first AI digest.</EmptySubtext>
        </EmptyState>
      ) : (
        grouped.map(([category, categoryItems]) => {
          const isOpen = !collapsed.has(category);
          const color = getCategoryColor(category);
          return (
            <div key={category}>
              <SectionHeader
                onClick={() => toggleSection(category)}
                aria-expanded={isOpen}
              >
                <Chevron $open={isOpen}>›</Chevron>
                {getCategoryLabel(category)}
                <SectionCount>{categoryItems.length}</SectionCount>
              </SectionHeader>
              {isOpen && (
                <Section>
                  {categoryItems.map((item: DigestItem) => (
                    <ItemRow
                      key={item.id}
                      href={item.url}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      <Dot $color={color} />
                      <ItemContent>
                        <ItemTitle data-halo="body">{item.title}</ItemTitle>
                        {item.summary && <ItemSummary>{item.summary}</ItemSummary>}
                      </ItemContent>
                      <ItemMeta>
                        <SourceBadge $color={color}>
                          {item.source_name}
                        </SourceBadge>
                        <TimeAgo>{formatTimeAgo(item.published_at || item.fetched_at)}</TimeAgo>
                      </ItemMeta>
                    </ItemRow>
                  ))}
                </Section>
              )}
            </div>
          );
        })
      )}

      {data?.last_refreshed && (
        <Footer>Last updated: {formatTimeAgo(data.last_refreshed)}</Footer>
      )}
    </Page>
  );
}
