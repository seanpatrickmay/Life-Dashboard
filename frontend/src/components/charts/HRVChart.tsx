import { useMemo } from 'react';
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid, type TooltipProps } from 'recharts';
import styled, { useTheme } from 'styled-components';

import { useMetricsOverview } from '../../hooks/useMetricsOverview';
import { getChartTheme } from '../../theme/rechartsTheme';
import { Card } from '../common/Card';
import type { MonetTheme } from '../../theme/monetTheme';

export function HRVChart() {
  const { data } = useMetricsOverview(14);
  const appTheme = useTheme() as MonetTheme;
  const chart = getChartTheme(appTheme.mode ?? 'light');
  const points = useMemo(() => data?.hrv_trend_ms ?? [], [data]);
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

  const tooltipRenderer = ({ active, payload }: TooltipProps<number, string>) => {
    if (!active || !payload?.length) return null;
    const value = payload[0].value;
    if (typeof value !== 'number') return null;
    return (
      <TooltipLabel>
        {`${value.toFixed(0)} ms`}
      </TooltipLabel>
    );
  };
  return (
    <Card>
      <ChartTitle data-halo="heading">HRV (ms)</ChartTitle>
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={points} margin={{ top: 12, right: 0, left: 0, bottom: 0 }}>
          <CartesianGrid stroke={chart.grid.stroke} strokeDasharray="1 8" opacity={0.4} />
          <XAxis
            dataKey="timestamp"
            axisLine={false}
            tickLine={false}
            ticks={ticks}
            tickFormatter={labelForTick}
            stroke={chart.grid.stroke}
            minTickGap={24}
          />
          <YAxis hide domain={['auto', 'auto']} />
          <Tooltip cursor={false} content={tooltipRenderer} wrapperStyle={{ outline: 'none' }} />
          <Line
            type="monotone"
            dataKey="value"
            stroke={chart.HRV.stroke}
            strokeWidth={2.5}
            dot={false}
            strokeLinecap="round"
          />
        </LineChart>
      </ResponsiveContainer>
    </Card>
  );
}

const ChartTitle = styled.h3`
  margin-bottom: 8px;
`;

const TooltipLabel = styled.div`
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.85rem;
  letter-spacing: 0.12em;
  color: ${({ theme }) => theme.colors.textPrimary};
  text-shadow: ${({ theme }) => theme.tokens?.halo?.body ?? '0 0 2px rgba(0,0,0,0.6)'};
`;
