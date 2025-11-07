import styled from 'styled-components';

import { useInsight } from '../../hooks/useInsight';
import { Card } from '../common/Card';
import { HRVChart } from '../charts/HRVChart';
import { RHRChart } from '../charts/RHRChart';
import { SleepChart } from '../charts/SleepChart';
import { LoadChart } from '../charts/LoadChart';

const List = styled.div`
  display: flex;
  flex-direction: column;
  gap: 32px;
`;

const Entry = styled(Card)`
  display: flex;
  flex-direction: column;
  gap: 32px;
  padding: 36px;
`;

const Header = styled.div`
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 24px;
`;

const HeaderMeta = styled.div`
  display: flex;
  flex-direction: column;
  gap: 8px;

  span {
    font-size: 0.85rem;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: ${({ theme }) => theme.colors.textSecondary};
  }

  h3 {
    margin: 0;
    font-size: 1.4rem;
    font-family: ${({ theme }) => theme.fonts.heading};
    color: ${({ theme }) => theme.colors.textPrimary};
  }

  p {
    margin: 0;
    font-size: 1rem;
    line-height: 1.6;
    color: ${({ theme }) => theme.colors.textSecondary};
    white-space: pre-line;
  }
`;

const ScoreStack = styled.div`
  display: flex;
  align-items: flex-end;
  gap: 12px;
`;

const ScoreValue = styled.div`
  font-size: clamp(3rem, 4.5vw, 4rem);
  font-family: ${({ theme }) => theme.fonts.heading};
  line-height: 1;
  color: ${({ theme }) => theme.colors.textPrimary};
`;

const ScoreMeta = styled.div`
  display: flex;
  flex-direction: column;
  gap: 4px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  font-size: 0.9rem;
  color: ${({ theme }) => theme.colors.textSecondary};
`;

const MetricsRows = styled.div`
  display: flex;
  flex-direction: column;
  gap: clamp(18px, 3vw, 32px);
`;

const MetricRow = styled.div`
  display: grid;
  gap: clamp(14px, 2vw, 24px);
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
`;

const InfoCard = styled(Card)`
  padding: clamp(16px, 2vw, 24px);
  display: flex;
  flex-direction: column;
  gap: 10px;
`;

const InsightCard = styled(Card)`
  padding: clamp(16px, 2vw, 24px);
  font-size: 0.95rem;
  line-height: 1.7;
  color: ${({ theme }) => theme.colors.textSecondary};
  white-space: pre-line;
`;

const MetricTitle = styled.div`
  font-family: ${({ theme }) => theme.fonts.heading};
  letter-spacing: 0.18em;
  text-transform: uppercase;
  font-size: 0.85rem;
  color: ${({ theme }) => theme.colors.textSecondary};
`;

const MetricValue = styled.div`
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 1.8rem;
  color: ${({ theme }) => theme.colors.textPrimary};
`;

const ChartCell = styled.div`
  min-height: 320px;
  display: flex;
  align-items: stretch;
  > * {
    width: 100%;
  }
`;

const Warning = styled.div`
  padding: 12px 16px;
  border-radius: 12px;
  border: 1px solid ${({ theme }) => theme.palette.ember['200']};
  background: rgba(226, 187, 111, 0.12);
  font-size: 0.95rem;
  color: ${({ theme }) => theme.colors.textPrimary};
`;

export function InsightHistory() {
  const { data, isLoading } = useInsight();

  const formattedDate = data?.metric_date
    ? new Date(data.metric_date).toLocaleDateString(undefined, {
        weekday: 'long',
        month: 'long',
        day: 'numeric'
      })
    : '—';

  const formatValue = (value?: number | null, decimals = 0) =>
    typeof value === 'number' ? value.toFixed(decimals) : '—';

  const sections = [
    {
      key: 'hrv',
      title: 'HRV',
      value: formatValue(data?.hrv_value_ms),
      unit: 'ms',
      note: data?.hrv_note
    },
    {
      key: 'rhr',
      title: 'Resting HR',
      value: formatValue(data?.rhr_value_bpm),
      unit: 'bpm',
      note: data?.rhr_note
    },
    {
      key: 'sleep',
      title: 'Sleep',
      value: formatValue(data?.sleep_value_hours, 2),
      unit: 'hrs',
      note: data?.sleep_note
    },
    {
      key: 'load',
      title: 'Training Load',
      value: formatValue(data?.training_load_value),
      unit: 'pts',
      note: data?.training_load_note
    }
  ];

  const hasStructured = sections.some((section) => section.note || section.value !== '—') || !!data?.morning_note;
  const chartMap = {
    hrv: <HRVChart />,
    rhr: <RHRChart />,
    sleep: <SleepChart />,
    load: <LoadChart />
  } as const;

  return (
    <List>
      <Entry>
        <Header>
          <HeaderMeta>
            <span>{formattedDate}</span>
            <h3>{data?.greeting ?? 'Monet insight unavailable.'}</h3>
            <p>{data?.morning_note ?? 'No readiness summary available.'}</p>
          </HeaderMeta>
          <ScoreStack>
            <ScoreValue>{isLoading ? '…' : formatValue(data?.readiness_score)}</ScoreValue>
            <ScoreMeta>
              <span>/ 100</span>
              <span>{data?.readiness_label ?? 'Pending'}</span>
            </ScoreMeta>
          </ScoreStack>
        </Header>

        {!isLoading && !hasStructured && (
          <Warning>Structured Monet insight missing. Investigate Vertex generation and parsing pipeline.</Warning>
        )}

        <MetricsRows>
          {sections.map((section) => (
            <MetricRow key={section.key}>
              <InfoCard>
                <MetricTitle>{section.title}</MetricTitle>
                <MetricValue>
                  {section.value} {section.unit}
                </MetricValue>
              </InfoCard>
              <InsightCard>{section.note ?? 'Structured insight missing.'}</InsightCard>
              <ChartCell>{chartMap[section.key]}</ChartCell>
            </MetricRow>
          ))}
        </MetricsRows>
      </Entry>
    </List>
  );
}
