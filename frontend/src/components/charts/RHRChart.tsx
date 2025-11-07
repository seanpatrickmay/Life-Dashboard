import { useMemo } from 'react';
import { Area, AreaChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid } from 'recharts';
import styled, { useTheme } from 'styled-components';

import { useMetricsOverview } from '../../hooks/useMetricsOverview';
import { getChartTheme } from '../../theme/rechartsTheme';
import { Card } from '../common/Card';
import type { MonetTheme } from '../../theme/monetTheme';
import { getStrokePattern } from '../../theme/monetTheme';

export function RHRChart() {
  const { data } = useMetricsOverview(14);
  const appTheme = useTheme() as MonetTheme;
  const chart = getChartTheme(appTheme.mode ?? 'light');
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

  const strokePattern = getStrokePattern('RHR');
  const patternId = `rhr-stroke-pattern`;
  return (
    <Card>
      <h3>Resting Heart Rate (bpm)</h3>
      <ResponsiveContainer width="100%" height={240}>
        <AreaChart data={points}>
          <defs>
            <pattern id={patternId} patternUnits="userSpaceOnUse" width={8} height={8}>
              <image xlinkHref={strokePattern} width={8} height={8} />
            </pattern>
          </defs>
          <XAxis
            dataKey="timestamp"
            axisLine={false}
            tickLine={false}
            ticks={ticks}
            tickFormatter={labelForTick}
          />
          <YAxis domain={['auto', 'auto']} axisLine={false} stroke={chart.grid.stroke} />
          <CartesianGrid stroke={chart.grid.stroke} strokeDasharray="3 3" />
          <Tooltip contentStyle={{ background: chart.tooltip.background, color: chart.tooltip.color }} formatter={(value: number) => `${value?.toFixed?.(0)} bpm`} labelFormatter={() => ''} />
          <Area type="monotone" dataKey="value" stroke={chart.RHR.stroke} strokeWidth={3} fill={`url(#${patternId})`} dot={{ r: 3, stroke: chart.RHR.stroke, strokeWidth: 2, fill: chart.RHR.stroke }} />
          <Line type="monotone" dataKey="value" stroke={chart.RHR.stroke} strokeWidth={3} dot={false} />
        </AreaChart>
      </ResponsiveContainer>
    </Card>
  );
}
