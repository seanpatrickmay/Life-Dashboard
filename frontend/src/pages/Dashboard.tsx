import styled from 'styled-components';

import { MonetChatPanel } from '../components/dashboard/MonetChatPanel';
import { DashboardUpcomingEvents } from '../components/dashboard/DashboardUpcomingEvents';
import { DashboardNewsFeed } from '../components/dashboard/DashboardNewsFeed';
import { TodoScrollPad } from '../components/todo/TodoScrollPad';

const Grid = styled.div`
  display: grid;
  gap: clamp(20px, 3vw, 32px);
  grid-template-columns: repeat(2, 1fr);
  grid-template-rows: auto auto;
  align-items: start;
  margin-top: clamp(24px, 6vh, 84px);

  @media (max-width: 860px) {
    grid-template-columns: 1fr;
  }
`;

export function DashboardPage() {
  return (
    <Grid>
      <MonetChatPanel />
      <TodoScrollPad />
      <DashboardNewsFeed />
      <DashboardUpcomingEvents />
    </Grid>
  );
}
