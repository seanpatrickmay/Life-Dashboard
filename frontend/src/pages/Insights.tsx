import styled, { keyframes } from 'styled-components';

import { ReadinessCard } from '../components/insights/ReadinessCard';
import { InsightHistory } from '../components/insights/InsightHistory';

const fadeUp = keyframes`
  from { opacity: 0; transform: translateY(18px); }
  to   { opacity: 1; transform: translateY(0); }
`;

const Page = styled.div`
  display: flex;
  flex-direction: column;
  gap: clamp(24px, 4vw, 40px);
  margin-top: clamp(16px, 4vh, 48px);
  animation: ${fadeUp} 0.5s ease-out both;
`;

export function InsightsPage() {
  return (
    <Page>
      <ReadinessCard />
      <InsightHistory />
    </Page>
  );
}
