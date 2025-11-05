import styled from 'styled-components';

import { InsightHistory } from '../components/insights/InsightHistory';

const Wrapper = styled.div`
  display: flex;
  flex-direction: column;
  gap: 24px;
`;

export function InsightsPage() {
  return (
    <Wrapper>
      <InsightHistory />
    </Wrapper>
  );
}
