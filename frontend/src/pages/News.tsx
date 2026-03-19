import { useRef, useState } from 'react';
import styled from 'styled-components';

import { Card } from '../components/common/Card';
import { useNewsFeed } from '../hooks/useNewsFeed';
import { CATEGORY_LABELS, type Category } from '../services/newsFeedService';
import { fadeUp, reducedMotion } from '../styles/animations';

const CATEGORY_COLORS: Record<Category, string> = {
  tech: 'rgba(120, 180, 255, 0.85)',
  science: 'rgba(130, 220, 180, 0.85)',
  world: 'rgba(255, 180, 120, 0.85)',
  culture: 'rgba(220, 160, 255, 0.85)',
  history: 'rgba(255, 210, 130, 0.85)',
  business: 'rgba(180, 200, 240, 0.85)',
  wikipedia: 'rgba(200, 200, 200, 0.85)',
};

const CATEGORY_ORDER: Category[] = ['world', 'tech', 'science', 'culture', 'history', 'business', 'wikipedia'];

const Page = styled.div`
  display: flex;
  flex-direction: column;
  gap: clamp(14px, 2.5vw, 22px);
  animation: ${fadeUp} 0.45s ease-out both;
  ${reducedMotion}
`;

const TopBar = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
`;

const Title = styled.h1`
  margin: 0;
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: clamp(1.2rem, 2.5vw, 1.5rem);
  letter-spacing: 0.2em;
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

  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: 2px;
  }

  &:disabled {
    opacity: 0.4;
    cursor: default;
  }
`;

const CategoryStrip = styled.div`
  display: flex;
  gap: 6px;
  overflow-x: auto;
  scrollbar-width: none;
  -ms-overflow-style: none;
  &::-webkit-scrollbar { display: none; }
  padding-bottom: 2px;
`;

const CategoryTab = styled.button<{ $active: boolean; $color: string }>`
  background: ${({ $active, theme }) => $active ? theme.colors.overlay : 'transparent'};
  border: 1px solid ${({ $active, $color, theme }) =>
    $active ? $color : theme.colors.borderSubtle};
  border-radius: 6px;
  color: inherit;
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.7rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  padding: 5px 10px;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.15s ease;
  opacity: ${({ $active }) => $active ? 1 : 0.55};

  &:hover {
    opacity: 1;
    background: ${({ theme }) => theme.colors.overlay};
  }

  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: 2px;
  }
`;

const CategoryBlock = styled.div`
  display: flex;
  flex-direction: column;
  gap: clamp(8px, 1.5vw, 14px);
`;

const CategoryHead = styled.div`
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

const CategoryName = styled.h2`
  margin: 0;
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: clamp(0.8rem, 1.6vw, 0.95rem);
  letter-spacing: 0.14em;
  text-transform: uppercase;
`;

const Count = styled.span`
  font-size: 0.6rem;
  letter-spacing: 0.08em;
  opacity: 0.35;
  margin-left: auto;
`;

const ScrollTrack = styled.div`
  display: flex;
  gap: clamp(8px, 1.2vw, 12px);
  overflow-x: auto;
  scroll-snap-type: x mandatory;
  scrollbar-width: none;
  -ms-overflow-style: none;
  &::-webkit-scrollbar { display: none; }
  padding-bottom: 4px;

  /* fade hint on right edge */
  mask-image: linear-gradient(to right, black calc(100% - 40px), transparent 100%);
  -webkit-mask-image: linear-gradient(to right, black calc(100% - 40px), transparent 100%);
`;

const ArticleCard = styled.a<{ $borderColor: string }>`
  flex: 0 0 min(320px, 80vw);
  scroll-snap-align: start;
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding: clamp(10px, 1.5vw, 14px);
  border-radius: 10px;
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

const ArticleTitle = styled.div`
  font-family: ${({ theme }) => theme.fonts.body};
  font-size: 0.85rem;
  line-height: 1.3;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
`;

const ArticleSummary = styled.div`
  font-size: 0.75rem;
  line-height: 1.4;
  opacity: 0.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
`;

const ArticleMeta = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 0.58rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  opacity: 0.35;
  margin-top: auto;
  padding-top: 2px;
`;

const EmptyState = styled.div`
  font-size: 0.8rem;
  opacity: 0.35;
  padding: 4px 0;
`;

const LoadingState = styled.div`
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px;
  font-size: 1rem;
  opacity: 0.45;
`;

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

export function NewsPage() {
  const { allQuery, refreshFeed, markRead, isRefreshing } = useNewsFeed();
  const [activeFilter, setActiveFilter] = useState<Category | 'all'>('all');
  const scrollRefs = useRef<Record<string, HTMLDivElement | null>>({});

  const visibleCategories = CATEGORY_ORDER.filter(cat => {
    const articles = allQuery.data?.[cat] || [];
    return articles.length > 0;
  });

  const filteredCategories = activeFilter === 'all'
    ? visibleCategories
    : visibleCategories.filter(cat => cat === activeFilter);

  return (
    <Page>
      <TopBar>
        <Title data-halo="heading">Reading List</Title>
        <RefreshButton onClick={refreshFeed} disabled={isRefreshing}>
          {isRefreshing ? 'Refreshing...' : 'Refresh'}
        </RefreshButton>
      </TopBar>

      {!allQuery.isLoading && visibleCategories.length > 0 && (
        <CategoryStrip>
          <CategoryTab
            $active={activeFilter === 'all'}
            $color={CATEGORY_COLORS.tech}
            onClick={() => setActiveFilter('all')}
          >
            All
          </CategoryTab>
          {visibleCategories.map(cat => (
            <CategoryTab
              key={cat}
              $active={activeFilter === cat}
              $color={CATEGORY_COLORS[cat]}
              onClick={() => setActiveFilter(cat)}
            >
              {CATEGORY_LABELS[cat]}
            </CategoryTab>
          ))}
        </CategoryStrip>
      )}

      {allQuery.isLoading ? (
        <LoadingState>Loading articles...</LoadingState>
      ) : (
        filteredCategories.map(cat => {
          const articles = allQuery.data?.[cat] || [];
          const color = CATEGORY_COLORS[cat];

          return (
            <CategoryBlock key={cat}>
              <CategoryHead>
                <Dot $color={color} />
                <CategoryName data-halo="heading">{CATEGORY_LABELS[cat]}</CategoryName>
                <Count>{articles.length}</Count>
              </CategoryHead>
              {articles.length === 0 ? (
                <EmptyState>No articles yet.</EmptyState>
              ) : (
                <ScrollTrack
                  ref={el => { scrollRefs.current[cat] = el; }}
                >
                  {articles.map(article => (
                    <ArticleCard
                      key={article.id}
                      href={article.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      $borderColor={color}
                      onClick={() => markRead(article.id)}
                    >
                      <ArticleTitle data-halo="body">{article.title}</ArticleTitle>
                      {article.summary && (
                        <ArticleSummary>{article.summary}</ArticleSummary>
                      )}
                      <ArticleMeta>
                        <span>{article.sourceName}</span>
                        <span>{formatTimeAgo(article.publishedAt || article.fetchedAt)}</span>
                      </ArticleMeta>
                    </ArticleCard>
                  ))}
                </ScrollTrack>
              )}
            </CategoryBlock>
          );
        })
      )}
    </Page>
  );
}
