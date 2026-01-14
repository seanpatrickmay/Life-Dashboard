import { useMemo } from 'react';
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid, type TooltipProps } from 'recharts';
import styled, { useTheme } from 'styled-components';

import { useMetricsOverview } from '../../hooks/useMetricsOverview';
import { getChartTheme } from '../../theme/rechartsTheme';
import { Card } from '../common/Card';
import type { MonetTheme } from '../../theme/monetTheme';

type ChartVariant = 'card' | 'bare';
type ChartProps = {
  variant?: ChartVariant;
};

export function HRVChart({ variant = 'card' }: ChartProps) {
  const { data } = useMetricsOverview(14);
  const appTheme = useTheme() as MonetTheme;
  const chart = getChartTheme(appTheme.mode ?? 'light');
  const axisLabelColor =
    variant === 'bare'
      ? 'rgba(245, 248, 255, 0.92)'
      : appTheme.mode === 'dark'
        ? 'rgba(246, 240, 232, 0.92)'
        : 'rgba(30, 31, 46, 0.92)';
  const tooltipLabelColor =
    variant === 'bare' ? 'rgba(245, 248, 255, 0.95)' : appTheme.colors.textPrimary;
  const points = useMemo(() => data?.hrv_trend_ms ?? [], [data]);
  const labelTicks = useMemo(() => {
    if (!points?.length) return [];
    const lastIndex = points.length - 1;
    const todayTs = points[lastIndex]?.timestamp;
    const weekIndex = Math.max(0, lastIndex - 7);
    const weekTs = points[weekIndex]?.timestamp;
    return Array.from(new Set([weekTs, todayTs].filter(Boolean))) as string[];
  }, [points]);
  const dayTicks = useMemo(
    () => Array.from(new Set(points.map((point) => point.timestamp).filter(Boolean))) as string[],
    [points]
  );

  const labelForTick = useMemo(() => {
    if (!labelTicks.length) return () => '';
    const todayValue = labelTicks[labelTicks.length - 1];
    const weekValue = labelTicks[0];
    return (value: string) => {
      if (value === todayValue) {
        const d = new Date(value);
        return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
      }
      if (value === weekValue) {
        const d = new Date(value);
        return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
      }
      return '';
    };
  }, [labelTicks]);

  const tooltipRenderer = ({ active, payload }: TooltipProps<number, string>) => {
    if (!active || !payload?.length) return null;
    const value = payload[0].value;
    if (typeof value !== 'number') return null;
    return <TooltipLabel $color={tooltipLabelColor}>{`${value.toFixed(0)} ms`}</TooltipLabel>;
  };
  const content = (
    <>
      {variant === 'card' ? <ChartTitle data-halo="heading">HRV (ms)</ChartTitle> : null}
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={points} margin={{ top: 12, right: 12, left: 16, bottom: 22 }}>
          <CartesianGrid stroke={chart.grid.stroke} strokeDasharray="1 8" opacity={0.4} />
          <XAxis
            dataKey="timestamp"
            axisLine={false}
            tickLine={false}
            ticks={dayTicks}
            tickFormatter={labelForTick}
            stroke={axisLabelColor}
            tick={{ fill: axisLabelColor, fontSize: 12, fontWeight: 600 }}
            interval={0}
            height={28}
            tickMargin={10}
            padding={{ left: 8, right: 16 }}
          />
          <YAxis
            axisLine={false}
            tickLine={false}
            width={40}
            stroke={axisLabelColor}
            tick={{ fill: axisLabelColor, fontSize: 12, fontWeight: 600 }}
            domain={['auto', 'auto']}
          />
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
    </>
  );

  if (variant === 'card') {
    return <Card>{content}</Card>;
  }

  return <ChartShell>{content}</ChartShell>;
}

const ChartShell = styled.div`
  width: 100%;
  height: 100%;
`;

const ChartTitle = styled.h3`
  margin-bottom: 8px;
`;

const TooltipLabel = styled.div<{ $color: string }>`
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.85rem;
  letter-spacing: 0.12em;
  color: ${({ $color }) => $color};
  text-shadow: ${({ theme }) => theme.tokens?.halo?.body ?? '0 0 2px rgba(0,0,0,0.6)'};
`;
