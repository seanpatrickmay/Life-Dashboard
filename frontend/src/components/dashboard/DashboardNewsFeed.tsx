import styled from 'styled-components';

import { Card } from '../common/Card';
import { useNewsFeed } from '../../hooks/useNewsFeed';

const Panel = styled(Card)`
  display: flex;
  flex-direction: column;
  gap: clamp(12px, 2vw, 18px);
  box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.18), 0 0 32px rgba(200, 160, 255, 0.3);
  overflow: hidden;
`;

const HeadingRow = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
`;

const Heading = styled.h3`
  margin: 0;
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: clamp(0.95rem, 2vw, 1.1rem);
  letter-spacing: 0.16em;
  text-transform: uppercase;
`;

const RefreshButton = styled.button`
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 8px;
  color: inherit;
  font-size: 0.75rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  padding: 4px 10px;
  cursor: pointer;
  transition: all 0.2s ease;

  &:hover:not(:disabled) {
    background: rgba(255, 255, 255, 0.18);
    border-color: rgba(255, 255, 255, 0.35);
  }

  &:disabled {
    opacity: 0.5;
    cursor: default;
  }
`;

const ArticlesList = styled.div`
  display: flex;
  flex-direction: column;
  gap: clamp(8px, 1.5vw, 12px);
  overflow-y: auto;
  max-height: 420px;

  &::-webkit-scrollbar {
    width: 4px;
  }

  &::-webkit-scrollbar-track {
    background: transparent;
  }

  &::-webkit-scrollbar-thumb {
    background: rgba(255, 255, 255, 0.15);
    border-radius: 2px;

    &:hover {
      background: rgba(255, 255, 255, 0.25);
    }
  }
`;

const ArticleCard = styled.a<{ $isWikipedia?: boolean }>`
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: clamp(10px, 2vw, 14px);
  border-radius: 18px;
  background: rgba(0, 0, 0, 0.18);
  border: 1px solid ${({ $isWikipedia }) =>
    $isWikipedia ? 'rgba(200, 180, 255, 0.25)' : 'rgba(255, 255, 255, 0.2)'};
  transition: all 0.2s ease;
  text-decoration: none;
  color: inherit;
  cursor: pointer;

  &:hover {
    background: rgba(0, 0, 0, 0.25);
    border-color: ${({ $isWikipedia }) =>
      $isWikipedia ? 'rgba(200, 180, 255, 0.4)' : 'rgba(255, 255, 255, 0.3)'};
  }
`;

const ArticleSource = styled.div`
  font-size: 0.75rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  opacity: 0.6;
`;

const ArticleTitle = styled.div`
  font-family: ${({ theme }) => theme.fonts.body};
  font-size: 0.95rem;
  line-height: 1.35;
`;

const ArticleSummary = styled.div`
  font-size: 0.82rem;
  line-height: 1.4;
  opacity: 0.7;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
`;

const EmptyState = styled.p`
  margin: 0;
  font-size: 0.9rem;
  opacity: 0.8;
  text-align: center;
  padding: 20px;
`;

const LoadingState = styled.div`
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
  font-size: 1.2rem;
  opacity: 0.6;
`;

export function DashboardNewsFeed() {
  const { feedQuery, refreshFeed, markRead, isRefreshing } = useNewsFeed();

  const handleArticleClick = (articleId: string) => {
    markRead(articleId);
  };

  return (
    <Panel>
      <HeadingRow>
        <Heading data-halo="heading">News Feed</Heading>
        <RefreshButton onClick={refreshFeed} disabled={isRefreshing}>
          {isRefreshing ? '...' : 'Refresh'}
        </RefreshButton>
      </HeadingRow>

      {feedQuery.isLoading ? (
        <LoadingState>Loading...</LoadingState>
      ) : !feedQuery.data?.length ? (
        <EmptyState>No articles yet — click Refresh to fetch news</EmptyState>
      ) : (
        <ArticlesList>
          {feedQuery.data.map(article => (
            <ArticleCard
              key={article.id}
              href={article.url}
              target="_blank"
              rel="noopener noreferrer"
              $isWikipedia={article.sourceType === 'wikipedia'}
              onClick={() => handleArticleClick(article.id)}
            >
              <ArticleSource data-halo="body">
                {article.sourceName}
              </ArticleSource>
              <ArticleTitle data-halo="body">
                {article.title}
              </ArticleTitle>
              {article.summary && (
                <ArticleSummary data-halo="body">
                  {article.summary}
                </ArticleSummary>
              )}
            </ArticleCard>
          ))}
        </ArticlesList>
      )}
    </Panel>
  );
}
