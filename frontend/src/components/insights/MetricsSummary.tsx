import styled from 'styled-components';

import { useMetricsOverview } from '../../hooks/useMetricsOverview';

const Card = styled.div`
  background: rgba(255, 255, 255, 0.9);
  border-radius: 24px;
  padding: 24px;
  box-shadow: ${({ theme }) => theme.shadows.soft};
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 16px;
`;

const Metric = styled.div`
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 0.9rem;

  span.value {
    font-size: 1.4rem;
    font-family: ${({ theme }) => theme.fonts.heading};
  }
`;

export function MetricsSummary() {
  const { data } = useMetricsOverview();
  const volumeLabel = data ? `Training Volume (${data.training_volume_window_days}d)` : 'Training Volume';
  return (
    <Card>
      <Metric>
        <label>{volumeLabel}</label>
        <span className="value">{data ? `${data.training_volume_hours.toFixed(1)} h` : '—'}</span>
      </Metric>
      <Metric>
        <label>Avg Load</label>
        <span className="value">{data?.training_load_avg?.toFixed(0) ?? '—'}</span>
      </Metric>
      <Metric>
        <label>HRV Trend</label>
        <span className="value">{data?.hrv_trend_ms.at(-1)?.value?.toFixed(0) ?? '—'} ms</span>
      </Metric>
      <Metric>
        <label>Resting HR</label>
        <span className="value">{data?.rhr_trend_bpm.at(-1)?.value?.toFixed(0) ?? '—'} bpm</span>
      </Metric>
    </Card>
  );
}
