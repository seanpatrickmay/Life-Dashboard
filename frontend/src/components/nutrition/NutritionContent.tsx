import { useState, useCallback, useMemo } from 'react';
import styled from 'styled-components';

import { MacroHero } from './MacroHero';
import { MicronutrientPanel } from './MicronutrientPanel';
import { MenuPanel } from './MenuPanel';
import { GoalsPanel } from './GoalsPanel';
import { QuickLogPanel } from './QuickLogPanel';
import { useNutritionHistory } from '../../hooks/useNutritionIntake';

/* ── Collapsible section ── */

const SectionCard = styled.div`
  border-radius: 16px;
  background: ${({ theme }) => theme.colors.overlay};
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  overflow: hidden;
`;

const SectionToggle = styled.button`
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  background: none;
  border: none;
  color: inherit;
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.68rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  padding: clamp(12px, 1.5vw, 16px) clamp(14px, 2vw, 20px);
  cursor: pointer;

  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: -2px;
  }
`;

const ToggleLeft = styled.div`
  display: flex;
  align-items: center;
  gap: 10px;
`;

const Chevron = styled.span<{ $open: boolean }>`
  display: inline-block;
  transition: transform 0.2s ease;
  transform: rotate(${({ $open }) => ($open ? '90deg' : '0deg')});
  font-size: 0.6rem;
  opacity: 0.4;

  @media (prefers-reduced-motion: reduce) {
    transition-duration: 0.01ms;
  }
`;

const CollapsibleWrapper = styled.div<{ $open: boolean }>`
  display: grid;
  grid-template-rows: ${({ $open }) => ($open ? '1fr' : '0fr')};
  transition: grid-template-rows 0.3s ease;

  @media (prefers-reduced-motion: reduce) {
    transition-duration: 0.01ms;
  }
`;

const CollapsibleInner = styled.div`
  overflow: hidden;
`;

const SectionContent = styled.div`
  padding: 0 clamp(14px, 2vw, 20px) clamp(14px, 2vw, 20px);
`;

/* ── 14-Day Averages ── */

const CALORIE_SLUG = 'calories';

const MACRO_COLORS: Record<string, string> = {
  protein: '#FFC075',
  carbohydrate: '#BF6BAB',
  fat: '#C2D5FF',
  fiber: '#82dcb8',
};

const AvgGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;

  @media (max-width: 768px) {
    grid-template-columns: repeat(2, 1fr);
  }

  @media (max-width: 480px) {
    grid-template-columns: 1fr;
  }
`;

const AvgCard = styled.div<{ $accent: string }>`
  border-radius: 14px;
  padding: clamp(10px, 1.5vw, 14px);
  background: ${({ $accent }) => `${$accent}0A`};
  border: 1px solid ${({ $accent }) => `${$accent}26`};
`;

const AvgLabel = styled.div`
  font-size: 0.55rem;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  opacity: 0.5;
  margin-bottom: 4px;
`;

const AvgValue = styled.div<{ $accent: string }>`
  font-size: 1rem;
  font-weight: bold;
  color: ${({ $accent }) => $accent};
`;

const AvgGoal = styled.span`
  font-size: 0.6rem;
  opacity: 0.4;
  font-weight: normal;
  margin-left: 4px;
`;

const AvgPct = styled.div`
  font-size: 0.5rem;
  opacity: 0.35;
  margin-top: 6px;
  text-align: right;
`;

const AvgTrack = styled.div`
  height: 4px;
  background: ${({ theme }) => theme.colors.overlay};
  border-radius: 2px;
  overflow: hidden;
  margin-top: 6px;
`;

const AvgFill = styled.div<{ $pct: number; $accent: string }>`
  width: ${({ $pct }) => Math.min($pct, 100)}%;
  height: 100%;
  background: ${({ $accent }) => $accent};
  border-radius: 2px;
  transition: width 0.4s ease;
`;

const AvgEmpty = styled.p`
  font-size: 0.8rem;
  color: ${({ theme }) => theme.colors.textSecondary};
  margin: 0;
