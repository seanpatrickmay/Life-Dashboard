import styled from 'styled-components';

import { Card } from '../components/common/Card';
import { MonetChatPanel } from '../components/dashboard/MonetChatPanel';
import { DashboardNutritionSnapshot } from '../components/dashboard/DashboardNutritionSnapshot';
import { TodoScrollPad } from '../components/todo/TodoScrollPad';

const Grid = styled.div`
  display: grid;
  gap: clamp(20px, 3vw, 32px);
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
`;

const TodoPanel = styled(Card)`
  display: flex;
  flex-direction: column;
  gap: clamp(12px, 2vw, 18px);
`;

export function DashboardPage() {
  return (
    <Grid>
      <MonetChatPanel />
      <TodoPanel>
        <TodoScrollPad />
      </TodoPanel>
      <DashboardNutritionSnapshot />
    </Grid>
  );
}
