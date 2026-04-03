import { useMemo, useState, useCallback } from 'react';
import styled from 'styled-components';
import { Link } from 'react-router-dom';

import { Card } from '../components/common/Card';
import { QualityFeedback, shouldShowFeedback, recordFeedbackRead } from '../components/news/QualityFeedback';
import { useNewsFeed } from '../hooks/useNewsFeed';
import {
  CATEGORY_LABELS,
  getLastRefresh,
  getReadTodayCount,
  type Category,
  type NewsArticle,
} from '../services/newsFeedService';
import { getSavedArticleIds } from '../services/interestProfile';
import { fadeUp, reducedMotion } from '../styles/animations';

/* ─── Category colors ─────────────────────────── */

const CATEGORY_COLORS: Record<Category, string> = {
  tech: 'rgba(120, 180, 255, 0.85)',
  science: 'rgba(130, 220, 180, 0.85)',
  world: 'rgba(255, 180, 120, 0.85)',
  culture: 'rgba(220, 160, 255, 0.85)',
  history: 'rgba(255, 210, 130, 0.85)',
  business: 'rgba(180, 200, 240, 0.85)',
  wikipedia: 'rgba(200, 200, 200, 0.85)',
};

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

const ActionGroup = styled.div`
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
`;

const ReadingPill = styled.span`
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
  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: 2px;
  }
  &:disabled {
    opacity: 0.4;
    cursor: default;
  }
`;

/* ─── Hero Card ────────────────────────────────── */

const HeroCard = styled(Card)`
  display: flex;
  flex-direction: column;
  gap: 8px;
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
  text-decoration: none;
  color: inherit;

  &:hover {
    transform: translateY(-2px);
  }
`;

const HeroMeta = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
`;

const SourcePill = styled.span<{ $color: string }>`
  font-size: 0.75rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  padding: 2px 8px;
  border-radius: 5px;
  background: ${({ $color }) => $color.replace(/[\d.]+\)$/, '0.15)')};
  color: ${({ $color }) => $color};
  white-space: nowrap;
`;

const HeroTimeAgo = styled.span`
  font-size: 0.875rem;
  letter-spacing: 0.06em;
  opacity: 0.35;
  text-transform: uppercase;
`;

const HeroTitle = styled.h2`
  margin: 0;
  font-family: ${({ theme }) => theme.fonts.body};
  font-size: clamp(1.05rem, 2.2vw, 1.35rem);
  line-height: 1.35;
  letter-spacing: 0.01em;
`;

const HeroSummary = styled.p`
  margin: 0;
  font-size: 0.82rem;
  line-height: 1.55;
  opacity: 0.6;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
`;

const HeroActions = styled.div`
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 2px;
`;

/* ─── Pick Cards ───────────────────────────────── */

const PicksGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(280px, 100%), 1fr));
  gap: clamp(10px, 1.5vw, 16px);
`;

const PickCard = styled.a<{ $borderColor: string }>`
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: clamp(12px, 1.5vw, 16px);
  border-radius: ${({ theme }) => theme.radii?.card ?? '16px'};
  background: ${({ theme }) => theme.colors.surfaceRaised};
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  transition: border-color 0.15s ease, transform 0.15s ease;
  text-decoration: none;
  color: inherit;
  cursor: pointer;

  &:hover {
    border-color: ${({ $borderColor }) => $borderColor};
    transform: translateY(-1px);
  }
  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: 2px;
  }
`;

const PickTitle = styled.div`
  font-family: ${({ theme }) => theme.fonts.body};
  font-size: 0.88rem;
  line-height: 1.35;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
`;

const PickSummary = styled.div`
  font-size: 0.75rem;
  line-height: 1.45;
  opacity: 0.45;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
`;

const PickMeta = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: auto;
  padding-top: 4px;
`;

const PickSource = styled.span`
  font-size: 0.875rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  opacity: 0.35;
