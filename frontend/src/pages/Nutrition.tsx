import { useState, useCallback } from 'react';
import styled from 'styled-components';

import { Card } from '../components/common/Card';
import { NutritionDashboard } from '../components/nutrition/NutritionDashboard';
import { MenuPanel } from '../components/nutrition/MenuPanel';
import { GoalsPanel } from '../components/nutrition/GoalsPanel';
import { FoodManager } from '../components/nutrition/FoodManager';
import { fadeUp, reducedMotion } from '../styles/animations';

const Page = styled.div`
  display: flex;
  flex-direction: column;
  gap: clamp(18px, 3vw, 28px);
  margin-top: clamp(16px, 4vh, 48px);
  animation: ${fadeUp} 0.5s ease-out both;
  ${reducedMotion}
`;

const TopGrid = styled.div`
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: clamp(14px, 2.5vw, 24px);
  align-items: start;

  @media (max-width: 860px) {
    grid-template-columns: 1fr;
  }
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
  font-size: 0.8rem;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  padding: 0;
  cursor: pointer;

  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: 2px;
  }
`;

const SectionChevron = styled.span<{ $open: boolean }>`
  display: inline-block;
  transition: transform 0.2s ease;
  transform: rotate(${({ $open }) => ($open ? '90deg' : '0deg')});
  font-size: 0.7rem;
  opacity: 0.5;

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

const SectionHeader = styled(Card)`
  padding: clamp(12px, 2vw, 16px) clamp(14px, 2vw, 20px);
`;

const STORAGE_KEY = 'nutrition-sections';

function readPersistedSections(): { goals: boolean; foods: boolean } {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch { /* ignore */ }
  return { goals: false, foods: false };
}

function persistSections(goals: boolean, foods: boolean) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify({ goals, foods }));
}

export function NutritionPage() {
  const persisted = readPersistedSections();
  const [goalsOpen, setGoalsOpen] = useState(persisted.goals);
  const [foodsOpen, setFoodsOpen] = useState(persisted.foods);

  const toggleGoals = useCallback(() => {
    setGoalsOpen(prev => {
      const next = !prev;
      persistSections(next, foodsOpen);
      return next;
    });
  }, [foodsOpen]);

  const toggleFoods = useCallback(() => {
    setFoodsOpen(prev => {
      const next = !prev;
      persistSections(goalsOpen, next);
      return next;
    });
  }, [goalsOpen]);

  return (
    <Page>
      <TopGrid>
        <NutritionDashboard />
        <MenuPanel />
      </TopGrid>

      <div>
        <SectionHeader>
          <SectionToggle
            type="button"
            onClick={toggleGoals}
            aria-expanded={goalsOpen}
          >
            <span data-halo="heading">Nutrient Goals</span>
            <SectionChevron $open={goalsOpen}>▶</SectionChevron>
          </SectionToggle>
        </SectionHeader>
        <CollapsibleWrapper $open={goalsOpen}>
          <CollapsibleInner>
            <GoalsPanel />
          </CollapsibleInner>
        </CollapsibleWrapper>
      </div>

      <div>
        <SectionHeader>
          <SectionToggle
            type="button"
            onClick={toggleFoods}
            aria-expanded={foodsOpen}
          >
            <span data-halo="heading">Food Manager</span>
            <SectionChevron $open={foodsOpen}>▶</SectionChevron>
          </SectionToggle>
        </SectionHeader>
        <CollapsibleWrapper $open={foodsOpen}>
          <CollapsibleInner>
            <FoodManager />
          </CollapsibleInner>
        </CollapsibleWrapper>
      </div>
    </Page>
  );
}
