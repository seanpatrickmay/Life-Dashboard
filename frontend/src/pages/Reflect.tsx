import { useState } from 'react';
import styled from 'styled-components';
import { reducedMotion } from '../styles/animations';
import { JournalBook } from '../components/journal/JournalBook';
import { getSavedTodayCount, getTodayLocalDate } from '../services/savedToday';
import { pixelWell } from '../theme/surfaces';
import { PixelButton } from '../components/common/PixelButton';

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
  ${pixelWell}
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 16px;
  margin-bottom: 12px;
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

const DismissButton = styled(PixelButton).attrs({ variant: 'ghost' })`
  min-height: 44px;
  min-width: 44px;
  padding: 6px 10px;
  font-size: 0.75rem;
  flex-shrink: 0;
  ${reducedMotion}
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
