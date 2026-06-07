import { useState } from 'react';
import styled from 'styled-components';
import { reducedMotion } from '../styles/animations';
import { JournalBook } from '../components/journal/JournalBook';
import { getSavedTodayCount, getTodayLocalDate } from '../services/savedToday';

// ── Constants ────────────────────────────────────────────────────────────

const DISMISSED_KEY = 'news.savedTodayPromptDismissed';

function isDismissedToday(): boolean {
  try {
    return localStorage.getItem(DISMISSED_KEY) === getTodayLocalDate();
  } catch {
    return false;
  }
}

function setDismissedToday(): void {
  try {
    localStorage.setItem(DISMISSED_KEY, getTodayLocalDate());
  } catch {
    // private-mode safety
  }
}

// ── Styled components ────────────────────────────────────────────────────

const NudgeBanner = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 16px;
  margin-bottom: 12px;
  border-radius: 16px;
  background: ${({ theme }) => theme.colors.overlay};
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  font-size: 0.8rem;
  letter-spacing: 0.04em;

  @media (prefers-reduced-motion: no-preference) {
    animation: nudge-in 0.2s ease;
  }

  @keyframes nudge-in {
    from { opacity: 0; transform: translateY(-4px); }
    to   { opacity: 1; transform: translateY(0); }
  }
`;

const NudgeText = styled.span`
  opacity: 0.85;
  line-height: 1.5;
`;

const DismissButton = styled.button`
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 44px;
  min-width: 44px;
  border-radius: 999px;
  padding: 6px 10px;
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  background: transparent;
  color: ${({ theme }) => theme.colors.textPrimary};
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.75rem;
  cursor: pointer;
  flex-shrink: 0;
  opacity: 0.7;
  transition: opacity 0.2s ease;
  ${reducedMotion}

  &:hover { opacity: 1; }
  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: 2px;
  }
`;

// ── Component ────────────────────────────────────────────────────────────

function SavedTodayNudge() {
  const count = getSavedTodayCount();
  const [dismissed, setDismissed] = useState(() => isDismissedToday());

  if (count === 0 || dismissed) return null;

  const plural = count === 1 ? 'read' : 'reads';

  function handleDismiss() {
    setDismissedToday();
    setDismissed(true);
  }

  return (
    <NudgeBanner role="status" aria-live="polite">
      <NudgeText>
        You saved {count} {plural} today — note one?
      </NudgeText>
      <DismissButton
        type="button"
        aria-label="Dismiss saved reads nudge"
        onClick={handleDismiss}
      >
        ✕
      </DismissButton>
    </NudgeBanner>
  );
}

export function ReflectPage() {
  return (
    <>
      <SavedTodayNudge />
      <JournalBook />
    </>
  );
}
