import { useCallback, useRef, type RefObject } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import styled from 'styled-components';

import { ReadinessCard } from '../components/insights/ReadinessCard';
import { InsightHistory } from '../components/insights/InsightHistory';
import { NutritionContent } from '../components/nutrition/NutritionContent';
import { fadeUp, reducedMotion } from '../styles/animations';

/* ── Layout ── */

const Page = styled.div`
  display: flex;
  flex-direction: column;
  gap: clamp(14px, 2.5vw, 22px);
  margin-top: clamp(16px, 4vh, 48px);
  animation: ${fadeUp} 0.5s ease-out both;
  ${reducedMotion}
`;

/* ── Back link ── */

const BackLink = styled(Link)`
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 0.7rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: ${({ theme }) => theme.colors.textSecondary};
  text-decoration: none;
  opacity: 0.7;
  transition: opacity 0.15s ease;

  &:hover {
    opacity: 1;
  }

  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: 2px;
    border-radius: 3px;
  }
`;

/* ── Sticky sub-nav ── */

const SubNavWrapper = styled.div`
  position: sticky;
  top: 0;
  z-index: 20;
  background: ${({ theme }) =>
    theme.mode === 'dark'
      ? 'rgba(20, 28, 46, 0.82)'
      : 'rgba(255, 255, 255, 0.72)'};
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  padding: 6px 0;
  margin: 0 -4px;
`;

const TabList = styled.div`
  display: flex;
  gap: 4px;
  background: ${({ theme }) => theme.colors.overlay};
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  border-radius: 12px;
  padding: 4px;
`;

const Tab = styled.button<{ $active: boolean }>`
  flex: 1;
  background: ${({ $active, theme }) =>
    $active ? theme.colors.accentSubtle : 'transparent'};
  border: none;
  border-bottom: ${({ $active, theme }) =>
    $active ? `2px solid ${theme.colors.accent}` : '2px solid transparent'};
  border-radius: 9px;
  color: ${({ $active, theme }) =>
    $active ? theme.colors.accent : theme.colors.textSecondary};
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.68rem;
  font-weight: ${({ $active }) => ($active ? 600 : 400)};
  letter-spacing: 0.12em;
  text-transform: uppercase;
  padding: 8px 16px;
  min-height: 44px;
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease;

  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: 2px;
  }

  @media (prefers-reduced-motion: reduce) {
    transition-duration: 0.01ms;
  }
`;

/* ── Tab panel containers ── */

const TabPanel = styled.div`
  display: flex;
  flex-direction: column;
  gap: clamp(14px, 2.5vw, 22px);
`;

/* ── BodyPage ── */

type BodyTab = 'health' | 'nutrition';

const VALID_TABS: ReadonlySet<string> = new Set(['health', 'nutrition']);

const TABS: readonly BodyTab[] = ['health', 'nutrition'];

export function BodyPage() {
  const [searchParams, setSearchParams] = useSearchParams();

  const rawTab = searchParams.get('tab') ?? 'health';
  const activeTab: BodyTab = VALID_TABS.has(rawTab) ? (rawTab as BodyTab) : 'health';

  const healthRef = useRef<HTMLButtonElement>(null);
  const nutritionRef = useRef<HTMLButtonElement>(null);
  const tabButtonRefs: Record<BodyTab, RefObject<HTMLButtonElement | null>> = {
    health: healthRef,
    nutrition: nutritionRef,
  };

  const switchTab = useCallback(
    (tab: BodyTab) => {
      setSearchParams(tab === 'health' ? {} : { tab }, { replace: true });
    },
    [setSearchParams]
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLDivElement>) => {
      const currentIndex = TABS.indexOf(activeTab);
      let nextIndex: number | null = null;

      if (e.key === 'ArrowRight') {
        nextIndex = (currentIndex + 1) % TABS.length;
      } else if (e.key === 'ArrowLeft') {
        nextIndex = (currentIndex - 1 + TABS.length) % TABS.length;
      } else if (e.key === 'Home') {
        nextIndex = 0;
      } else if (e.key === 'End') {
        nextIndex = TABS.length - 1;
      }

      if (nextIndex !== null) {
        e.preventDefault();
        const nextTab = TABS[nextIndex];
        switchTab(nextTab);
        tabButtonRefs[nextTab].current?.focus();
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [activeTab, switchTab, healthRef, nutritionRef]
  );

  return (
    <Page>
      <BackLink to="/">‹ Today</BackLink>

      <SubNavWrapper>
        <TabList role="tablist" aria-label="Body sections" onKeyDown={handleKeyDown}>
          <Tab
            ref={healthRef}
            role="tab"
            $active={activeTab === 'health'}
            aria-selected={activeTab === 'health'}
            aria-controls="body-panel-health"
            id="body-tab-health"
            tabIndex={activeTab === 'health' ? 0 : -1}
            onClick={() => switchTab('health')}
          >
            Health
          </Tab>
          <Tab
            ref={nutritionRef}
            role="tab"
            $active={activeTab === 'nutrition'}
            aria-selected={activeTab === 'nutrition'}
            aria-controls="body-panel-nutrition"
            id="body-tab-nutrition"
            tabIndex={activeTab === 'nutrition' ? 0 : -1}
            onClick={() => switchTab('nutrition')}
          >
            Nutrition
          </Tab>
        </TabList>
      </SubNavWrapper>

      {activeTab === 'health' && (
        <TabPanel
          role="tabpanel"
          id="body-panel-health"
          aria-labelledby="body-tab-health"
        >
          <ReadinessCard />
          <InsightHistory />
        </TabPanel>
      )}

      {activeTab === 'nutrition' && (
        <TabPanel
          role="tabpanel"
          id="body-panel-nutrition"
          aria-labelledby="body-tab-nutrition"
        >
          <NutritionContent />
        </TabPanel>
      )}
    </Page>
  );
}
