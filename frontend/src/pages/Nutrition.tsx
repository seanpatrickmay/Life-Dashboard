import styled from 'styled-components';

import { NutritionDashboard } from '../components/nutrition/NutritionDashboard';
import { MenuPanel } from '../components/nutrition/MenuPanel';
import { GoalsPanel } from '../components/nutrition/GoalsPanel';
import { FoodManager } from '../components/nutrition/FoodManager';
import { fadeUp, reducedMotion } from '../styles/animations';

const Page = styled.div`
  display: flex;
  flex-direction: column;
  gap: clamp(24px, 4vw, 40px);
  margin-top: clamp(16px, 4vh, 48px);
  animation: ${fadeUp} 0.5s ease-out both;
  ${reducedMotion}
`;

const TopGrid = styled.div`
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: clamp(16px, 3vw, 28px);
  align-items: start;

  @media (max-width: 860px) {
    grid-template-columns: 1fr;
  }
`;

export function NutritionPage() {
  return (
    <Page>
      <TopGrid>
        <NutritionDashboard />
        <MenuPanel />
      </TopGrid>
      <GoalsPanel />
      <FoodManager />
    </Page>
  );
}
