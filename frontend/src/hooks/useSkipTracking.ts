import { useEffect, useRef, useCallback } from 'react';
import { recordSurfaced } from '../services/interestProfile';

/**
 * Track which articles are visible in the viewport using Intersection Observer
 * and Page Visibility API. Records surfaced articles for skip penalty calculation.
 *
 * Only records when the page is actually visible (not a background tab).
 */
export function useSkipTracking(
  articles: Array<{ id: string; category: string }>,
  containerRef: React.RefObject<HTMLElement | null>,
) {
  const observerRef = useRef<IntersectionObserver | null>(null);
  const visibleRef = useRef(new Set<string>());

  const flushVisible = useCallback(() => {
    if (document.hidden) return;
    for (const id of visibleRef.current) {
      const article = articles.find(a => a.id === id);
      if (article) {
        recordSurfaced(article.id, article.category);
      }
    }
  }, [articles]);

  useEffect(() => {
    if (!containerRef.current) return;

    observerRef.current = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          const id = (entry.target as HTMLElement).dataset.articleId;
          if (!id) continue;
          if (entry.isIntersecting) {
            visibleRef.current.add(id);
          } else {
            visibleRef.current.delete(id);
          }
        }
      },
      { root: null, threshold: 0.5 },
    );

    // Observe all article elements with data-article-id
    const elements = containerRef.current.querySelectorAll('[data-article-id]');
    for (const el of elements) {
      observerRef.current.observe(el);
    }

    // Flush on visibility change (tab becomes hidden = flush what was visible)
    const handleVisibilityChange = () => {
      if (!document.hidden) return;
      flushVisible();
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);

    // Periodic flush every 60 seconds while visible
    const interval = setInterval(() => {
      if (!document.hidden) flushVisible();
    }, 60_000);

    return () => {
      observerRef.current?.disconnect();
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      clearInterval(interval);
      flushVisible();
    };
  }, [containerRef, flushVisible]);
}
