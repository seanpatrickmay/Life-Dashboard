import { useMemo } from 'react';
import styled from 'styled-components';

import { useNewsFeed } from '../../hooks/useNewsFeed';
import { type NewsArticle } from '../../services/newsFeedService';

const Card = styled.a`
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: clamp(12px, 1.5vw, 16px);
  border-radius: ${({ theme }) => theme.radii?.card ?? '16px'};
  background: ${({ theme }) => theme.colors.surfaceRaised};
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  text-decoration: none;
  color: inherit;
  transition: border-color 0.15s ease, transform 0.15s ease;
  cursor: pointer;

  &:hover {
    transform: translateY(-1px);
    border-color: ${({ theme }) => theme.palette?.pond?.['200'] ?? '#7ED7C4'};
  }
  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: 2px;
  }
`;

const Label = styled.div`
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.65rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  opacity: 0.4;
`;

const Title = styled.div`
  font-family: ${({ theme }) => theme.fonts.body};
  font-size: 0.88rem;
  line-height: 1.35;
`;

const Meta = styled.div`
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.75rem;
  opacity: 0.35;
  letter-spacing: 0.04em;
  text-transform: uppercase;
`;

const Dot = styled.span<{ $color: string }>`
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: ${({ $color }) => $color};
  flex-shrink: 0;
`;

const Annotation = styled.div`
  font-size: 0.72rem;
  font-style: italic;
  opacity: 0.45;
  line-height: 1.3;
`;

const CATEGORY_COLORS: Record<string, string> = {
  tech: 'rgba(120, 180, 255, 0.85)',
  science: 'rgba(130, 220, 180, 0.85)',
  world: 'rgba(255, 180, 120, 0.85)',
  culture: 'rgba(220, 160, 255, 0.85)',
  history: 'rgba(255, 210, 130, 0.85)',
  business: 'rgba(180, 200, 240, 0.85)',
  wikipedia: 'rgba(200, 200, 200, 0.85)',
};

// Categories most relevant to insights/health context
const INSIGHT_CATEGORIES = new Set(['science', 'tech']);

export function InsightRelatedArticle() {
  const { curatedQuery, annotationsQuery, markRead } = useNewsFeed();
  const annotations = annotationsQuery.data ?? {};

  const article: NewsArticle | null = useMemo(() => {
    const allArticles = [
      ...(curatedQuery.data?.picks ?? []),
      ...(curatedQuery.data?.more ?? []),
    ];

    // Find the highest-scored article from insight-relevant categories
    return allArticles
      .filter(a => INSIGHT_CATEGORIES.has(a.category))
      .sort((a, b) => b.relevanceScore - a.relevanceScore)[0] ?? null;
  }, [curatedQuery.data]);

  if (!article) return null;

  return (
    <Card
      href={article.url}
      target="_blank"
      rel="noopener noreferrer"
      onClick={() => markRead(article.id)}
    >
      <Label>Related Reading</Label>
      <Title data-halo="body">{article.title}</Title>
      {annotations[article.id] && (
        <Annotation>{annotations[article.id]}</Annotation>
      )}
      <Meta>
        <Dot $color={CATEGORY_COLORS[article.category] || 'rgba(200,200,200,0.85)'} />
        {article.sourceName}
      </Meta>
    </Card>
  );
}
