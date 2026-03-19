import { useState } from 'react';
import styled from 'styled-components';

import { useInsight } from '../../hooks/useInsight';
import { Card } from '../common/Card';
import { HRVChart } from '../charts/HRVChart';
import { RHRChart } from '../charts/RHRChart';
import { SleepChart } from '../charts/SleepChart';
import { LoadChart } from '../charts/LoadChart';

const Section = styled.div`
  display: flex;
  flex-direction: column;
  gap: 2px;
`;

const MetricStrip = styled.button<{ $expanded: boolean }>`
  display: grid;
  grid-template-columns: 8px auto 1fr auto auto;
  align-items: center;
  gap: clamp(10px, 1.5vw, 16px);
  padding: clamp(10px, 1.5vw, 14px) clamp(14px, 2vw, 20px);
  background: ${({ theme, $expanded }) =>
    $expanded ? theme.colors.overlayHover : 'transparent'};
  border: none;
  border-radius: 12px;
  color: inherit;
  font-family: inherit;
  cursor: pointer;
  transition: background 0.15s ease;
  text-align: left;
  width: 100%;

  &:hover {
    background: ${({ theme }) => theme.colors.overlay};
  }

  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: -2px;
  }
`;

const ScoreDot = styled.span<{ $score: number | null | undefined }>`
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
  background: ${({ $score, theme }) => {
    if ($score == null) return theme.colors.borderSubtle;
    if ($score >= 7) return theme.colors.success;
    if ($score >= 4) return theme.palette?.ember?.['300'] ?? theme.colors.accent;
    return theme.colors.danger;
  }};
`;

const TierLabel = styled.span<{ $score: number | null | undefined }>`
  font-size: 0.62rem;
  font-family: ${({ theme }) => theme.fonts.heading};
  letter-spacing: 0.08em;
  text-transform: uppercase;
  min-width: 28px;
  color: ${({ $score, theme }) => {
    if ($score == null) return theme.colors.textSecondary;
    if ($score >= 7) return theme.colors.success;
    if ($score >= 4) return theme.palette?.ember?.['300'] ?? theme.colors.accent;
    return theme.colors.danger;
  }};
`;

const MetricName = styled.span`
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.78rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: ${({ theme }) => theme.colors.textPrimary};
`;

const MetricValue = styled.span`
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.9rem;
  color: ${({ theme }) => theme.colors.textPrimary};
  font-variant-numeric: tabular-nums;
  text-align: right;
`;

const MetricScore = styled.span`
  font-size: 0.72rem;
  letter-spacing: 0.1em;
  color: ${({ theme }) => theme.colors.textSecondary};
  min-width: 32px;
  text-align: right;
`;

const ExpandPanel = styled.div<{ $open: boolean }>`
  display: grid;
  grid-template-rows: ${({ $open }) => ($open ? '1fr' : '0fr')};
  transition: grid-template-rows 0.25s ease;

  @media (prefers-reduced-motion: reduce) {
    transition-duration: 0.01ms;
  }
`;

const ExpandInner = styled.div`
  overflow: hidden;
`;

const DetailGrid = styled.div`
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: clamp(10px, 1.5vw, 16px);
  padding: 4px clamp(14px, 2vw, 20px) clamp(14px, 2vw, 20px);

  @media (max-width: 700px) {
    grid-template-columns: 1fr;
  }
`;

const NoteCard = styled(Card)`
  padding: clamp(12px, 1.5vw, 18px);
  font-size: 0.88rem;
  line-height: 1.6;
  color: ${({ theme }) => theme.colors.textSecondary};
  white-space: pre-line;
`;

const ChartCard = styled(Card)`
  padding: clamp(8px, 1vw, 12px);
  min-height: 220px;
  display: flex;
  align-items: stretch;
  > * {
    width: 100%;
  }
`;

const GreetingSection = styled(Card)`
  padding: clamp(16px, 2vw, 24px);
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: clamp(10px, 1.5vw, 16px);
`;

