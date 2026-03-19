import styled from 'styled-components';

import { Card } from '../components/common/Card';
import { useNewsFeed } from '../hooks/useNewsFeed';
import { CATEGORY_LABELS, type Category } from '../services/newsFeedService';

const CATEGORY_COLORS: Record<Category, { accent: string; bg: string; border: string }> = {
  tech: { accent: 'rgba(120, 180, 255, 0.85)', bg: 'rgba(120, 180, 255, 0.06)', border: 'rgba(120, 180, 255, 0.2)' },
  science: { accent: 'rgba(130, 220, 180, 0.85)', bg: 'rgba(130, 220, 180, 0.06)', border: 'rgba(130, 220, 180, 0.2)' },
  world: { accent: 'rgba(255, 180, 120, 0.85)', bg: 'rgba(255, 180, 120, 0.06)', border: 'rgba(255, 180, 120, 0.2)' },
  culture: { accent: 'rgba(220, 160, 255, 0.85)', bg: 'rgba(220, 160, 255, 0.06)', border: 'rgba(220, 160, 255, 0.2)' },
  history: { accent: 'rgba(255, 210, 130, 0.85)', bg: 'rgba(255, 210, 130, 0.06)', border: 'rgba(255, 210, 130, 0.2)' },
  business: { accent: 'rgba(180, 200, 240, 0.85)', bg: 'rgba(180, 200, 240, 0.06)', border: 'rgba(180, 200, 240, 0.2)' },
  wikipedia: { accent: 'rgba(200, 200, 200, 0.85)', bg: 'rgba(200, 200, 200, 0.06)', border: 'rgba(200, 200, 200, 0.2)' },
};

const CATEGORY_ORDER: Category[] = ['world', 'tech', 'science', 'culture', 'history', 'business', 'wikipedia'];

const PageHeader = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: clamp(16px, 3vw, 28px);
`;

const Title = styled.h1`
  margin: 0;
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: clamp(1.3rem, 3vw, 1.8rem);
  letter-spacing: 0.2em;
  text-transform: uppercase;
`;

const RefreshButton = styled.button`
  background: ${({ theme }) => theme.colors.overlay};
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  border-radius: 10px;
  color: inherit;
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.72rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  padding: 8px 16px;
  cursor: pointer;
  transition: background 0.2s ease, border-color 0.2s ease;

  &:hover:not(:disabled) {
    background: ${({ theme }) => theme.colors.overlayActive};
    border-color: ${({ theme }) => theme.colors.borderSubtle};
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

const CategoriesGrid = styled.div`
  display: flex;
  flex-direction: column;
  gap: clamp(20px, 3vw, 32px);
`;

const CategorySection = styled(Card)<{ $accent: string; $border: string }>`
  display: flex;
  flex-direction: column;
  gap: clamp(10px, 1.5vw, 16px);
  border-color: ${({ $border }) => $border};
`;

const CategoryHeader = styled.div`
  display: flex;
  align-items: center;
  gap: 10px;
`;

const CategoryDot = styled.span<{ $color: string }>`
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: ${({ $color }) => $color};
  flex-shrink: 0;
`;

const CategoryName = styled.h2`
  margin: 0;
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: clamp(0.9rem, 1.8vw, 1.05rem);
  letter-spacing: 0.14em;
  text-transform: uppercase;
`;

const ArticleCount = styled.span`
  font-size: 0.65rem;
  letter-spacing: 0.08em;
  opacity: 0.4;
  margin-left: auto;
`;

const ArticlesGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: clamp(8px, 1.5vw, 12px);
`;

const ArticleCard = styled.a`
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: clamp(12px, 2vw, 16px);
  border-radius: 16px;
  background: ${({ theme }) => theme.colors.surfaceRaised};
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  transition: all 0.2s ease;
  text-decoration: none;
  color: inherit;
  cursor: pointer;

  &:hover {
    background: ${({ theme }) => theme.colors.surfaceInset};
    border-color: ${({ theme }) => theme.colors.borderSubtle};
    transform: translateY(-1px);
  }

  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: 2px;
  }
`;

const ArticleTitle = styled.div`
  font-family: ${({ theme }) => theme.fonts.body};
  font-size: 0.92rem;
  line-height: 1.35;
`;

const ArticleSummary = styled.div`
  font-size: 0.78rem;
  line-height: 1.45;
  opacity: 0.6;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
`;

const ArticleMeta = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 0.62rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  opacity: 0.4;
  margin-top: 2px;
`;

const EmptyCategory = styled.div`
  font-size: 0.82rem;
  opacity: 0.4;
  padding: 8px 0;
`;

const LoadingState = styled.div`
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 60px;
  font-size: 1.2rem;
  opacity: 0.5;
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

  return (
    <div>
      <PageHeader>
        <Title data-halo="heading">Reading List</Title>
        <RefreshButton onClick={refreshFeed} disabled={isRefreshing}>
          {isRefreshing ? 'Refreshing...' : 'Refresh Feeds'}
        </RefreshButton>
      </PageHeader>

      {allQuery.isLoading ? (
        <LoadingState>Loading articles...</LoadingState>
      ) : (
        <CategoriesGrid>
          {CATEGORY_ORDER.map(cat => {
            const articles = allQuery.data?.[cat] || [];
            const colors = CATEGORY_COLORS[cat];
            if (articles.length === 0) return null;

            return (
              <CategorySection key={cat} $accent={colors.accent} $border={colors.border}>
                <CategoryHeader>
                  <CategoryDot $color={colors.accent} />
                  <CategoryName data-halo="heading">{CATEGORY_LABELS[cat]}</CategoryName>
                  <ArticleCount>{articles.length} article{articles.length !== 1 ? 's' : ''}</ArticleCount>
                </CategoryHeader>
                <ArticlesGrid>
                  {articles.slice(0, 8).map(article => (
                    <ArticleCard
                      key={article.id}
                      href={article.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={() => markRead(article.id)}
                    >
                      <ArticleTitle data-halo="body">{article.title}</ArticleTitle>
                      {article.summary && (
                        <ArticleSummary data-halo="body">{article.summary}</ArticleSummary>
                      )}
                      <ArticleMeta>
                        <span>{article.sourceName}</span>
                        <span>{formatTimeAgo(article.publishedAt || article.fetchedAt)}</span>
                      </ArticleMeta>
                    </ArticleCard>
                  ))}
                </ArticlesGrid>
              </CategorySection>
            );
          })}
        </CategoriesGrid>
      )}
    </div>
  );
}
