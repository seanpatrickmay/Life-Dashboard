import { useMemo, useState } from 'react';
import styled from 'styled-components';

import { useNewsFeed } from '../../hooks/useNewsFeed';
import { type NewsArticle } from '../../services/newsFeedService';
import { reducedMotion } from '../../styles/animations';

interface ProjectRelatedReadingProps {
  projectName: string;
  recentFocus?: string;
  todoTexts: string[];
}

const Section = styled.div`
  display: flex;
  flex-direction: column;
  gap: 8px;
`;

const Header = styled.button`
  display: flex;
  align-items: center;
  gap: 8px;
  background: none;
  border: none;
  padding: 2px 0;
  cursor: pointer;
  color: inherit;
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.78rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  opacity: 0.5;
  transition: opacity 0.15s ease;

  &:hover { opacity: 0.8; }
  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: 2px;
  }
`;

const Count = styled.span`
  font-size: 0.65rem;
  opacity: 0.6;
`;

const Chevron = styled.span<{ $open: boolean }>`
  display: inline-block;
  transition: transform 0.2s ease;
  transform: rotate(${({ $open }) => ($open ? '90deg' : '0deg')});
  font-size: 0.65rem;
`;

const List = styled.div<{ $open: boolean }>`
  display: grid;
  grid-template-rows: ${({ $open }) => ($open ? '1fr' : '0fr')};
  transition: grid-template-rows 0.25s ease-out;
  ${reducedMotion}
`;

const ListInner = styled.div`
  overflow: hidden;
  display: flex;
  flex-direction: column;
  gap: 2px;
`;

const ArticleRow = styled.a`
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 8px;
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
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: ${({ $color }) => $color};
  flex-shrink: 0;
`;

const Title = styled.span`
  flex: 1;
  font-size: 0.82rem;
  line-height: 1.3;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
`;

const Annotation = styled.span`
  flex-shrink: 0;
  font-size: 0.65rem;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  opacity: 0.4;
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

function matchesProject(article: NewsArticle, keywords: string[]): boolean {
  if (keywords.length === 0) return false;
  const text = `${article.title} ${article.summary || ''}`.toLowerCase();
  return keywords.some(kw => text.includes(kw));
}

export function ProjectRelatedReading({ projectName, recentFocus, todoTexts }: ProjectRelatedReadingProps) {
  const { curatedQuery, markRead } = useNewsFeed();
  const [open, setOpen] = useState(false);

  const relevantArticles = useMemo(() => {
    const allArticles = [
      ...(curatedQuery.data?.picks ?? []),
      ...(curatedQuery.data?.more ?? []),
    ];

    // Build keywords from project context
    const rawKeywords = [projectName, recentFocus || '', ...todoTexts]
      .join(' ')
      .toLowerCase()
      .split(/\W+/)
      .filter(w => w.length > 3);
    const keywords = [...new Set(rawKeywords)];

    return allArticles
      .filter(a => matchesProject(a, keywords))
      .slice(0, 3);
  }, [curatedQuery.data, projectName, recentFocus, todoTexts]);

  if (relevantArticles.length === 0) return null;

  return (
    <Section>
      <Header onClick={() => setOpen(o => !o)} aria-expanded={open}>
        <Chevron $open={open}>›</Chevron>
        Related Reading
        <Count>({relevantArticles.length})</Count>
      </Header>
      <List $open={open}>
        <ListInner>
          {relevantArticles.map(article => (
            <ArticleRow
              key={article.id}
              href={article.url}
              target="_blank"
              rel="noopener noreferrer"
              onClick={() => markRead(article.id)}
            >
              <Dot $color={CATEGORY_COLORS[article.category] || 'rgba(200,200,200,0.85)'} />
              <Title>{article.title}</Title>
              <Annotation>Related to {projectName}</Annotation>
            </ArticleRow>
          ))}
        </ListInner>
      </List>
    </Section>
  );
}
