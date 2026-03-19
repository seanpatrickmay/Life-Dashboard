import styled from 'styled-components';

import { ReadinessCard } from '../components/insights/ReadinessCard';
import { LifeContextPanel } from '../components/insights/LifeContextPanel';
import { InsightHistory } from '../components/insights/InsightHistory';
import { fadeUp, reducedMotion } from '../styles/animations';

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
      <ReadinessCard />
      <LifeContextPanel />
      <InsightHistory />
    </Page>
  );
}
