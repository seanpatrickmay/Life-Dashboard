import { useMemo } from 'react';
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import styled from 'styled-components';

import { useMetricsOverview } from '../../hooks/useMetricsOverview';

const Card = styled.div`
  background: rgba(255, 255, 255, 0.9);
  border-radius: 24px;
  padding: 24px;
  box-shadow: ${({ theme }) => theme.shadows.soft};
`;

export function SleepChart() {
  const { data } = useMetricsOverview(14);
  const bars = useMemo(() => data?.sleep_trend_hours ?? [], [data]);
  const ticks = useMemo(() => {
    if (!bars?.length) return [];
    const lastIndex = bars.length - 1;
    const todayTs = bars[lastIndex]?.timestamp;
    const weekIndex = Math.max(0, lastIndex - 7);
    const weekTs = bars[weekIndex]?.timestamp;
    return Array.from(new Set([weekTs, todayTs].filter(Boolean))) as string[];
  }, [bars]);

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
      <h3>Sleep Hours</h3>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={bars}>
          <XAxis
            dataKey="timestamp"
            axisLine={false}
            tickLine={false}
            ticks={ticks}
            tickFormatter={labelForTick}
          />
          <YAxis axisLine={false} tickLine={false} stroke="#f9d776" />
          <Tooltip formatter={(value: number) => `${value.toFixed(1)} h`} labelFormatter={() => ''} />
          <Bar dataKey="value" fill="#f9d776" radius={[8, 8, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </Card>
  );
}
