import { useMemo, useState } from 'react';
import styled from 'styled-components';
import { LilyPadCard } from './LilyPadCard';
import { useNutritionDailySummary, useNutritionHistory } from '../../hooks/useNutritionIntake';
import { useNutritionGoals } from '../../hooks/useNutritionGoals';
import { GROUP_LABELS, GROUP_ORDER, type GroupKey } from '../nutrition/NutrientGroupUI';
import type { NutritionGoal } from '../../services/api';

const Stage = styled.div`
  position: relative;
  min-height: calc(100vh + 180px);
  padding-bottom: 220px;
  color: #ffffff;
`;

const NutritionSection = styled.section`
  margin-top: clamp(40px, 6vh, 80px);
  display: grid;
  width: min(1200px, 100%);
  margin-left: auto;
  margin-right: auto;
  grid-template-columns: minmax(0, 1.15fr) minmax(0, 0.85fr);
  gap: clamp(28px, 5vw, 96px);
  align-items: start;
  @media (max-width: 1100px) {
    grid-template-columns: 1fr;
  }
`;

const PadSlot = styled.div<{ $maxWidth: string; $align: 'start' | 'end' }>`
  position: relative;
  min-height: clamp(340px, 48vh, 520px);
  width: 100%;
  max-width: ${({ $maxWidth }) => $maxWidth};
  justify-self: ${({ $align }) => $align};
  --bridge-band-bottom: 0px;
  @media (max-width: 1100px) {
    justify-self: center;
    max-width: min(720px, 100%);
  }
`;

const SelectorStack = styled.div`
  display: flex;
  flex-direction: column;
  gap: 14px;
  text-align: left;
`;

const SectionHeader = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
`;

const SectionTitle = styled.div`
  font-family: ${({ theme }) => theme.fonts.heading};
  text-transform: uppercase;
  letter-spacing: 0.12em;
  font-size: 0.8rem;
`;

const GroupButtonGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
`;

const SelectorButton = styled.button<{ $active?: boolean }>`
  border: 1px solid rgba(255, 255, 255, 0.35);
  border-radius: 18px;
  padding: 12px 14px;
  font-size: 0.75rem;
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

const NutrientGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 10px;
`;

const BackButton = styled.button`
  border: 1px solid rgba(255, 255, 255, 0.3);
  background: rgba(0, 0, 0, 0.2);
  color: ${({ theme }) => theme.colors.textPrimary};
  border-radius: 16px;
  padding: 6px 12px;
  font-size: 0.7rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  cursor: pointer;
`;

const HelperText = styled.p`
  margin: 0;
  font-size: 0.82rem;
  opacity: 0.78;
`;

const StatList = styled.div`
  display: flex;
  flex-direction: column;
  gap: 12px;
  text-align: center;
  align-items: center;
`;

const StatItem = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding-bottom: 6px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.12);
  width: 100%;
  &:last-of-type {
    border-bottom: none;
  }
`;

const StatLabel = styled.span`
  font-size: 0.9rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  opacity: 0.85;
  text-shadow: 0 2px 10px rgba(4, 12, 24, 0.55);
`;

const StatValue = styled.span`
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 1.45rem;
  text-shadow: 0 2px 12px rgba(4, 12, 24, 0.65);
