import styled from 'styled-components';

import { LilyPadCard } from './LilyPadCard';
import type { LilyPadCardProps } from './LilyPadCard';
import { useMetricSummary } from '../../hooks/useMetricSummary';
import { useInsight } from '../../hooks/useInsight';
import type { MetricDelta } from '../../services/api';

const Spacer = styled.div`
  width: 100%;
`;

const formatValue = (metric?: MetricDelta, decimals = 0, fallbackUnit?: string, loading?: boolean) => {
  if (loading) return '…';
  if (!metric || metric.value == null) return undefined;
  const unit = metric.value_unit || fallbackUnit || '';
  return `${metric.value.toFixed(decimals)}${unit ? ` ${unit}` : ''}`;
};

const formatDelta = (metric?: MetricDelta) => {
  if (!metric || metric.delta == null || !metric.reference_label) return undefined;
  const sign = metric.delta > 0 ? '+' : metric.delta < 0 ? '−' : '';
  const mag = Math.abs(metric.delta);
  const unit = metric.delta_unit || '';
  let formatted: string;
  if (unit === '%') {
    formatted = `${mag.toFixed(1)}%`;
  } else if (unit === 'min') {
    formatted = `${Math.round(mag)} min`;
  } else if (unit === 'bpm') {
    formatted = `${mag.toFixed(1)} bpm`;
  } else if (unit === 'ms') {
    formatted = `${mag.toFixed(1)} ms`;
  } else if (unit) {
    formatted = `${mag.toFixed(1)} ${unit}`;
  } else {
    formatted = mag.toFixed(1);
  }
  return `${sign}${formatted} vs ${metric.reference_label}`;
};

export function LilyPadsDashboard() {
  const { data: summary, isLoading } = useMetricSummary();
  const { data: insight, isLoading: insightLoading } = useInsight();

  type PadConfig = {
    id: string;
    title: string;
    metric?: MetricDelta;
    decimals?: number;
    fallbackUnit?: string;
    side: LilyPadCardProps['side'];
    topOffsetPx: number;
    scale: NonNullable<LilyPadCardProps['scale']>;
    valueText?: string;
    subtitleText?: string;
  };

  const pads: PadConfig[] = [
    {
      id: 'pad-readiness',
      title: 'Readiness',
      side: 'left',
      topOffsetPx: 0,
      scale: 0.65,
      valueText: formatReadinessValue(insight?.readiness_score, insightLoading),
      subtitleText: insight?.readiness_label ?? (insightLoading ? 'Loading…' : 'Awaiting insight')
    },
    {
      id: 'pad-sleep',
      title: 'Sleep',
      metric: summary?.sleep,
      decimals: 1,
      fallbackUnit: 'hrs',
      side: 'right',
      topOffsetPx: 120,
      scale: 0.75
    },
    {
      id: 'pad-hrv',
      title: 'HRV',
      metric: summary?.hrv,
      decimals: 0,
      fallbackUnit: 'ms',
      side: 'left',
      topOffsetPx: 300,
      scale: 0.85
    },
    {
      id: 'pad-rhr',
      title: 'RHR',
      metric: summary?.rhr,
      decimals: 0,
      fallbackUnit: 'bpm',
      side: 'right',
      topOffsetPx: 450,
      scale: 0.95
    }
  ];
  const PAD_BASE_HEIGHT = 320;
  const spacerHeight = pads.reduce((max, pad) => {
    const padHeight = PAD_BASE_HEIGHT * pad.scale;
    return Math.max(max, pad.topOffsetPx + padHeight);
  }, 0);

  return (
    <>
      {pads.map((pad) => (
        <LilyPadCard
          key={pad.id}
          id={pad.id}
          side={pad.side}
          topOffsetPx={pad.topOffsetPx}
          scale={pad.scale}
          title={pad.title}
          value={pad.valueText ?? formatValue(pad.metric, pad.decimals ?? 0, pad.fallbackUnit, isLoading)}
          subtitle={pad.subtitleText ?? formatDelta(pad.metric)}
        />
      ))}
      <Spacer aria-hidden style={{ height: `${spacerHeight + 320}px` }} />
    </>
  );
}

const formatReadinessValue = (score?: number | null, loading?: boolean) => {
  if (loading) return '… / 100';
  if (typeof score === 'number') {
    return `${Math.round(score)} / 100`;
  }
  return '— / 100';
};
