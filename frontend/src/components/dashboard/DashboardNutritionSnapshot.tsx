import styled from 'styled-components';

import { Card } from '../common/Card';
import { useNutritionDailySummary } from '../../hooks/useNutritionIntake';

const Panel = styled(Card)`
  display: flex;
  flex-direction: column;
  gap: clamp(12px, 2vw, 18px);
  box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.18), 0 0 32px rgba(120, 170, 255, 0.35);
`;

const Heading = styled.h3`
  margin: 0;
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: clamp(0.95rem, 2vw, 1.1rem);
  letter-spacing: 0.16em;
  text-transform: uppercase;
`;

const Grid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: clamp(12px, 2vw, 18px);
`;

const MacroCard = styled.div`
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: clamp(10px, 2vw, 14px);
  border-radius: 18px;
  background: rgba(0, 0, 0, 0.18);
  border: 1px solid rgba(255, 255, 255, 0.2);
`;

const Label = styled.span`
  font-size: 0.85rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  opacity: 0.8;
`;

const Amount = styled.div`
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: clamp(1.8rem, 4vw, 2.6rem);
`;

const Goal = styled.span`
  font-size: 0.9rem;
  opacity: 0.8;
`;

const Bar = styled.div<{ $percent: number }>`
  position: relative;
  width: 100%;
  height: 8px;
  border-radius: 999px;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.15);

  &::after {
    content: '';
    position: absolute;
    inset: 0;
    background: ${({ theme }) => theme.colors.accent ?? '#f5d37c'};
    width: ${({ $percent }) => Math.min(100, Math.max(0, $percent))}%;
  }
`;

const Note = styled.p`
  margin: 0;
  font-size: 0.85rem;
  opacity: 0.8;
`;

const MACROS = [
  {
    key: 'energy',
    label: 'Calories',
    unit: 'kcal',
    keywords: ['calorie', 'calories', 'energy', 'kcal'],
  },
  {
    key: 'protein',
    label: 'Protein',
    unit: 'g',
    keywords: ['protein'],
  },
  {
    key: 'carbohydrates',
    label: 'Carbs',
    unit: 'g',
    keywords: ['carb', 'carbs', 'carbohydrate'],
  },
] as const;

export function DashboardNutritionSnapshot() {
  const summaryQuery = useNutritionDailySummary();
  const nutrients = summaryQuery.data?.nutrients ?? [];

  const cards = MACROS.map((macro) => {
    const entry = findEntry(nutrients, macro.keywords);
    const amount = entry?.amount ?? null;
    const goal = entry?.goal ?? null;
    const percent = goal && amount != null ? (amount / goal) * 100 : 0;
    const formatted = amount != null ? Math.round(amount) : null;
    const goalLabel = goal ? `${goal} ${entry?.unit ?? macro.unit}` : '—';
    return {
      key: macro.key,
      label: macro.label,
      display: formatted != null ? `${formatted} ${entry?.unit ?? macro.unit}` : '—',
      goal: goalLabel,
      percent,
      isMissing: entry == null,
    };
  });

  const missingAll = cards.every((card) => card.isMissing);

  return (
    <Panel>
      <Heading data-halo="heading">Today&apos;s Intake</Heading>
      {missingAll && !summaryQuery.isLoading ? (
        <Note>No nutrition entries logged yet today.</Note>
      ) : null}
      <Grid>
        {cards.map((card) => (
          <MacroCard key={card.key}>
            <Label data-halo="body">{card.label}</Label>
            <Amount data-halo="heading">{summaryQuery.isLoading ? '…' : card.display}</Amount>
            <Goal data-halo="body">Goal: {card.goal}</Goal>
            {!card.isMissing ? <Bar aria-hidden $percent={card.percent ?? 0} /> : null}
          </MacroCard>
        ))}
      </Grid>
    </Panel>
  );
}

function findEntry(
  nutrients: Array<{
    slug: string;
    display_name: string;
    group: string;
    unit: string;
    amount: number | null;
    goal: number | null;
    percent_of_goal: number | null;
  }>,
  keywords: readonly string[]
) {
  return nutrients.find((item) => {
    const haystack = `${item.slug} ${item.display_name}`.toLowerCase();
    return keywords.some((needle) => haystack.includes(needle));
  });
}
