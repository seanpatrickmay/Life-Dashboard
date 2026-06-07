import { useState } from 'react';
import styled from 'styled-components';

const DISMISSED_FLAG = 'ld_nav_moved_dismissed';

const Banner = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 16px;
  border-radius: 16px;
  background: ${({ theme }) => theme.colors.overlay};
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  font-size: 0.8rem;
  letter-spacing: 0.04em;
`;

const BannerText = styled.span`
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
  &:hover { opacity: 1; }
  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: 2px;
  }
`;

export function MovedBanner() {
  const [dismissed, setDismissed] = useState(() => {
    try { return localStorage.getItem(DISMISSED_FLAG) === '1'; }
    catch { return false; }
  });

  if (dismissed) return null;

  function handleDismiss() {
    try { localStorage.setItem(DISMISSED_FLAG, '1'); } catch { /* private mode */ }
    setDismissed(true);
  }

  return (
    <Banner role="status" aria-live="polite">
      <BannerText>
        We've simplified to <strong>Today · Read · Reflect</strong>. Insights &amp; Nutrition now
        live under Body, Calendar &amp; Projects open from Today, and account settings are in the{' '}
        <strong>⚙ Settings</strong> menu.
      </BannerText>
      <DismissButton
        type="button"
        aria-label="Dismiss navigation change notice"
        onClick={handleDismiss}
      >
        ✕
      </DismissButton>
    </Banner>
  );
}