`;

const PickTimeAgo = styled.span`
  font-size: 0.875rem;
  letter-spacing: 0.06em;
  opacity: 0.3;
`;

/* ─── Action buttons ───────────────────────────── */

const IconButton = styled.button<{ $active?: boolean }>`
  background: none;
  border: none;
  padding: 10px 12px;
  min-width: 44px;
  min-height: 44px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  font-size: 0.72rem;
  opacity: ${({ $active }) => ($active ? 0.9 : 0.3)};
  color: ${({ $active, theme }) =>
    $active ? (theme.palette?.pond?.['200'] ?? '#7ED7C4') : 'inherit'};
  transition: opacity 0.15s ease, color 0.15s ease;
  border-radius: 4px;

  &:hover {
    opacity: 0.8;
    background: ${({ theme }) => theme.colors.overlay};
  }
  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: 2px;
  }
`;

/* ─── More Stories section ─────────────────────── */

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

const CollapsibleSection = styled.div<{ $open: boolean }>`
  display: grid;
  grid-template-rows: ${({ $open }) => ($open ? '1fr' : '0fr')};
  transition: grid-template-rows 0.25s ease-out;
  ${reducedMotion}
`;

const CollapsibleInner = styled.div`
  overflow: hidden;
`;

const MoreList = styled.div`
  display: flex;
  flex-direction: column;
  gap: 2px;
`;

const MoreRow = styled.a`
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 8px;
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

const MoreTitle = styled.span`
  flex: 1;
  font-size: 0.82rem;
  line-height: 1.3;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
`;

const MoreSource = styled.span`
  flex-shrink: 0;
  font-size: 0.55rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  opacity: 0.3;
`;

const Dot = styled.span<{ $color: string }>`
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: ${({ $color }) => $color};
  flex-shrink: 0;
`;

const Annotation = styled.div`
  font-size: 0.75rem;
  font-style: italic;
  letter-spacing: 0.02em;
  opacity: 0.45;
  line-height: 1.3;
  margin-top: 2px;
`;

const DiscoveryLabel = styled.span`
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.65rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  padding: 2px 8px;
  border-radius: 5px;
  background: ${({ theme }) => theme.palette?.lilac?.['100'] ?? '#E5E0FF'}33;
  color: ${({ theme }) => theme.palette?.lilac?.['200'] ?? '#B1A7FF'};
  white-space: nowrap;
`;

/* ─── Saved section ────────────────────────────── */

const SavedList = styled.div`
  display: flex;
  flex-direction: column;
  gap: 2px;
`;

/* ─── Empty / Loading states ───────────────────── */

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

/* ─── Page component ──────────────────────────── */

