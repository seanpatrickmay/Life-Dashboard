import styled from 'styled-components';
import { useInsight } from '../../hooks/useInsight';
import { LilyPadCard } from './LilyPadCard';
import { HRVChart } from '../charts/HRVChart';
import { RHRChart } from '../charts/RHRChart';
import { SleepChart } from '../charts/SleepChart';
import { LoadChart } from '../charts/LoadChart';

const CHART_SINK_PX = 500;

const Stage = styled.div`
  position: relative;
  display: flex;
  flex-direction: column;
  gap: clamp(180px, 22vh, 260px);
  padding: clamp(32px, 6vh, 72px) clamp(16px, 6vw, 80px) clamp(220px, 28vh, 360px);
`;

const Narrative = styled.p`
  margin: 10px 0 0;
  font-size: 0.95rem;
  line-height: 1.7;
  color: #ffffff;
  opacity: 0.92;
  max-width: 380px;
`;

const ReadinessBlock = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  width: 100%;
`;

const ReadinessValue = styled.div`
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: clamp(2.4rem, 4vw, 3.2rem);
`;

const ReadinessLabel = styled.span`
  font-size: 0.85rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  opacity: 0.85;
`;

const Subtitle = styled.span`
  display: block;
  font-size: 0.8rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: rgba(255, 255, 255, 0.85);
  margin-bottom: 4px;
`;

const MetricRow = styled.div<{ $padSide: 'left' | 'right' }>`
  display: flex;
  justify-content: ${(p) => (p.$padSide === 'left' ? 'flex-end' : 'flex-start')};
  align-items: flex-start;
  gap: clamp(24px, 5vw, 72px);
  min-height: clamp(180px, 34vh, 320px);
`;

const ChartUnderlay = styled.div<{ $align: 'left' | 'right' }>`
  width: min(460px, 44vw);
  min-height: clamp(220px, 34vh, 320px);
  padding: clamp(16px, 2vw, 28px);
  background: linear-gradient(180deg, rgba(5, 18, 34, 0.25), rgba(3, 10, 20, 0.6));
  border-radius: 36px;
  border: 1px solid rgba(156, 192, 224, 0.28);
  box-shadow: none;
  color: #ffffff;
  backdrop-filter: blur(3px) saturate(1.05);
  display: flex;
  flex-direction: column;
  gap: 12px;
  position: relative;
  overflow: hidden;
  isolation: isolate;
  transform: translateY(${22 + CHART_SINK_PX}px);
  margin-left: ${(p) => (p.$align === 'right' ? 'auto' : '0')};
  margin-right: ${(p) => (p.$align === 'left' ? 'auto' : '0')};
  &::before {
    content: '';
    position: absolute;
    inset: -20% -10% -40% -10%;
    background: radial-gradient(circle at 30% 20%, rgba(255, 255, 255, 0.18), transparent 60%),
      radial-gradient(circle at 70% 10%, rgba(173, 216, 255, 0.2), transparent 55%);
    opacity: 0.7;
    mix-blend-mode: screen;
    pointer-events: none;
  }
  &::after {
    content: '';
    position: absolute;
    inset: 0;
    background: linear-gradient(180deg, rgba(4, 9, 18, 0.35), rgba(6, 12, 24, 0.85));
    opacity: 0.9;
    mix-blend-mode: multiply;
    pointer-events: none;
  }
  > * {
    position: relative;
    z-index: 1;
  }
`;

const PadSpacer = styled.div`
  width: 100%;
  height: 120px;
`;

export function LilyPadsInsights() {
  const { data } = useInsight();

  const formattedDate = data?.metric_date
    ? new Date(data.metric_date).toLocaleDateString(undefined, {
        weekday: 'long',
        month: 'long',
        day: 'numeric'
      })
    : '—';

  const formatValue = (value?: number | null, decimals = 0) =>
    typeof value === 'number' ? value.toFixed(decimals) : '—';

  const PAD_BASE_OFFSET = 650;
  const PAD_VERTICAL_STEP = 700;
  const PAD_EDGE_OFFSET = -68;
  const PAD_SHIFT = 26;

  const metricBlocks = [
    {
      key: 'hrv',
      title: 'HRV',
      value: formatValue(data?.hrv_value_ms),
      subtitle: data?.hrv_note ?? 'Awaiting insight',
      chart: <HRVChart />
    },
    {
      key: 'rhr',
      title: 'Resting HR',
      value: formatValue(data?.rhr_value_bpm),
      subtitle: data?.rhr_note ?? 'Awaiting insight',
      chart: <RHRChart />
    },
    {
      key: 'sleep',
      title: 'Sleep Hours',
      value: formatValue(data?.sleep_value_hours, 2),
      subtitle: data?.sleep_note ?? 'Awaiting insight',
      chart: <SleepChart />
    },
    {
      key: 'load',
      title: 'Training Load',
      value: formatValue(data?.training_load_value),
      subtitle: data?.training_load_note ?? 'Awaiting insight',
      chart: <LoadChart />
    }
  ].map((block, index) => ({
    ...block,
    padSide: index % 2 === 0 ? 'left' : 'right',
    chartAlign: index % 2 === 0 ? 'right' : 'left',
    padTopOffset: PAD_BASE_OFFSET + index * PAD_VERTICAL_STEP
  }));

  const padStackSpacer = PAD_VERTICAL_STEP + 280;

  return (
    <Stage>
      <MetricRow $padSide="left">
        <LilyPadCard
          id="insights-greeting"
          side="center"
          topOffsetPx={0}
          scale={1.5}
          aspectRatio={16 / 4}
          title={`${data?.greeting ?? 'Good morning'}, ${formattedDate}`}
          contentWidthPct={0.9}
        >
          <ReadinessBlock>
            <ReadinessValue data-halo="heading">{formatReadinessValue(data?.readiness_score)}</ReadinessValue>
            <ReadinessLabel>{data?.readiness_label ?? 'Awaiting insight'}</ReadinessLabel>
          </ReadinessBlock>
          <Narrative>{data?.morning_note ?? 'Structured readiness insight is not available yet.'}</Narrative>
        </LilyPadCard>
      </MetricRow>

      {metricBlocks.map((block) => (
        <MetricRow key={block.key} $padSide={block.padSide}>
          <LilyPadCard
            id={`insights-${block.key}`}
            side={block.padSide}
            topOffsetPx={block.padTopOffset}
            scale={1.1}
            edgeOffsetPx={PAD_EDGE_OFFSET}
            sideShiftPercent={PAD_SHIFT}
            title={block.title}
            value={`${block.value}`}
            subtitle={block.subtitle}
            contentWidthPct={0.54}
          />
          <ChartUnderlay $align={block.chartAlign}>
            <Subtitle>{block.title} trend</Subtitle>
            <div style={{ flex: 1 }}>{block.chart}</div>
          </ChartUnderlay>
        </MetricRow>
      ))}
      <PadSpacer style={{ height: `${padStackSpacer}px` }} />
    </Stage>
  );
}

const formatReadinessValue = (score?: number | null) => {
  if (typeof score === 'number') {
    return `${Math.round(score)} / 100`;
  }
  return '— / 100';
};
