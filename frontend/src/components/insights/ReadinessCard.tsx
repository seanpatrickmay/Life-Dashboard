import styled, { useTheme } from 'styled-components';

import { useInsight } from '../../hooks/useInsight';
import { Card as BaseCard } from '../common/Card';
import type { MonetTheme, Moment } from '../../theme/monetTheme';

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

const Notice = styled.p`
  margin: 0;
  font-size: 0.9rem;
  line-height: 1.5;
  color: ${({ theme }) => theme.colors.alert ?? theme.colors.textSecondary};
  font-family: ${({ theme }) => theme.fonts.body};
`;

const fallbackHeroNarrative: Record<Moment, string> = {
  morning: 'Poised for a bright start.',
  noon: 'Steady energy through the day.',
  twilight: 'Ease into the calm.',
  night: 'Restore and settle.'
};

const momentLabelMap: Record<Moment, string> = {
  morning: 'Morning',
  noon: 'Noon',
  twilight: 'Twilight',
  night: 'Night'
};

export function ReadinessCard() {
  const { data: insight, isLoading: insightLoading } = useInsight();
  const theme = useTheme() as MonetTheme;
  const activeMoment = (theme.moment ?? 'morning') as Moment;

  const heroScore = insightLoading ? '…' : formatValue(insight?.readiness_score);
  const heroLabel = insight?.readiness_label ?? 'Awaiting insight';
  const heroNarrative = insight?.morning_note ?? fallbackHeroNarrative[activeMoment];
  const heroTitle = `${momentLabelMap[activeMoment]} Readiness`;
  const heroStamp = insight?.metric_date ?? '—';

  const hasStructured = Boolean(
    insight?.greeting ??
      insight?.hrv_note ??
      insight?.rhr_note ??
      insight?.sleep_note ??
      insight?.training_load_note ??
      insight?.morning_note
  );

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
    </Section>
  );
}

function formatValue(value?: number | null, decimals = 0) {
  return typeof value === 'number' ? value.toFixed(decimals) : '—';
}

