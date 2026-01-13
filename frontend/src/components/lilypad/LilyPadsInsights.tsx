import { useState } from 'react';
import styled from 'styled-components';
import { useInsight } from '../../hooks/useInsight';
import { LilyPadCard } from './LilyPadCard';
import { HRVChart } from '../charts/HRVChart';
import { RHRChart } from '../charts/RHRChart';
import { SleepChart } from '../charts/SleepChart';
import { LoadChart } from '../charts/LoadChart';

const Stage = styled.div`
  position: relative;
  display: flex;
  flex-direction: column;
  padding: clamp(24px, 5vh, 60px) clamp(16px, 6vw, 80px) clamp(140px, 18vh, 220px);
  color: #ffffff;
`;

const Subtitle = styled.span`
  display: block;
  font-size: 0.8rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: rgba(255, 255, 255, 0.85);
  margin-bottom: 0;
`;

const MetricSection = styled.section`
  margin-top: clamp(80px, 12vh, 140px);
  display: grid;
  width: min(1200px, 100%);
  margin-left: auto;
  margin-right: auto;
  grid-template-columns: minmax(0, 1.2fr) minmax(0, 0.8fr);
  gap: clamp(28px, 5vw, 96px);
  align-items: start;
  @media (max-width: 1100px) {
    grid-template-columns: 1fr;
    margin-top: clamp(60px, 10vh, 120px);
  }
`;

const MetricPadStack = styled.div`
  position: relative;
  min-height: clamp(320px, 46vh, 520px);
  padding-top: clamp(260px, 28vw, 380px);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  --bridge-band-bottom: 0px;
  width: min(760px, 100%);
  justify-self: start;
  @media (max-width: 1100px) {
    width: 100%;
    margin: 0 auto;
  }
`;

const MetricToggleRow = styled.div`
  display: flex;
  flex-wrap: nowrap;
  gap: 6px;
  justify-content: flex-end;
  overflow-x: auto;
  scrollbar-width: none;
  &::-webkit-scrollbar {
    display: none;
  }
`;

const MetricToggleButton = styled.button<{ $active?: boolean }>`
  border: 1px solid rgba(255, 255, 255, 0.35);
  border-radius: 999px;
  padding: 4px 9px;
  font-size: 0.6rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  cursor: pointer;
  color: #ffffff;
  background: ${({ $active }) => ($active ? 'rgba(255, 255, 255, 0.22)' : 'rgba(8, 16, 30, 0.45)')};
  transition: opacity 0.2s ease, transform 0.2s ease;
  &:hover {
    opacity: 0.9;
    transform: translateY(-1px);
  }
`;

const ChartHeader = styled.div`
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 8px;
`;

const ChartBody = styled.div`
  position: relative;
  flex: 1;
  margin-top: 10px;
  padding: 12px 18px 20px;
  border-radius: 24px;
  overflow: hidden;
`;

const ChartWater = styled.div`
  position: absolute;
  inset: 0;
  background:
    linear-gradient(180deg, rgba(9, 22, 36, 0.08) 0%, rgba(6, 20, 34, 0.45) 55%, rgba(3, 12, 22, 0.75) 100%),
    radial-gradient(circle at 20% 30%, rgba(122, 197, 220, 0.18), transparent 55%),
    radial-gradient(circle at 80% 70%, rgba(90, 140, 210, 0.24), transparent 60%);
  opacity: 0.85;
  mix-blend-mode: screen;
  pointer-events: none;
`;

const ChartDepth = styled.div`
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, rgba(2, 8, 14, 0) 0%, rgba(2, 8, 14, 0.4) 55%, rgba(2, 8, 14, 0.65) 100%);
  opacity: 0.9;
  mix-blend-mode: multiply;
  pointer-events: none;
`;

const ChartContent = styled.div`
  position: relative;
  z-index: 1;
  height: 100%;
`;

const ChartUnderlay = styled.div`
  width: 100%;
  max-width: 620px;
  min-height: clamp(240px, 40vh, 360px);
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
  justify-self: end;
  &::before {
    content: '';
    position: absolute;
    inset: 56px -10% -40% -10%;
    background: radial-gradient(circle at 30% 20%, rgba(255, 255, 255, 0.18), transparent 60%),
      radial-gradient(circle at 70% 10%, rgba(173, 216, 255, 0.2), transparent 55%);
    opacity: 0.7;
    mix-blend-mode: screen;
    pointer-events: none;
  }
  &::after {
    content: '';
    position: absolute;
    inset: 56px 0 0 0;
    background: linear-gradient(180deg, rgba(4, 9, 18, 0.35), rgba(6, 12, 24, 0.85));
    opacity: 0.9;
    mix-blend-mode: multiply;
    pointer-events: none;
  }
  > * {
    position: relative;
    z-index: 1;
  }
  @media (max-width: 1100px) {
    width: 100%;
    justify-self: center;
  }
`;

export function LilyPadsInsights() {
  const { data } = useInsight();
  const [activeKey, setActiveKey] = useState('hrv');

  const formatValue = (value?: number | null, decimals = 0) =>
    typeof value === 'number' ? value.toFixed(decimals) : '—';

  const metricBlocks = [
    {
      key: 'hrv',
      title: 'HRV',
      value: formatValue(data?.hrv_value_ms),
      subtitle: data?.hrv_note ?? 'Awaiting insight',
      chart: <HRVChart variant="bare" />
    },
    {
      key: 'rhr',
      title: 'Resting HR',
      value: formatValue(data?.rhr_value_bpm),
      subtitle: data?.rhr_note ?? 'Awaiting insight',
      chart: <RHRChart variant="bare" />
    },
    {
      key: 'sleep',
      title: 'Sleep Hours',
      value: formatValue(data?.sleep_value_hours, 2),
      subtitle: data?.sleep_note ?? 'Awaiting insight',
      chart: <SleepChart variant="bare" />
    },
    {
      key: 'load',
      title: 'Training Load',
      value: formatValue(data?.training_load_value),
      subtitle: data?.training_load_note ?? 'Awaiting insight',
      chart: <LoadChart variant="bare" />
    }
  ];

  const activeMetric = metricBlocks.find((metric) => metric.key === activeKey) ?? metricBlocks[0];

  return (
    <Stage>
      <MetricSection>
        <MetricPadStack>
          <LilyPadCard
            id={`insights-${activeMetric.key}`}
            side="center"
            topOffsetPx={0}
            scale={1.28}
            padWidth="clamp(420px, 56vw, 760px)"
            centerShiftPx={-40}
            title={activeMetric.title}
            value={`${activeMetric.value}`}
            subtitle={activeMetric.subtitle}
            contentWidthPct={0.68}
          />
        </MetricPadStack>
        <ChartUnderlay>
          <ChartHeader>
            <Subtitle>{activeMetric.title} trend</Subtitle>
            <MetricToggleRow>
              {metricBlocks.map((metric) => (
                <MetricToggleButton
                  key={metric.key}
                  type="button"
                  $active={metric.key === activeKey}
                  aria-pressed={metric.key === activeKey}
                  onClick={() => setActiveKey(metric.key)}
                >
                  {metric.title}
                </MetricToggleButton>
              ))}
            </MetricToggleRow>
          </ChartHeader>
          <ChartBody>
            <ChartWater />
            <ChartDepth />
            <ChartContent>{activeMetric.chart}</ChartContent>
          </ChartBody>
        </ChartUnderlay>
      </MetricSection>
    </Stage>
  );
}
