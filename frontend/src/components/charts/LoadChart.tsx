import { useMemo } from 'react';
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import styled from 'styled-components';

import { useMetricsOverview } from '../../hooks/useMetricsOverview';

const Card = styled.div`
  background: rgba(255, 255, 255, 0.9);
  border-radius: 24px;
  padding: 24px;
  box-shadow: ${({ theme }) => theme.shadows.soft};
`;

export function LoadChart() {
  const { data } = useMetricsOverview(14);
  const points = useMemo(() => data?.training_load_trend ?? [], [data]);
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
      <h3>Training Load</h3>
      <ResponsiveContainer width="100%" height={220}>
        <AreaChart data={points}>
          <XAxis
            dataKey="timestamp"
            axisLine={false}
            tickLine={false}
            ticks={ticks}
            tickFormatter={labelForTick}
          />
          <YAxis axisLine={false} tickLine={false} stroke="#9ed0a1" />
          <Tooltip formatter={(value: number) => value.toFixed(0)} labelFormatter={() => ''} />
          <Area type="monotone" dataKey="value" stroke="#9ed0a1" fill="#cfead1" fillOpacity={0.8} />
        </AreaChart>
      </ResponsiveContainer>
    </Card>
  );
}
