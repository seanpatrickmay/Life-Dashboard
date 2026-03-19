import styled, { useTheme } from 'styled-components';

import { useInsight } from '../../hooks/useInsight';
import { Card as BaseCard } from '../common/Card';
import type { MonetTheme, Moment } from '../../theme/monetTheme';

const Hero = styled(BaseCard)`
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: clamp(16px, 3vw, 28px);
  padding: clamp(20px, 3vw, 32px);
`;

const ScoreBlock = styled.div`
  display: flex;
  align-items: baseline;
  gap: 10px;
  flex-shrink: 0;
`;

const Score = styled.div`
  font-size: clamp(3.2rem, 5.5vw, 4.2rem);
  font-family: ${({ theme }) => theme.fonts.heading};
  line-height: 1;
  color: ${({ theme }) => theme.colors.textPrimary};
`;

const ScoreSuffix = styled.span`
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.9rem;
  letter-spacing: 0.14em;
  color: ${({ theme }) => theme.colors.textSecondary};
`;

const ContentBlock = styled.div`
  flex: 1;
  min-width: min(260px, 100%);
  display: flex;
  flex-direction: column;
  gap: 6px;
`;

const LabelRow = styled.div`
  display: flex;
  align-items: baseline;
  gap: 12px;
  flex-wrap: wrap;
`;

const StatusLabel = styled.span`
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.85rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: ${({ theme }) => theme.colors.textPrimary};
`;

const DateStamp = styled.span`
  font-size: 0.72rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: ${({ theme }) => theme.colors.textSecondary};
`;

const Narrative = styled.p`
  margin: 0;
  font-size: 0.92rem;
  line-height: 1.55;
  color: ${({ theme }) => theme.colors.textSecondary};
  max-width: 56ch;
`;

const Notice = styled.p`
  margin: 0;
  font-size: 0.82rem;
  color: ${({ theme }) => theme.palette?.ember?.['300'] ?? theme.colors.textSecondary};
`;

const fallbackNarrative: Record<Moment, string> = {
  morning: 'Poised for a bright start.',
  noon: 'Steady energy through the day.',
  twilight: 'Ease into the calm.',
  night: 'Restore and settle.'
};

export function ReadinessCard() {
  const { data: insight, isLoading } = useInsight();
  const theme = useTheme() as MonetTheme;
  const moment = (theme.moment ?? 'morning') as Moment;

  const score = isLoading ? '…' : formatValue(insight?.readiness_score);
  const label = insight?.readiness_label ?? 'Awaiting insight';
  const narrative = insight?.morning_note ?? fallbackNarrative[moment];
  const stamp = insight?.metric_date
    ? new Date(insight.metric_date).toLocaleDateString(undefined, {
        weekday: 'short',
        month: 'short',
        day: 'numeric'
      })
    : '—';

  const hasStructured = Boolean(
    insight?.greeting ?? insight?.hrv_note ?? insight?.rhr_note ??
    insight?.sleep_note ?? insight?.training_load_note ?? insight?.morning_note
  );

  return (
    <Hero>
      <ScoreBlock>
        <Score data-halo="heading" aria-label={`Readiness score: ${score} out of 100`}>
          {score}
        </Score>
        <ScoreSuffix>/ 100</ScoreSuffix>
      </ScoreBlock>
      <ContentBlock>
        <LabelRow>
          <StatusLabel data-halo="heading">{label}</StatusLabel>
          <DateStamp>{stamp}</DateStamp>
        </LabelRow>
        <Narrative>{narrative}</Narrative>
        {!isLoading && !hasStructured && (
          <Notice>Structured insight missing.</Notice>
        )}
      </ContentBlock>
    </Hero>
  );
}

function formatValue(value?: number | null) {
  return typeof value === 'number' ? value.toFixed(0) : '—';
}
