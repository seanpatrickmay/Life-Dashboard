import styled from 'styled-components';
import { ClaudeChatPanel } from '../components/nutrition/ClaudeChatPanel';
import { FoodManager } from '../components/nutrition/FoodManager';
import { GoalsPanel } from '../components/nutrition/GoalsPanel';
import { NutritionDashboard } from '../components/nutrition/NutritionDashboard';
import { MenuPanel } from '../components/nutrition/MenuPanel';

const Layout = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: clamp(18px, 2vw, 28px);
`;

const Column = styled.div`
  display: flex;
  flex-direction: column;
  gap: clamp(18px, 2vw, 24px);
`;

export function NutritionPage() {
  return (
    <Layout>
      <Column>
        <ClaudeChatPanel />
        <MenuPanel />
        <FoodManager />
      </Column>
      <Column>
        <NutritionDashboard />
        <GoalsPanel />
      </Column>
    </Layout>
  );
}
