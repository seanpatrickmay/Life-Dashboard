import styled, { useTheme } from 'styled-components';
import { useLayoutEffect, useState } from 'react';

import { useInsight } from '../../hooks/useInsight';
import { useMetricSummary } from '../../hooks/useMetricSummary';
import type { MetricDelta } from '../../services/api';
import { Card as BaseCard } from '../common/Card';
import type { MonetTheme, Moment } from '../../theme/monetTheme';

type MetricKey = 'hrv' | 'rhr' | 'sleep' | 'training_load';
const Section = styled.div`
  display: flex;
  flex-direction: column;
  gap: clamp(18px, 2.5vw, 32px);
`;

const HeroCluster = styled.div`
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: clamp(14px, 2vw, 22px);
`;

const HeroTile = styled(BaseCard)`
  flex: 1 1 min(320px, 48vw);
  min-width: min(260px, 48vw);
  display: flex;
  flex-direction: column;
  gap: 8px;
`;

const HeroLabel = styled.span`
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.85rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: ${({ theme }) => theme.colors.textSecondary};
`;

const HeroScore = styled.div`
  font-size: clamp(3.6rem, 6vw, 4.6rem);
  font-family: ${({ theme }) => theme.fonts.heading};
  line-height: 1;
  color: ${({ theme }) => theme.colors.textPrimary};
`;

const HeroScale = styled.div`
  display: flex;
  flex-direction: column;
  gap: 6px;
`;

const ScaleRow = styled.div`
  display: flex;
  align-items: baseline;
  gap: 8px;
`;

const ScaleValue = styled.strong`
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 1rem;
  letter-spacing: 0.18em;
  color: ${({ theme }) => theme.colors.textPrimary};
`;

const ScoreLabel = styled.span`
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.95rem;
  letter-spacing: 0.12em;
  color: ${({ theme }) => theme.colors.textPrimary};
`;

const ScaleStamp = styled.small`
  font-size: 0.8rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: ${({ theme }) => theme.colors.textSecondary};
`;

const HeroNarrative = styled.p`
  margin: 0;
  font-size: 1rem;
  line-height: 1.6;
  color: ${({ theme }) => theme.colors.textSecondary};
`;

const MetricMatrix = styled.div`
  display: flex;
  flex-direction: column;
  gap: clamp(18px, 2.8vw, 34px);
`;

const MetricGroup = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: clamp(12px, 1.5vw, 20px);
  align-items: flex-start;
`;

const MetricChip = styled(BaseCard)`
  min-height: 110px;
  display: flex;
  flex-direction: column;
  gap: 10px;
`;

const InsightChip = styled(BaseCard)`
  min-height: 110px;
`;

const SparklineCard = styled(BaseCard)`
  min-height: 70px;
  padding: clamp(10px, 1.4vw, 16px);
`;

const MetricTitleLine = styled.div`
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.95rem;
  letter-spacing: 0.15em;
  text-transform: uppercase;
  color: ${({ theme }) => theme.colors.textSecondary};
  display: flex;
  flex-wrap: wrap;
  gap: 6px;

  strong {
    font-size: 1.1rem;
    color: ${({ theme }) => theme.colors.textPrimary};
    font-family: ${({ theme }) => theme.fonts.heading};
  }
`;

const MetricScoreText = styled.span`
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 1.1rem;
  letter-spacing: 0.2em;
  color: ${({ theme }) => theme.colors.textPrimary};
`;

type DeltaVariant = 'positive' | 'negative' | 'neutral';

const MetricDeltaText = styled.span<{ $variant: DeltaVariant }>`
  font-size: 0.85rem;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: ${({ theme, $variant }) => {
    if ($variant === 'positive') return theme.palette.pond['200'] ?? '#7ED7C4';
    if ($variant === 'negative') return theme.palette.ember['200'] ?? '#FFC075';
    return theme.colors.textSecondary;
  }};
