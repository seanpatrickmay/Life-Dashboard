import styled from 'styled-components';

import { LilyPadsDashboard } from '../components/lilypad/LilyPadsDashboard';

const Grid = styled.div`
  display: grid;
  gap: clamp(20px, 3vw, 32px);
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
`;

export function DashboardPage() {
  return (
    <Grid>
      <LilyPadsDashboard />
    </Grid>
  );
}
