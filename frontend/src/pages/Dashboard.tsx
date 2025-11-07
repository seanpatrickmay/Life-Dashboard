import styled from 'styled-components';

import { ReadinessCard } from '../components/insights/ReadinessCard';

const Grid = styled.div`
  display: grid;
  gap: clamp(20px, 3vw, 32px);
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
`;

export function DashboardPage() {
  return (
    <Grid>
      <ReadinessCard />
    </Grid>
  );
}
