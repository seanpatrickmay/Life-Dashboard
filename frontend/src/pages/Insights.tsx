import styled from 'styled-components';

import { ReadinessCard } from '../components/insights/ReadinessCard';
import { InsightHistory } from '../components/insights/InsightHistory';
import { fadeUp, reducedMotion } from '../styles/animations';

const Page = styled.div`
  display: flex;
  flex-direction: column;
  gap: clamp(24px, 4vw, 40px);
  margin-top: clamp(16px, 4vh, 48px);
  animation: ${fadeUp} 0.5s ease-out both;
  ${reducedMotion}
`;

export function InsightsPage() {
  return (
    <Page>
      <ReadinessCard />
      <InsightHistory />
    </Page>
  );
}
