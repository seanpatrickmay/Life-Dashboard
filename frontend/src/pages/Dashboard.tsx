import styled, { useTheme } from 'styled-components';

import { DashboardUpcomingEvents } from '../components/dashboard/DashboardUpcomingEvents';
import { DashboardNewsFeed } from '../components/dashboard/DashboardNewsFeed';
import { DashboardNutritionSnapshot } from '../components/dashboard/DashboardNutritionSnapshot';
import { TodoScrollPad } from '../components/todo/TodoScrollPad';
import { useInsight } from '../hooks/useInsight';
import { fadeUp, reducedMotion } from '../styles/animations';
import type { MonetTheme, Moment } from '../theme/monetTheme';

const GREETINGS: Record<Moment, string> = {
  morning: 'Good morning',
  noon: 'Good afternoon',
  twilight: 'Good evening',
  night: 'Good night'
};

const GreetingStrip = styled.div`
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 10px 18px;
  margin-top: clamp(20px, 5vh, 64px);
  margin-bottom: clamp(4px, 1vh, 12px);
  animation: ${fadeUp} 0.5s ease-out both;
  ${reducedMotion}
`;

const GreetingText = styled.h2`
  margin: 0;
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: clamp(1.1rem, 2vw, 1.4rem);
  letter-spacing: 0.08em;
  color: ${({ theme }) => theme.colors.textPrimary};
  text-shadow: 0 2px 10px rgba(10, 18, 40, 0.25);
`;

const DateText = styled.span`
  font-size: clamp(0.7rem, 1vw, 0.82rem);
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: ${({ theme }) => theme.colors.textSecondary};
`;

const ScoreBadge = styled.span`
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 10px;
  border-radius: 20px;
  background: ${({ theme }) => theme.colors.overlay};
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.78rem;
  letter-spacing: 0.06em;
  color: ${({ theme }) => theme.colors.textPrimary};
`;

const Grid = styled.div`
  display: grid;
  gap: clamp(20px, 3vw, 32px);
  grid-template-columns: repeat(3, 1fr);
  align-items: start;

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
  min-width: 0;
  animation: ${fadeUp} 0.5s ease-out ${({ $delay }) => ($delay ?? 0) * 0.08}s both;
  ${reducedMotion}
`;

export function DashboardPage() {
  const theme = useTheme() as MonetTheme;
  const moment = (theme.moment ?? 'morning') as Moment;
  const { data: insight } = useInsight();

  const today = new Date().toLocaleDateString(undefined, {
    weekday: 'long',
    month: 'short',
    day: 'numeric'
  });

  const score = typeof insight?.readiness_score === 'number'
    ? insight.readiness_score.toFixed(0)
    : null;

  return (
    <>
      <GreetingStrip>
        <GreetingText data-halo="heading">{GREETINGS[moment]}</GreetingText>
        <DateText>{today}</DateText>
        {score && <ScoreBadge>Readiness {score}/100</ScoreBadge>}
      </GreetingStrip>
      <Grid>
        <Column $delay={0}>
          <TodoScrollPad />
        </Column>
        <Column $delay={1}>
          <DashboardUpcomingEvents />
        </Column>
        <Column $delay={2}>
          <DashboardNutritionSnapshot />
          <DashboardNewsFeed />
        </Column>
      </Grid>
    </>
  );
}
