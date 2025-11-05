import styled from 'styled-components';

import { ReadinessCard } from '../components/insights/ReadinessCard';
import { MetricsSummary } from '../components/insights/MetricsSummary';
import { HRVChart } from '../components/charts/HRVChart';
import { RHRChart } from '../components/charts/RHRChart';
import { LoadChart } from '../components/charts/LoadChart';
import { SleepChart } from '../components/charts/SleepChart';

const Grid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 24px;
`;

export function DashboardPage() {
  return (
    <Grid>
      <ReadinessCard />
      <MetricsSummary />
      <HRVChart />
      <RHRChart />
      <LoadChart />
      <SleepChart />
    </Grid>
  );
}
