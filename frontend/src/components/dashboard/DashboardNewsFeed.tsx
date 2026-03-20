import { useEffect, useState } from 'react';
import styled from 'styled-components';
import { Link } from 'react-router-dom';

import { Card } from '../common/Card';
import { useNewsFeed } from '../../hooks/useNewsFeed';
import { shortenTitles } from '../../services/api';
import { CATEGORY_LABELS, type Category, type NewsArticle } from '../../services/newsFeedService';

const SHORT_TITLE_CACHE_KEY = 'ld_short_titles';

function loadTitleCache(): Record<string, string> {
  try {
    const raw = localStorage.getItem(SHORT_TITLE_CACHE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch { return {}; }
}

function saveTitleCache(cache: Record<string, string>) {
  localStorage.setItem(SHORT_TITLE_CACHE_KEY, JSON.stringify(cache));
}

function useShortTitles(articles: NewsArticle[]) {
  const [titleMap, setTitleMap] = useState<Record<string, string>>(loadTitleCache);

  useEffect(() => {
    if (!articles.length) return;

    const uncached = articles.filter(a => !(a.id in titleMap));
    if (uncached.length === 0) return;

    let cancelled = false;
    shortenTitles(uncached.map(a => a.title)).then(shorts => {
      if (cancelled) return;
      setTitleMap(prev => {
        const next = { ...prev };
        uncached.forEach((a, i) => { next[a.id] = shorts[i] ?? a.title; });
        saveTitleCache(next);
        return next;
      });
    }).catch(() => {
      // On failure, fall back to original titles — no-op
    });

    return () => { cancelled = true; };
  }, [articles, titleMap]);

  return (id: string, fallback: string) => titleMap[id] ?? fallback;
}

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
    background: ${({ theme }) => theme.colors.scrollThumb};
    border-radius: 2px;
  }
`;

const ArticleRow = styled.a`
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 12px;
  border-radius: 14px;
  background: ${({ theme }) => theme.colors.surfaceRaised};
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  transition: all 0.2s ease;
  text-decoration: none;
  color: inherit;
  cursor: pointer;

  &:hover {
    background: ${({ theme }) => theme.colors.overlayHover};
    border-color: ${({ theme }) => theme.colors.borderSubtle};
  }

  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: 2px;
  }
`;

const CategoryPill = styled.span<{ $color: string }>`
  align-self: flex-start;
  font-size: 0.55rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  padding: 1px 6px;
  border-radius: 5px;
  background: ${({ $color }) => ($color || 'rgba(200,200,200,0.7)').replace('0.7', '0.18')};
  color: ${({ $color }) => $color || 'rgba(200,200,200,0.7)'};
  white-space: nowrap;
`;

const ArticleTitle = styled.div`
  font-family: ${({ theme }) => theme.fonts.body};
  font-size: 0.88rem;
  line-height: 1.3;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
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
  const articles = feedQuery.data ?? [];
  const getTitle = useShortTitles(articles);

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
      ) : !articles.length ? (
        <EmptyState>No articles yet</EmptyState>
      ) : (
        <ArticlesList>
          {articles.map(article => (
            <ArticleRow
              key={article.id}
              href={article.url}
              target="_blank"
              rel="noopener noreferrer"
              onClick={() => handleArticleClick(article.id)}
            >
              <ArticleTitle data-halo="body">
                {getTitle(article.id, article.title)}
              </ArticleTitle>
              <CategoryPill $color={CATEGORY_COLORS[article.category] || 'rgba(200,200,200,0.7)'}>
                {CATEGORY_LABELS[article.category] || article.category}
              </CategoryPill>
            </ArticleRow>
          ))}
        </ArticlesList>
      )}
    </Panel>
  );
}