`;

function AveragesContent() {
  const { data } = useNutritionHistory();
  const macros = useMemo(
    () =>
      (data?.nutrients ?? []).filter(
        (n) => n.group === 'macro' && n.slug !== CALORIE_SLUG
      ),
    [data]
  );

  if (macros.length === 0) {
    return <AvgEmpty>No history data available yet.</AvgEmpty>;
  }

  const fmt = (v: number) =>
    v >= 1000 ? v.toLocaleString(undefined, { maximumFractionDigits: 0 }) : String(Math.round(v));

  return (
    <AvgGrid>
      {macros.map((n) => {
        const accent = MACRO_COLORS[n.slug] ?? '#aaa';
        const pct = n.goal ? ((n.average_amount ?? 0) / n.goal) * 100 : 0;
        return (
          <AvgCard key={n.slug} $accent={accent}>
            <AvgLabel>{n.display_name}</AvgLabel>
            <AvgValue $accent={accent}>
              {fmt(n.average_amount ?? 0)}
              {n.unit}
              {n.goal != null && <AvgGoal>/ {fmt(n.goal)}</AvgGoal>}
            </AvgValue>
            {n.goal != null && (
              <>
                <AvgTrack>
                  <AvgFill $pct={pct} $accent={accent} />
                </AvgTrack>
                <AvgPct>{Math.round(pct)}%</AvgPct>
              </>
            )}
          </AvgCard>
        );
      })}
    </AvgGrid>
  );
}

/* ── State persistence ── */

const STORAGE_KEY = 'nutrition-sections';

type SectionState = {
  meals: boolean;
  micro: boolean;
  averages: boolean;
  goals: boolean;
  quicklog: boolean;
};

const DEFAULTS: SectionState = {
  meals: true,
  micro: false,
  averages: false,
  goals: false,
  quicklog: true,
};

function readPersistedSections(): SectionState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      return { ...DEFAULTS, ...parsed };
    }
  } catch { /* ignore */ }
  return DEFAULTS;
}

function persistSections(state: SectionState) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

/* ── NutritionContent ── */

export function NutritionContent() {
  const [sections, setSections] = useState<SectionState>(readPersistedSections);

  const toggle = useCallback((key: keyof SectionState) => {
    setSections((prev) => {
      const next = { ...prev, [key]: !prev[key] };
      persistSections(next);
      return next;
    });
  }, []);

  return (
    <>
      <MacroHero />

      {/* Quick Log */}
      <SectionCard>
        <SectionToggle
          type="button"
          onClick={() => toggle('quicklog')}
          aria-expanded={sections.quicklog}
        >
          <ToggleLeft>
            <span>Quick Log</span>
          </ToggleLeft>
          <Chevron $open={sections.quicklog}>▶</Chevron>
        </SectionToggle>
        <CollapsibleWrapper $open={sections.quicklog}>
          <CollapsibleInner>
            <SectionContent>
              <QuickLogPanel />
            </SectionContent>
          </CollapsibleInner>
        </CollapsibleWrapper>
      </SectionCard>

      {/* Today's Meals */}
      <SectionCard>
        <SectionToggle
          type="button"
          onClick={() => toggle('meals')}
          aria-expanded={sections.meals}
        >
          <ToggleLeft>
            <span>Today&apos;s Meals</span>
          </ToggleLeft>
          <Chevron $open={sections.meals}>▶</Chevron>
        </SectionToggle>
        <CollapsibleWrapper $open={sections.meals}>
          <CollapsibleInner>
            <SectionContent>
              <MenuPanel />
            </SectionContent>
          </CollapsibleInner>
        </CollapsibleWrapper>
      </SectionCard>

      {/* Vitamins & Minerals */}
      <SectionCard>
        <SectionToggle
          type="button"
          onClick={() => toggle('micro')}
          aria-expanded={sections.micro}
        >
          <ToggleLeft>
            <span>Vitamins &amp; Minerals</span>
          </ToggleLeft>
          <Chevron $open={sections.micro}>▶</Chevron>
        </SectionToggle>
        <CollapsibleWrapper $open={sections.micro}>
          <CollapsibleInner>
            <SectionContent>
              <MicronutrientPanel />
            </SectionContent>
          </CollapsibleInner>
        </CollapsibleWrapper>
      </SectionCard>

      {/* 14-Day Averages */}
      <SectionCard>
        <SectionToggle
          type="button"
          onClick={() => toggle('averages')}
          aria-expanded={sections.averages}
        >
          <ToggleLeft>
            <span>14-Day Averages</span>
          </ToggleLeft>
          <Chevron $open={sections.averages}>▶</Chevron>
        </SectionToggle>
        <CollapsibleWrapper $open={sections.averages}>
          <CollapsibleInner>
            <SectionContent>
              <AveragesContent />
            </SectionContent>
          </CollapsibleInner>
        </CollapsibleWrapper>
      </SectionCard>

      {/* Nutrient Goals */}
      <SectionCard>
        <SectionToggle
          type="button"
          onClick={() => toggle('goals')}
          aria-expanded={sections.goals}
        >
          <ToggleLeft>
            <span>Nutrient Goals</span>
          </ToggleLeft>
          <Chevron $open={sections.goals}>▶</Chevron>
        </SectionToggle>
        <CollapsibleWrapper $open={sections.goals}>
          <CollapsibleInner>
            <GoalsPanel />
          </CollapsibleInner>
        </CollapsibleWrapper>
      </SectionCard>
    </>
  );
}
