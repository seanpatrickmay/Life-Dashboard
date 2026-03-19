import styled, { keyframes } from 'styled-components';

import { DashboardUpcomingEvents } from '../components/dashboard/DashboardUpcomingEvents';
import { DashboardNewsFeed } from '../components/dashboard/DashboardNewsFeed';
import { TodoScrollPad } from '../components/todo/TodoScrollPad';

const fadeUp = keyframes`
  from {
    opacity: 0;
    transform: translateY(18px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
`;

const Grid = styled.div`
  display: grid;
  gap: clamp(20px, 3vw, 32px);
  grid-template-columns: repeat(3, 1fr);
  align-items: start;
  margin-top: clamp(24px, 6vh, 84px);

  @media (max-width: 1024px) {
    grid-template-columns: 1fr 1fr;
  }

  @media (max-width: 640px) {
    grid-template-columns: 1fr;
  }
`;

const Column = styled.div<{ $delay?: number }>`
  display: flex;
  flex-direction: column;
  gap: clamp(20px, 3vw, 32px);
  animation: ${fadeUp} 0.5s ease-out ${({ $delay }) => ($delay ?? 0) * 0.08}s both;
`;

export function DashboardPage() {
  return (
    <Grid>
      <Column $delay={0}>
        <TodoScrollPad />
      </Column>
      <Column $delay={1}>
        <DashboardUpcomingEvents />
      </Column>
      <Column $delay={2}>
        <DashboardNewsFeed />
      </Column>
    </Grid>
  );
}
