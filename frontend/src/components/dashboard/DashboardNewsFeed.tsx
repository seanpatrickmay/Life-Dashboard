import styled from 'styled-components';
import { Link } from 'react-router-dom';

import { Card } from '../common/Card';
import { useNewsFeed } from '../../hooks/useNewsFeed';
import { CATEGORY_LABELS, type Category } from '../../services/newsFeedService';

const CATEGORY_COLORS: Record<Category, string> = {
  tech: 'rgba(120, 180, 255, 0.7)',
  science: 'rgba(130, 220, 180, 0.7)',
  world: 'rgba(255, 180, 120, 0.7)',
  culture: 'rgba(220, 160, 255, 0.7)',
  history: 'rgba(255, 210, 130, 0.7)',
  business: 'rgba(180, 200, 240, 0.7)',
  wikipedia: 'rgba(200, 200, 200, 0.7)',
};

const Panel = styled(Card)`
  display: flex;
  flex-direction: column;
  gap: clamp(10px, 1.5vw, 14px);
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

const ViewAllLink = styled(Link)`
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.68rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  text-decoration: none;
  color: inherit;
  opacity: 0.6;
  transition: opacity 0.2s ease;
  &:hover { opacity: 1; }
`;

const ArticlesList = styled.div`
  display: flex;
  flex-direction: column;
  gap: clamp(6px, 1vw, 8px);
  overflow-y: auto;
  max-height: 380px;

  &::-webkit-scrollbar { width: 3px; }
  &::-webkit-scrollbar-track { background: transparent; }
  &::-webkit-scrollbar-thumb {
    background: rgba(255, 255, 255, 0.12);
    border-radius: 2px;
  }
`;

const ArticleRow = styled.a`
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 14px;
  background: rgba(0, 0, 0, 0.14);
  border: 1px solid rgba(255, 255, 255, 0.1);
  transition: all 0.2s ease;
  text-decoration: none;
  color: inherit;
  cursor: pointer;

  &:hover {
    background: rgba(0, 0, 0, 0.22);
    border-color: rgba(255, 255, 255, 0.2);
  }
`;

const CategoryPill = styled.span<{ $color: string }>`
  flex-shrink: 0;
  font-size: 0.58rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  padding: 2px 7px;
  border-radius: 6px;
  background: ${({ $color }) => $color.replace('0.7', '0.18')};
  color: ${({ $color }) => $color};
  margin-top: 2px;
  white-space: nowrap;
`;

const ArticleContent = styled.div`
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
`;

const ArticleTitle = styled.div`
  font-family: ${({ theme }) => theme.fonts.body};
  font-size: 0.88rem;
  line-height: 1.3;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
`;

const ArticleSource = styled.div`
  font-size: 0.65rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  opacity: 0.45;
`;

const EmptyState = styled.p`
  margin: 0;
  font-size: 0.85rem;
  opacity: 0.6;
  text-align: center;
  padding: 16px 0;
`;

const LoadingState = styled.div`
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 28px;
  font-size: 1rem;
  opacity: 0.5;
`;

export function DashboardNewsFeed() {
  const { feedQuery, markRead } = useNewsFeed();

  const handleArticleClick = (articleId: string) => {
    markRead(articleId);
  };

  return (
    <Panel>
      <HeadingRow>
        <Heading data-halo="heading">Reading List</Heading>
        <ViewAllLink to="/news">View All</ViewAllLink>
      </HeadingRow>

      {feedQuery.isLoading ? (
        <LoadingState>Loading...</LoadingState>
      ) : !feedQuery.data?.length ? (
        <EmptyState>No articles yet</EmptyState>
      ) : (
        <ArticlesList>
          {feedQuery.data.map(article => (
            <ArticleRow
              key={article.id}
              href={article.url}
              target="_blank"
              rel="noopener noreferrer"
              onClick={() => handleArticleClick(article.id)}
            >
              <CategoryPill $color={CATEGORY_COLORS[article.category]}>
                {CATEGORY_LABELS[article.category]}
              </CategoryPill>
              <ArticleContent>
                <ArticleTitle data-halo="body">
                  {article.title}
                </ArticleTitle>
                <ArticleSource data-halo="body">
                  {article.sourceName}
                </ArticleSource>
              </ArticleContent>
            </ArticleRow>
          ))}
        </ArticlesList>
      )}
    </Panel>
  );
}
