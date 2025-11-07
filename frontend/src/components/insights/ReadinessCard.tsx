import styled from 'styled-components';

import { useInsight } from '../../hooks/useInsight';
import { useMetricSummary } from '../../hooks/useMetricSummary';
import type { MetricDelta } from '../../services/api';
import { Card as BaseCard } from '../common/Card';
import { getBlossomSprite } from '../../theme/monetTheme';

const Section = styled.div`
  display: flex;
  flex-direction: column;
  gap: clamp(18px, 2.5vw, 28px);
`;

const HeroCard = styled(BaseCard)`
  padding: clamp(28px, 4vw, 40px);
  overflow: hidden;
  min-height: 240px;

  &::after {
    content: '';
    position: absolute;
    width: clamp(100px, 20vw, 220px);
    height: clamp(100px, 20vw, 220px);
    top: clamp(-10px, -4vw, 10px);
    right: clamp(-20px, 5vw, 60px);
    background-image: ${({ theme }) => `url(${getBlossomSprite(theme.mode ?? 'light')})`};
    background-size: contain;
    background-repeat: no-repeat;
    opacity: 0.6;
    image-rendering: pixelated;
    pointer-events: none;
  }
`;

const MiniCard = styled(BaseCard)`
  padding: clamp(16px, 2.2vw, 26px);
  min-height: 120px;
`;

const Header = styled.div`
  display: flex;
  flex-direction: column;
  gap: 12px;

  span {
    font-family: ${({ theme }) => theme.fonts.heading};
    font-size: 0.8rem;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: ${({ theme }) => theme.colors.textSecondary};
  }
`;

const ScoreRow = styled.div`
  display: flex;
  align-items: flex-end;
  gap: 16px;
`;

const ScoreValue = styled.div`
  font-size: clamp(3.2rem, 5vw, 4.2rem);
  font-family: ${({ theme }) => theme.fonts.heading};
  line-height: 1;
  color: ${({ theme }) => theme.colors.textPrimary};
`;

const ScoreMeta = styled.div`
  display: flex;
  flex-direction: column;
  gap: 4px;
`;

const ScoreOutOf = styled.span`
  font-size: 0.9rem;
  text-transform: uppercase;
  letter-spacing: 0.2em;
  color: ${({ theme }) => theme.colors.textSecondary};
`;

const ScoreLabel = styled.strong`
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 1rem;
  color: ${({ theme }) => theme.colors.textPrimary};
`;

const ReadinessNote = styled.p`
  margin: 0;
  font-size: 1rem;
  line-height: 1.7;
  color: ${({ theme }) => theme.colors.textSecondary};
  white-space: pre-line;
`;

const MetricsStack = styled.div`
  display: flex;
  flex-direction: column;
  gap: clamp(18px, 2.8vw, 32px);
  /* Push all non-hero cards below the bridge span (height ≈ width / AR). */
  /* Push below arc + reflection heights (computed from viewport width and AR vars). */
  margin-top: calc(
    (100vw - (2 * var(--willow-offset, 6vw))) * (1 / var(--bridge-ar, 6) + 1 / var(--bridge-ref-ar, 6))
    + 24px
  );
`;

const MetricRow = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: clamp(16px, 2vw, 28px);
`;

const MetricLeft = styled.div`
  display: flex;
  flex-direction: column;
  gap: 12px;
`;

const MetricTitleLine = styled.div`
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 1rem;
  letter-spacing: 0.15em;
  text-transform: uppercase;
  color: ${({ theme }) => theme.colors.textSecondary};
  display: flex;
  flex-wrap: wrap;
  gap: 8px;

  strong {
    font-size: 1.1rem;
    color: ${({ theme }) => theme.colors.textPrimary};
    font-family: ${({ theme }) => theme.fonts.heading};
  }
`;

const MetricScoreText = styled.span`
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 1.2rem;
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
  font-size: 1rem;
  line-height: 1.7;
  color: ${({ theme }) => theme.colors.textSecondary};
`;

const Notice = styled.p`
  margin: 0;
  font-size: 0.9rem;
  line-height: 1.5;
  color: ${({ theme }) => theme.colors.alert ?? theme.colors.textSecondary};
  font-family: ${({ theme }) => theme.fonts.body};
`;

export function ReadinessCard() {
  const { data: insight, isLoading: insightLoading } = useInsight();
  const { data: summary } = useMetricSummary();

  const hasStructured =
    insight?.greeting != null ||
    insight?.hrv_note != null ||
    insight?.rhr_note != null ||
    insight?.sleep_note != null ||
    insight?.training_load_note != null ||
    insight?.morning_note != null;

  const formatValue = (value?: number | null, decimals = 0) =>
    typeof value === 'number' ? value.toFixed(decimals) : '—';

  type MetricKey = 'hrv' | 'rhr' | 'sleep' | 'training_load';

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
    { key: 'training_load', title: 'Training Load (14d)', note: insight?.training_load_note, decimals: 0 }
  ];

  const formatScore = (value?: number | null, scale = 10) =>
    typeof value === 'number' ? value.toFixed(1) : '—';

  return (
    <Section>
      <HeroCard data-hero-readiness="true">
        <Header>
          <span>Morning Readiness</span>
          <ScoreRow>
            <ScoreValue>{insightLoading ? '…' : formatValue(insight?.readiness_score)}</ScoreValue>
            <ScoreMeta>
              <ScoreOutOf>/ 100</ScoreOutOf>
              <ScoreLabel>{insight?.readiness_label ?? 'Awaiting insight'}</ScoreLabel>
            </ScoreMeta>
          </ScoreRow>
          <ReadinessNote>{insight?.morning_note ?? 'Structured insight missing.'}</ReadinessNote>
        </Header>
        {!insightLoading && !hasStructured && (
          <Notice>
            Structured Monet insight missing. Investigate Vertex generation and parsing pipeline.
          </Notice>
        )}
      </HeroCard>
      <MetricsStack>
        {metricSections.map(({ key, title, note, decimals }) => {
          const metric = metricSummary[key];
          const unit = key === 'sleep' ? 'hrs' : key === 'rhr' ? 'bpm' : key === 'hrv' ? 'ms' : 'pts';
          const measurement = metric ? `${formatMeasurement(metric, decimals ?? 0)} ${metricUnit(metric, unit)}` : '—';
          const scoreText = `${formatScore(metricScores[key])} / 10`;
          return (
            <MetricRow key={key}>
              <MiniCard>
                <MetricLeft>
                  <MetricTitleLine>
                    {title}:
                    <strong>{measurement}</strong>
                  </MetricTitleLine>
                  <MetricScoreText>{scoreText}</MetricScoreText>
                  <MetricDeltaText $variant={deltaVariant(key, metric?.delta)}>
                    {formatDeltaText(metric)}
                  </MetricDeltaText>
                </MetricLeft>
              </MiniCard>
              <MiniCard>
                <MetricInsight>{note ?? 'Structured insight missing.'}</MetricInsight>
              </MiniCard>
            </MetricRow>
          );
        })}
      </MetricsStack>
    </Section>
  );
}
