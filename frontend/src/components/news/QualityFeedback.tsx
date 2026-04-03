import { useState, useCallback } from 'react';
import styled, { keyframes } from 'styled-components';

import { recordRead } from '../../services/interestProfile';
import { reducedMotion } from '../../styles/animations';
import { type NewsArticle } from '../../services/newsFeedService';

interface QualityFeedbackProps {
  article: NewsArticle;
  onDismiss: () => void;
}

const slideUp = keyframes`
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
`;

const slideOut = keyframes`
  from { opacity: 1; transform: translateY(0); }
  to { opacity: 0; transform: translateY(-8px); }
`;

const Container = styled.div<{ $exiting: boolean }>`
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-radius: 12px;
  background: ${({ theme }) => theme.colors.surfaceRaised};
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  animation: ${({ $exiting }) => $exiting ? slideOut : slideUp} 0.25s ease-out both;
  ${reducedMotion}
`;

const Prompt = styled.span`
  font-size: 0.78rem;
  opacity: 0.6;
  flex: 1;
`;

const FeedbackButton = styled.button<{ $variant: 'more' | 'less' }>`
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.68rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  padding: 6px 14px;
  border-radius: 999px;
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  background: ${({ theme, $variant }) =>
    $variant === 'more'
      ? (theme.palette?.pond?.['200'] ?? '#7ED7C4') + '18'
      : 'transparent'};
  color: ${({ theme, $variant }) =>
    $variant === 'more'
      ? (theme.palette?.pond?.['200'] ?? '#7ED7C4')
      : 'inherit'};
  cursor: pointer;
  transition: all 0.15s ease;
  opacity: 0.7;
  min-width: 44px;
  min-height: 44px;
  display: inline-flex;
  align-items: center;
  justify-content: center;

  &:hover {
    opacity: 1;
    transform: scale(1.05);
  }
  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: 2px;
  }
`;

const FEEDBACK_KEY = 'ld_feedback_state';

type FeedbackState = {
  lastShownAt: string;
  readsToday: number;
  lastResetDate: string;
};

function loadFeedbackState(): FeedbackState {
  try {
    const raw = localStorage.getItem(FEEDBACK_KEY);
    if (raw) return JSON.parse(raw);
  } catch { /* ignore */ }
  return {
    lastShownAt: '',
    readsToday: 0,
    lastResetDate: new Date().toDateString(),
  };
}

function saveFeedbackState(state: FeedbackState): void {
  localStorage.setItem(FEEDBACK_KEY, JSON.stringify(state));
}

/** Returns true if we should show a feedback prompt (after 3+ reads today). */
export function shouldShowFeedback(): boolean {
  const state = loadFeedbackState();
  const today = new Date().toDateString();

  if (state.lastResetDate !== today) {
    saveFeedbackState({ lastShownAt: '', readsToday: 0, lastResetDate: today });
    return false;
  }

  // Show after 3 reads, but only once per session
  if (state.readsToday >= 3 && !state.lastShownAt) return true;
  return false;
}

/** Increment the read counter for today. */
export function recordFeedbackRead(): void {
  const state = loadFeedbackState();
  const today = new Date().toDateString();

  if (state.lastResetDate !== today) {
    saveFeedbackState({ lastShownAt: '', readsToday: 1, lastResetDate: today });
  } else {
    state.readsToday += 1;
    saveFeedbackState(state);
  }
}

export function QualityFeedback({ article, onDismiss }: QualityFeedbackProps) {
  const [exiting, setExiting] = useState(false);

  const handleFeedback = useCallback((wantMore: boolean) => {
    if (wantMore) {
      // Boost: record an extra "read" for this category to strengthen affinity
      recordRead(article.category, article.sourceName);
      recordRead(article.category, article.sourceName);
    }
    // Mark feedback as shown today
    const state = loadFeedbackState();
    state.lastShownAt = new Date().toISOString();
    saveFeedbackState(state);

    setExiting(true);
    setTimeout(onDismiss, 250);
  }, [article, onDismiss]);

  return (
    <Container $exiting={exiting}>
      <Prompt>More like "{article.title.slice(0, 40)}..."?</Prompt>
      <FeedbackButton $variant="more" onClick={() => handleFeedback(true)}>
        More
      </FeedbackButton>
      <FeedbackButton $variant="less" onClick={() => handleFeedback(false)}>
        Less
      </FeedbackButton>
    </Container>
  );
}