`;

const formatPercent = (value?: number | null) => {
  if (value == null) return '—';
  return `${Math.round(value)}%`;
};

const formatAmount = (amount?: number | null, unit?: string | null) => {
  if (amount == null || Number.isNaN(amount)) return '—';
  const rounded = Math.round(amount * 100) / 100;
  return `${rounded}${unit ? ` ${unit}` : ''}`;
};

const buildOptionsFromGoals = (goals: NutritionGoal[], group: GroupKey) =>
  goals
    .filter((goal) => (goal.group as GroupKey) === group)
    .map((goal) => ({ slug: goal.slug, label: goal.display_name }))
    .sort((a, b) => a.label.localeCompare(b.label));

export function LilyPadsNutrition() {
  const { data: summaryData, isLoading: summaryLoading } = useNutritionDailySummary();
  const { data: historyData, isLoading: historyLoading } = useNutritionHistory();
  const { goalsQuery } = useNutritionGoals();
  const [selectedGroup, setSelectedGroup] = useState<GroupKey | null>(null);
  const [selectedNutrient, setSelectedNutrient] = useState<string | null>(null);

  const goals = goalsQuery.data ?? [];

  const nutrientOptions = useMemo(() => {
    if (!selectedGroup) return [];
    const goalOptions = buildOptionsFromGoals(goals, selectedGroup);
    if (goalOptions.length) return goalOptions;
    const summaryOptions = (summaryData?.nutrients ?? [])
      .filter((nutrient) => (nutrient.group as GroupKey) === selectedGroup)
      .map((nutrient) => ({ slug: nutrient.slug, label: nutrient.display_name }))
      .sort((a, b) => a.label.localeCompare(b.label));
    return summaryOptions;
  }, [goals, selectedGroup, summaryData]);

  const selectedSummary = useMemo(
    () => summaryData?.nutrients?.find((nutrient) => nutrient.slug === selectedNutrient) ?? null,
    [summaryData, selectedNutrient]
  );
  const selectedHistory = useMemo(
    () => historyData?.nutrients?.find((nutrient) => nutrient.slug === selectedNutrient) ?? null,
    [historyData, selectedNutrient]
  );
  const selectedGoal = useMemo(
    () => goals.find((goal) => goal.slug === selectedNutrient) ?? null,
    [goals, selectedNutrient]
  );

  const selectedOption = nutrientOptions.find((option) => option.slug === selectedNutrient) ?? null;
  const detailTitle =
    selectedOption?.label ??
    selectedSummary?.display_name ??
    selectedGoal?.display_name ??
    selectedHistory?.display_name ??
    'Nutrient Detail';
  const currentPercent = selectedSummary?.percent_of_goal ?? null;
  const averagePercent = selectedHistory?.percent_of_goal ?? null;
  const goalAmount = selectedSummary?.goal ?? selectedGoal?.goal ?? null;
  const goalUnit = selectedSummary?.unit ?? selectedGoal?.unit ?? selectedHistory?.unit ?? '';
  const windowDays = historyData?.window_days ?? 14;

  const showGroupPicker = selectedGroup === null;

  return (
    <Stage>
      <NutritionSection>
        <PadSlot $align="start" $maxWidth="860px">
          <LilyPadCard
            id="nutrition-group-selector"
            side="center"
            topOffsetPx={238}
            scale={1.26}
            padWidth="100%"
            title={selectedGroup ? GROUP_LABELS[selectedGroup] : 'Nutrient Groups'}
            contentScale={0.87}
            interactive
            edgeOffsetPx={0}
            sideShiftPercent={0}
            contentWidthPct={0.78}
          >
            <SelectorStack>
              {showGroupPicker ? (
                <>
                  <SectionTitle>Select a nutrient group</SectionTitle>
                  <GroupButtonGrid>
                    {GROUP_ORDER.map((group) => (
                      <SelectorButton
                        key={group}
                        type="button"
                        onClick={() => {
                          setSelectedGroup(group);
                          setSelectedNutrient(null);
                        }}
                      >
                        {GROUP_LABELS[group]}
                      </SelectorButton>
                    ))}
                  </GroupButtonGrid>
                </>
              ) : (
                <>
                  <SectionHeader>
                    <SectionTitle>{GROUP_LABELS[selectedGroup]}</SectionTitle>
                    <BackButton
                      type="button"
                      onClick={() => {
                        setSelectedGroup(null);
                        setSelectedNutrient(null);
                      }}
                    >
                      Back
                    </BackButton>
                  </SectionHeader>
                  {goalsQuery.isLoading || summaryLoading ? (
                    <HelperText>Loading nutrients…</HelperText>
                  ) : nutrientOptions.length === 0 ? (
                    <HelperText>No nutrients available for this group yet.</HelperText>
                  ) : (
                    <NutrientGrid>
                      {nutrientOptions.map((option) => (
                        <SelectorButton
                          key={option.slug}
                          type="button"
                          $active={option.slug === selectedNutrient}
                          onClick={() => setSelectedNutrient(option.slug)}
                        >
                          {option.label}
                        </SelectorButton>
                      ))}
                    </NutrientGrid>
                  )}
                </>
              )}
            </SelectorStack>
          </LilyPadCard>
        </PadSlot>
        <PadSlot $align="end" $maxWidth="560px">
          <LilyPadCard
            id="nutrition-nutrient-detail"
            side="center"
            topOffsetPx={326}
            scale={1.12}
            padWidth="100%"
            title={detailTitle}
            contentScale={0.87}
            interactive
            edgeOffsetPx={0}
            sideShiftPercent={0}
            contentWidthPct={0.72}
          >
            {selectedNutrient ? (
              <StatList>
                <StatItem>
                  <StatLabel>Today</StatLabel>
                  <StatValue>{formatPercent(currentPercent)}</StatValue>
                </StatItem>
                <StatItem>
                  <StatLabel>{windowDays}-Day Avg</StatLabel>
                  <StatValue>{formatPercent(averagePercent)}</StatValue>
                </StatItem>
                <StatItem>
                  <StatLabel>Goal Today</StatLabel>
                  <StatValue>{formatAmount(goalAmount, goalUnit)}</StatValue>
                </StatItem>
                {summaryLoading || historyLoading ? (
                  <HelperText>Refreshing nutrient insights…</HelperText>
                ) : null}
              </StatList>
            ) : (
              <HelperText>Select a nutrient to see daily progress and averages.</HelperText>
            )}
          </LilyPadCard>
        </PadSlot>
      </NutritionSection>
    </Stage>
  );
}
