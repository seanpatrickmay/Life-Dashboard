import { useMemo } from 'react';
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid } from 'recharts';
import { useTheme } from 'styled-components';

import { useMetricsOverview } from '../../hooks/useMetricsOverview';
import { getChartTheme } from '../../theme/rechartsTheme';
import { Card } from '../common/Card';
import type { MonetTheme } from '../../theme/monetTheme';
import { getStrokePattern } from '../../theme/monetTheme';

export function LoadChart() {
  const { data } = useMetricsOverview(14);
  const appTheme = useTheme() as MonetTheme;
  const chart = getChartTheme(appTheme.mode ?? 'light');
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

  const strokePattern = getStrokePattern('Load');
  const patternId = `load-stroke-pattern`;
  return (
    <Card>
      <h3>Training Load</h3>
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
          <YAxis axisLine={false} tickLine={false} stroke={chart.grid.stroke} />
          <CartesianGrid stroke={chart.grid.stroke} strokeDasharray="3 3" />
          <Tooltip contentStyle={{ background: chart.tooltip.background, color: chart.tooltip.color }} formatter={(value: number) => value.toFixed(0)} labelFormatter={() => ''} />
          <Area type="monotone" dataKey="value" stroke={chart.Load.stroke} fill={`url(#${patternId})`} fillOpacity={1} />
        </AreaChart>
      </ResponsiveContainer>
    </Card>
  );
}
