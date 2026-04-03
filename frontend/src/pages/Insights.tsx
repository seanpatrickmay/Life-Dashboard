import styled from 'styled-components';

import { ReadinessCard } from '../components/insights/ReadinessCard';
import { LifeContextPanel } from '../components/insights/LifeContextPanel';
import { InsightHistory } from '../components/insights/InsightHistory';
import { InsightRelatedArticle } from '../components/insights/InsightRelatedArticle';
import { fadeUp, reducedMotion } from '../styles/animations';

const Title = styled.h1`
  margin: 0;
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 1rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
`;

const Page = styled.div`
  display: flex;
  flex-direction: column;
  gap: clamp(14px, 2.5vw, 22px);
  margin-top: clamp(16px, 4vh, 48px);
  animation: ${fadeUp} 0.5s ease-out both;
  ${reducedMotion}
`;

export function InsightsPage() {
  return (
    <Page>
      <Title data-halo="heading">Insights</Title>
      <ReadinessCard />
      <InsightRelatedArticle />
      <LifeContextPanel />
      <InsightHistory />
    </Page>
  );
}
