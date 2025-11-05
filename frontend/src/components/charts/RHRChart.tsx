import { useMemo } from 'react';
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import styled from 'styled-components';

import { useMetricsOverview } from '../../hooks/useMetricsOverview';

const Card = styled.div`
  background: rgba(255, 255, 255, 0.9);
  border-radius: 24px;
  padding: 24px;
  box-shadow: ${({ theme }) => theme.shadows.soft};
`;

export function RHRChart() {
  const { data } = useMetricsOverview(14);
  const points = useMemo(() => data?.rhr_trend_bpm ?? [], [data]);
  const ticks = useMemo(() => {
    if (!points?.length) return [];
    const lastIndex = points.length - 1;
    const todayTs = points[lastIndex]?.timestamp;
    const weekIndex = Math.max(0, lastIndex - 7);
    const weekTs = points[weekIndex]?.timestamp;
    return Array.from(new Set([weekTs, todayTs].filter(Boolean))) as string[];
  }, [points]);

  const labelForTick = useMemo(() => {
    if (!ticks.length) return () => '';
    const todayValue = ticks[ticks.length - 1];
    const weekValue = ticks[0];
    return (value: string) => {
      if (value === todayValue) {
        const d = new Date(value);
        return `Today (${d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })})`;
      }
      if (value === weekValue) {
        const d = new Date(value);
        return `1 wk ago (${d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })})`;
      }
      return '';
    };
  }, [ticks]);

  return (
    <Card>
      <h3>Resting Heart Rate (bpm)</h3>
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={points}>
          <XAxis
            dataKey="timestamp"
            axisLine={false}
            tickLine={false}
            ticks={ticks}
            tickFormatter={labelForTick}
          />
          <YAxis domain={['auto', 'auto']} axisLine={false} stroke="#f57c73" />
          <Tooltip formatter={(value: number) => `${value?.toFixed?.(0)} bpm`} labelFormatter={() => ''} />
          <Line type="monotone" dataKey="value" stroke="#f57c73" strokeWidth={3} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </Card>
  );
}