const Greeting = styled.h3`
  margin: 0;
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 1.1rem;
  letter-spacing: 0.08em;
  color: ${({ theme }) => theme.colors.textPrimary};
`;

const GreetingDate = styled.span`
  font-size: 0.75rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: ${({ theme }) => theme.colors.textSecondary};
`;

const Warning = styled.div`
  padding: 10px 14px;
  border-radius: 10px;
  border: 1px solid ${({ theme }) => theme.palette?.ember?.['200'] ?? theme.colors.borderSubtle};
  background: ${({ theme }) => theme.colors.accentSubtle};
  font-size: 0.85rem;
  color: ${({ theme }) => theme.colors.textPrimary};
`;

export function InsightHistory() {
  const { data, isLoading } = useInsight();
  const [expanded, setExpanded] = useState<string | null>(null);

  const formattedDate = data?.metric_date
    ? new Date(data.metric_date).toLocaleDateString(undefined, {
        weekday: 'long',
        month: 'long',
        day: 'numeric'
      })
    : '';

  const fmt = (value?: number | null, decimals = 0) =>
    typeof value === 'number' ? value.toFixed(decimals) : '—';

  const tierLabel = (score?: number | null) => {
    if (score == null) return '—';
    if (score >= 7) return 'Good';
    if (score >= 4) return 'Fair';
    return 'Low';
  };

  const sections = [
    { key: 'hrv', title: 'HRV', value: fmt(data?.hrv_value_ms), unit: 'ms', note: data?.hrv_note, score: data?.hrv_score },
    { key: 'rhr', title: 'Resting HR', value: fmt(data?.rhr_value_bpm), unit: 'bpm', note: data?.rhr_note, score: data?.rhr_score },
    { key: 'sleep', title: 'Sleep', value: fmt(data?.sleep_value_hours, 1), unit: 'hrs', note: data?.sleep_note, score: data?.sleep_score },
    { key: 'load', title: 'Training Load', value: fmt(data?.training_load_value), unit: 'pts', note: data?.training_load_note, score: data?.training_load_score }
  ];

  const hasStructured = sections.some(s => s.note || s.value !== '—') || !!data?.morning_note;

  type MetricKey = 'hrv' | 'rhr' | 'sleep' | 'load';
  const chartMap: Record<MetricKey, JSX.Element> = {
    hrv: <HRVChart />,
    rhr: <RHRChart />,
    sleep: <SleepChart />,
    load: <LoadChart />
  };

  const toggle = (key: string) => setExpanded(prev => prev === key ? null : key);

  return (
    <div>
      {data?.greeting && (
        <GreetingSection>
          <GreetingDate data-halo="heading">{formattedDate}</GreetingDate>
          <Greeting data-halo="heading">{data.greeting}</Greeting>
        </GreetingSection>
      )}

      {!isLoading && !hasStructured && (
        <Warning>Detailed insights are still being prepared. Check back shortly.</Warning>
      )}

      <Section>
        {sections.map(s => (
          <div key={s.key}>
            <MetricStrip
              type="button"
              $expanded={expanded === s.key}
              onClick={() => toggle(s.key)}
              aria-expanded={expanded === s.key}
              aria-label={`${s.title}: ${s.value} ${s.unit}${s.score != null ? `, score ${s.score} out of 10` : ''}`}
            >
              <ScoreDot $score={s.score} />
              <TierLabel $score={s.score}>{tierLabel(s.score)}</TierLabel>
              <MetricName>{s.title}</MetricName>
              <MetricValue>{s.value} {s.unit}</MetricValue>
              <MetricScore>{s.score != null ? `${s.score}/10` : ''}</MetricScore>
            </MetricStrip>
            <ExpandPanel $open={expanded === s.key}>
              <ExpandInner>
                <DetailGrid>
                  <NoteCard>{s.note ?? 'No insight available.'}</NoteCard>
                  <ChartCard>{chartMap[s.key as MetricKey]}</ChartCard>
                </DetailGrid>
              </ExpandInner>
            </ExpandPanel>
          </div>
        ))}
      </Section>
    </div>
  );
}
