import styled from 'styled-components';

import { MonetChatPanel } from '../components/dashboard/MonetChatPanel';
import { DashboardUpcomingEvents } from '../components/dashboard/DashboardUpcomingEvents';
import { DashboardNewsFeed } from '../components/dashboard/DashboardNewsFeed';
import { TodoScrollPad } from '../components/todo/TodoScrollPad';

const Grid = styled.div`
  display: grid;
  gap: clamp(20px, 3vw, 32px);
  grid-template-columns: 1fr 1fr;
  align-items: start;
  margin-top: clamp(24px, 6vh, 84px);

  @media (max-width: 768px) {
    grid-template-columns: 1fr;
  }
`;

const RightColumn = styled.div`
  display: flex;
  flex-direction: column;
  gap: clamp(20px, 3vw, 32px);
`;

export function DashboardPage() {
  return (
    <Grid>
      <MonetChatPanel />
      <RightColumn>
        <TodoScrollPad />
        <DashboardUpcomingEvents />
        <DashboardNewsFeed />
      </RightColumn>
    </Grid>
  );
}
