import { useMemo } from 'react';
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid } from 'recharts';
import { useTheme } from 'styled-components';

import { useMetricsOverview } from '../../hooks/useMetricsOverview';
import { getChartTheme } from '../../theme/rechartsTheme';
import { Card } from '../common/Card';
import type { MonetTheme } from '../../theme/monetTheme';
import { getStrokePattern } from '../../theme/monetTheme';

export function SleepChart() {
  const { data } = useMetricsOverview(14);
  const appTheme = useTheme() as MonetTheme;
  const chart = getChartTheme(appTheme.mode ?? 'light');
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

  const strokePattern = getStrokePattern('Sleep');
  const patternId = `sleep-stroke-pattern`;
  return (
    <Card>
      <h3>Sleep Hours</h3>
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={bars}>
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
          <Tooltip contentStyle={{ background: chart.tooltip.background, color: chart.tooltip.color }} formatter={(value: number) => `${(value as number).toFixed(1)} h`} labelFormatter={() => ''} />
          <Bar dataKey="value" fill={`url(#${patternId})`} stroke={chart.Sleep.stroke} radius={[8, 8, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </Card>
  );
}