`;

const MetricInsight = styled.p`
  margin: 0;
  font-size: 0.95rem;
  line-height: 1.6;
  color: ${({ theme }) => theme.colors.textSecondary};
`;

const SparklineSvg = styled.svg`
  width: 100%;
  height: 48px;
  display: block;
`;

const SparklinePath = styled.path`
  fill: none;
  stroke-width: 2;
  vector-effect: non-scaling-stroke;
  stroke-linecap: round;
  stroke-linejoin: round;
  shape-rendering: crispEdges;
`;

const SparklineBaseline = styled.line`
  stroke-width: 1;
  stroke-dasharray: 2 3;
  vector-effect: non-scaling-stroke;
  shape-rendering: crispEdges;
`;

const Notice = styled.p`
  margin: 0;
  font-size: 0.9rem;
  line-height: 1.5;
  color: ${({ theme }) => theme.colors.alert ?? theme.colors.textSecondary};
  font-family: ${({ theme }) => theme.fonts.body};
`;

type SparklinePoint = { x: number; y: number };

const createSeededRandom = (seed: string) => {
  let h = 0;
  for (let i = 0; i < seed.length; i += 1) {
    h = Math.imul(31, h) + seed.charCodeAt(i);
    h |= 0;
  }
  return () => {
    h = Math.imul(h ^ (h >>> 15), h | 1);
    h ^= h + Math.imul(h ^ (h >>> 7), h | 61);
    return ((h ^ (h >>> 14)) >>> 0) / 4294967296;
  };
};

type MetricRange = { min: number; max: number };

const metricRanges: Record<MetricKey, MetricRange> = {
  hrv: { min: 20, max: 120 },
  rhr: { min: 40, max: 80 },
  sleep: { min: 4, max: 10 },
  training_load: { min: 0, max: 160 }
};

const normalizeValue = (value?: number | null, range?: MetricRange) => {
  if (value == null) return 50;
  if (!range) return Math.max(0, Math.min(100, value));
  const clamped = Math.max(range.min, Math.min(range.max, value));
  return ((clamped - range.min) / (range.max - range.min)) * 100;
};

const buildSparkline = (key: string, metricKey: string, metric?: MetricDelta): SparklinePoint[] => {
  const points = 7;
  const rng = createSeededRandom(`${key}-${metricKey}`);
  const range = metricRanges[metricKey];
  const base = normalizeValue(metric?.value, range);
  const width = range ? range.max - range.min : 100;
  const deltaNorm = width ? ((metric?.delta ?? 0) / width) * 100 : 0;
  return Array.from({ length: points }, (_, idx) => {
    const progress = idx / (points - 1);
    const trend = base + deltaNorm * progress;
    const noise = (rng() - 0.5) * 10;
    const value = Math.max(0, Math.min(100, trend + noise));
    return {
      x: progress * 100,
      y: 40 - (value / 100) * 40
    };
  });
};

const fallbackHeroNarrative: Record<Moment, string> = {
  morning: 'Poised for a bright start.',
  noon: 'Steady energy through the day.',
  twilight: 'Ease into the calm.',
  night: 'Restore and settle.'
};

const fallbackMetricInsights: Record<MetricKey, string> = {
  hrv: 'Recovery signals trending strong.',
  rhr: 'Resting rate holds steady.',
  sleep: 'Deep sleep carried the night.',
  training_load: 'Training load within sweet spot.'
};

const chartKeyMap: Record<MetricKey, keyof MonetTheme['chart']> = {
  hrv: 'HRV',
  rhr: 'RHR',
  sleep: 'Sleep',
  training_load: 'Load'
};

const unitLabelMap: Record<MetricKey, string> = {
  hrv: 'ms',
  rhr: 'bpm',
  sleep: 'hrs',
  training_load: 'pts'
};

const momentLabelMap: Record<Moment, string> = {
  morning: 'Morning',
  noon: 'Noon',
  twilight: 'Twilight',
  night: 'Night'
};

export function ReadinessCard() {
  const { data: insight, isLoading: insightLoading } = useInsight();
  const { data: summary } = useMetricSummary();
  const theme = useTheme() as MonetTheme;
  const activeMoment = (theme.moment ?? 'morning') as Moment;
  const [safeOffsets, setSafeOffsets] = useState({ metricsTop: 0, bottomPad: 64 });

  useLayoutEffect(() => {
    const surface = document.querySelector('[data-scene-surface]') as HTMLElement | null;
    if (!surface) return;

    const compute = () => {
      const styles = getComputedStyle(surface);
      const metricsTop = parseFloat(styles.getPropertyValue('--safe-metrics-top') || '0');
      const bottomPad = parseFloat(styles.getPropertyValue('--boat-padding') || '64') || 64;
      setSafeOffsets({ metricsTop, bottomPad });
    };

    compute();
    const resizeObs = new ResizeObserver(compute);
    resizeObs.observe(surface);
    window.addEventListener('resize', compute);
    return () => {
      resizeObs.disconnect();
      window.removeEventListener('resize', compute);
    };
  }, [activeMoment]);

  const hasStructured =
    insight?.greeting != null ||
    insight?.hrv_note != null ||
    insight?.rhr_note != null ||
    insight?.sleep_note != null ||
    insight?.training_load_note != null ||
    insight?.morning_note != null;

  const formatValue = (value?: number | null, decimals = 0) =>
    typeof value === 'number' ? value.toFixed(decimals) : '—';

  const deltaVariant = (key: MetricKey, delta?: number | null): DeltaVariant => {
    if (delta == null || delta === 0) return 'neutral';
    const positive = delta > 0;
    if (key === 'rhr') {
      return positive ? 'negative' : 'positive';
    }
    return positive ? 'positive' : 'negative';
  };

  const formatMeasurement = (metric?: MetricDelta, decimals = 0) =>
    metric?.value != null ? metric.value.toFixed(decimals) : '—';

  const metricUnit = (metric?: MetricDelta, fallback = '') => metric?.value_unit ?? fallback;

  const formatDeltaText = (metric?: MetricDelta) => {
    if (!metric || metric.delta == null || !metric.reference_label) {
      return 'No comparison available';
    }
    if (metric.delta === 0) {
      return `No change vs ${metric.reference_label}`;
    }
    const sign = metric.delta > 0 ? '+' : '−';
    const magnitude = Math.abs(metric.delta);
    let formatted: string;
    if (metric.delta_unit === '%') {
      formatted = `${magnitude.toFixed(1)}%`;
    } else if (metric.delta_unit === 'min') {
      formatted = `${Math.round(magnitude)} min`;
    } else if (metric.delta_unit === 'bpm') {
      formatted = `${magnitude.toFixed(1)} bpm`;
    } else {
      formatted = `${magnitude.toFixed(1)} ${metric.delta_unit}`;
    }
    return `${sign}${formatted} vs ${metric.reference_label}`;
  };

  const metricSummary: Record<MetricKey, MetricDelta | undefined> = {
    hrv: summary?.hrv,
    rhr: summary?.rhr,
    sleep: summary?.sleep,
    training_load: summary?.training_load
  };

  const metricScores: Record<MetricKey, number | null | undefined> = {
    hrv: insight?.hrv_score,
    rhr: insight?.rhr_score,
    sleep: insight?.sleep_score,
    training_load: insight?.training_load_score
  };

  const metricSections: { key: MetricKey; title: string; note?: string | null; decimals?: number }[] = [
    { key: 'hrv', title: 'HRV', note: insight?.hrv_note, decimals: 0 },
    { key: 'rhr', title: 'Resting HR', note: insight?.rhr_note, decimals: 0 },
    { key: 'sleep', title: 'Sleep', note: insight?.sleep_note, decimals: 2 },
    { key: 'training_load', title: 'Load (14d)', note: insight?.training_load_note, decimals: 0 }
  ];

  const formatScore = (value?: number | null) =>
    typeof value === 'number' ? value.toFixed(1) : '—';

  const heroScore = insightLoading ? '…' : formatValue(insight?.readiness_score);
  const heroLabel = insight?.readiness_label ?? 'Awaiting insight';
  const heroNarrative = insight?.morning_note ?? fallbackHeroNarrative[activeMoment];
  const heroTitle = `${momentLabelMap[activeMoment]} Readiness`;
  const heroStamp = insight?.metric_date ?? '—';

  return (
    <Section>
      <HeroCluster data-hero-readiness="true">
        <HeroTile>
          <HeroLabel data-halo="heading">{heroTitle}</HeroLabel>
          <HeroScore data-halo="heading">{heroScore}</HeroScore>
        </HeroTile>
        <HeroTile>
          <HeroLabel data-halo="heading">Status</HeroLabel>
          <HeroScale>
            <ScaleRow>
              <ScaleValue data-halo="heading">/ 100</ScaleValue>
              <ScoreLabel>{heroLabel}</ScoreLabel>
            </ScaleRow>
            <ScaleStamp>{heroStamp}</ScaleStamp>
          </HeroScale>
        </HeroTile>
        <HeroTile>
          <HeroLabel data-halo="heading">Today</HeroLabel>
          <HeroNarrative>{heroNarrative}</HeroNarrative>
          {!insightLoading && !hasStructured && (
            <Notice>Structured insight missing. Investigate Vertex generation.</Notice>
          )}
        </HeroTile>
      </HeroCluster>
      <MetricMatrix style={{ marginTop: safeOffsets.metricsTop, paddingBottom: safeOffsets.bottomPad }}>
        {metricSections.map(({ key, title, note, decimals }) => {
          const metric = metricSummary[key];
          const measurement = metric
            ? `${formatMeasurement(metric, decimals ?? 0)} ${metricUnit(metric, unitLabelMap[key])}`
            : '—';
          const scoreText = `${formatScore(metricScores[key])} / 10`;
          const sparkPoints = buildSparkline(title, key, metric);
          const sparkPath = sparkPoints
            .map((point, idx) => `${idx === 0 ? 'M' : 'L'} ${point.x} ${point.y}`)
            .join(' ');
          const baselineVal = normalizeValue(metric?.reference_value ?? metric?.value, metricRanges[key]);
          const baselineY = 40 - (baselineVal / 100) * 40;
          const chartKey = chartKeyMap[key];
          const strokeColor = theme.chart?.[chartKey]?.stroke ?? theme.colors.accent;
          const baselineColor = theme.colors.accentSoft ?? 'rgba(255,255,255,0.25)';
          const insightCopy = note ?? fallbackMetricInsights[key];
          return (
            <MetricGroup key={key}>
              <MetricChip>
                <MetricTitleLine data-halo="heading">
                  {title}:
                  <strong>{measurement}</strong>
                </MetricTitleLine>
                <MetricScoreText data-halo="heading">{scoreText}</MetricScoreText>
                <MetricDeltaText $variant={deltaVariant(key, metric?.delta)}>
                  {formatDeltaText(metric)}
                </MetricDeltaText>
              </MetricChip>
              <InsightChip>
                <MetricInsight>{insightCopy}</MetricInsight>
              </InsightChip>
              <SparklineCard aria-hidden>
                <SparklineSvg viewBox="0 0 100 40" preserveAspectRatio="none">
                  <SparklineBaseline x1="0" y1={baselineY} x2="100" y2={baselineY} stroke={baselineColor} />
                  <SparklinePath d={sparkPath} stroke={strokeColor} />
                </SparklineSvg>
              </SparklineCard>
            </MetricGroup>
          );
        })}
      </MetricMatrix>
    </Section>
  );
}