export function NewsPage() {
  const {
    curatedQuery,
    annotationsQuery,
    refreshFeed,
    markRead,
    saveArticle: doSave,
    unsaveArticle: doUnsave,
    dismissArticle: doDismiss,
    isRefreshing,
  } = useNewsFeed();

  const annotations = annotationsQuery.data ?? {};

  const [moreOpen, setMoreOpen] = useState(false);
  const [savedOpen, setSavedOpen] = useState(false);
  const [showFeedback, setShowFeedback] = useState(false);
  const [feedbackArticle, setFeedbackArticle] = useState<NewsArticle | null>(null);

  const curated = curatedQuery.data;
  const picks = curated?.picks ?? [];
  const more = curated?.more ?? [];
  const saved = curated?.saved ?? [];

  const hero = picks[0] ?? null;
  const restPicks = picks.slice(1);

  // Derive saved set from query data for reactive UI updates
  const savedSet = useMemo(
    () => new Set(saved.map(a => a.id)),
    [saved],
  );
  const isSaved = (id: string) => savedSet.has(id);

  const lastRefresh = getLastRefresh();
  const readToday = getReadTodayCount();

  function handleArticleClick(articleId: string) {
    markRead(articleId);
    recordFeedbackRead();
    // After reading, check if we should show feedback
    if (shouldShowFeedback()) {
      const article = picks.find(a => a.id !== articleId) ?? picks[0];
      if (article) {
        setFeedbackArticle(article);
        setShowFeedback(true);
      }
    }
  }

  function handleSaveToggle(e: React.MouseEvent, articleId: string) {
    e.preventDefault();
    e.stopPropagation();
    if (isSaved(articleId)) {
      doUnsave(articleId);
    } else {
      doSave(articleId);
    }
  }

  function handleDismiss(e: React.MouseEvent, articleId: string) {
    e.preventDefault();
    e.stopPropagation();
    doDismiss(articleId);
  }

  return (
    <Page>
      {/* ─── Header ─────────────────────────────── */}
      <TopBar>
        <TitleGroup>
          <Title data-halo="heading">Today's Briefing</Title>
          <DateLine>{formatDate()}</DateLine>
        </TitleGroup>
        <ActionGroup>
          {readToday > 0 && (
            <ReadingPill>{readToday} read today</ReadingPill>
          )}
          {lastRefresh && (
            <DateLine>{formatTimeAgo(lastRefresh)}</DateLine>
          )}
          <RefreshButton onClick={refreshFeed} disabled={isRefreshing}>
            {isRefreshing ? 'Refreshing...' : 'Refresh'}
          </RefreshButton>
          <Link to="/news/profile" style={{ textDecoration: 'none', color: 'inherit', opacity: 0.4, fontSize: '0.68rem', letterSpacing: '0.1em', textTransform: 'uppercase' as const }}>
            Profile
          </Link>
        </ActionGroup>
      </TopBar>

      {/* Quality Feedback */}
      {showFeedback && feedbackArticle && (
        <QualityFeedback
          article={feedbackArticle}
          onDismiss={() => setShowFeedback(false)}
        />
      )}

      {/* ─── Loading ────────────────────────────── */}
      {curatedQuery.isLoading ? (
        <LoadingState>Curating your briefing...</LoadingState>
      ) : !hero ? (
        <EmptyState>
          <EmptyHeading data-halo="heading">No articles yet</EmptyHeading>
          <EmptySubtext>Hit refresh to fetch your first briefing.</EmptySubtext>
        </EmptyState>
      ) : (
        <>
          {/* ─── Hero Article ───────────────────── */}
          <HeroCard
            as="a"
            href={hero.url}
            target="_blank"
            rel="noopener noreferrer"
            onClick={() => handleArticleClick(hero.id)}
          >
            <HeroMeta>
              <SourcePill $color={CATEGORY_COLORS[hero.category]}>
                {CATEGORY_LABELS[hero.category]}
              </SourcePill>
              <HeroTimeAgo>
                {hero.sourceName} &middot; {formatTimeAgo(hero.publishedAt || hero.fetchedAt)}
              </HeroTimeAgo>
            </HeroMeta>
            <HeroTitle data-halo="heading">{hero.title}</HeroTitle>
            {annotations[hero.id] && <Annotation>{annotations[hero.id]}</Annotation>}
            {hero.summary && <HeroSummary>{hero.summary}</HeroSummary>}
            <HeroActions>
              <IconButton
                $active={isSaved(hero.id)}
                onClick={(e) => handleSaveToggle(e, hero.id)}
                aria-label={isSaved(hero.id) ? 'Remove from saved' : 'Save for later'}
              >
                {isSaved(hero.id) ? '★' : '☆'}
              </IconButton>
              <IconButton
                onClick={(e) => handleDismiss(e, hero.id)}
                aria-label="Dismiss article"
              >
                ✕
              </IconButton>
            </HeroActions>
          </HeroCard>

          {/* ─── Picks Grid ─────────────────────── */}
          {restPicks.length > 0 && (
            <PicksGrid>
              {restPicks.map(article => {
                const color = CATEGORY_COLORS[article.category];
                return (
                  <PickCard
                    key={article.id}
                    href={article.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    $borderColor={color}
                    onClick={() => handleArticleClick(article.id)}
                  >
                    <PickTitle data-halo="body">{article.title}</PickTitle>
                    {annotations[article.id] && <Annotation>{annotations[article.id]}</Annotation>}
                    {article.summary && (
                      <PickSummary>{article.summary}</PickSummary>
                    )}
                    <PickMeta>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <Dot $color={color} />
                        <PickSource>{article.sourceName}</PickSource>
                        {article.isExploration && <DiscoveryLabel>Discovery</DiscoveryLabel>}
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <PickTimeAgo>
                          {formatTimeAgo(article.publishedAt || article.fetchedAt)}
                        </PickTimeAgo>
                        <IconButton
                          $active={isSaved(article.id)}
                          onClick={(e) => handleSaveToggle(e, article.id)}
                          aria-label={isSaved(article.id) ? 'Remove from saved' : 'Save for later'}
                        >
                          {isSaved(article.id) ? '★' : '☆'}
                        </IconButton>
                        <IconButton
                          onClick={(e) => handleDismiss(e, article.id)}
                          aria-label="Dismiss article"
                        >
                          ✕
                        </IconButton>
                      </div>
                    </PickMeta>
                  </PickCard>
                );
              })}
            </PicksGrid>
          )}

          {/* ─── More Stories ───────────────────── */}
          {more.length > 0 && (
            <div>
              <SectionHeader
                onClick={() => setMoreOpen(o => !o)}
                aria-expanded={moreOpen}
              >
                <Chevron $open={moreOpen}>›</Chevron>
                More Stories
                <span style={{ fontSize: '0.6rem', opacity: 0.4 }}>
                  {more.length}
                </span>
              </SectionHeader>

              <CollapsibleSection $open={moreOpen}>
                <CollapsibleInner>
                  <MoreList>
                    {more.map(article => {
                      const color = CATEGORY_COLORS[article.category];
                      return (
                        <MoreRow
                          key={article.id}
                          href={article.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={() => handleArticleClick(article.id)}
                        >
                          <Dot $color={color} />
                          <MoreTitle data-halo="body">{article.title}</MoreTitle>
                          <MoreSource>{article.sourceName}</MoreSource>
                          <IconButton
                            $active={isSaved(article.id)}
                            onClick={(e) => handleSaveToggle(e, article.id)}
                            aria-label={isSaved(article.id) ? 'Remove from saved' : 'Save for later'}
                          >
                            {isSaved(article.id) ? '★' : '☆'}
                          </IconButton>
                        </MoreRow>
                      );
                    })}
                  </MoreList>
                </CollapsibleInner>
              </CollapsibleSection>
            </div>
          )}

          {/* ─── Saved Articles ─────────────────── */}
          {saved.length > 0 && (
            <div>
              <SectionHeader
                onClick={() => setSavedOpen(o => !o)}
                aria-expanded={savedOpen}
              >
                <Chevron $open={savedOpen}>›</Chevron>
                Saved
                <span style={{ fontSize: '0.6rem', opacity: 0.4 }}>
                  {saved.length}
                </span>
              </SectionHeader>

              <CollapsibleSection $open={savedOpen}>
                <CollapsibleInner>
                  <SavedList>
                    {saved.map(article => {
                      const color = CATEGORY_COLORS[article.category];
                      return (
                        <MoreRow
                          key={article.id}
                          href={article.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={() => handleArticleClick(article.id)}
                        >
                          <Dot $color={color} />
                          <MoreTitle data-halo="body">{article.title}</MoreTitle>
                          <MoreSource>{article.sourceName}</MoreSource>
                          <IconButton
                            $active
                            onClick={(e) => handleSaveToggle(e, article.id)}
                            title="Unsave"
                          >
                            ★
                          </IconButton>
                        </MoreRow>
                    );
                  })}
                  </SavedList>
                </CollapsibleInner>
              </CollapsibleSection>
            </div>
          )}
        </>
      )}
    </Page>
  );
}
