import styled from 'styled-components';
import { useTodos } from '../../hooks/useTodos';
import { useNutritionDailySummary } from '../../hooks/useNutritionIntake';
import { useCalendarEvents } from '../../hooks/useCalendar';

const Strip = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: clamp(12px, 2vw, 20px);
  padding: clamp(10px, 1.5vw, 14px) 0;
`;

const Chip = styled.div`
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.78rem;
  color: ${({ theme }) => theme.colors.textSecondary};
  letter-spacing: 0.06em;
`;

const ChipLabel = styled.span`
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.7rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  opacity: 0.6;
`;

const ChipValue = styled.span`
  font-variant-numeric: tabular-nums;
`;

const Separator = styled.span`
  color: ${({ theme }) => theme.colors.borderSubtle};
  font-size: 0.65rem;
`;

export function LifeContextPanel() {
  const { todosQuery } = useTodos();
  const { data: nutritionData } = useNutritionDailySummary();

  const today = new Date();
  const startOfDay = new Date(today.getFullYear(), today.getMonth(), today.getDate()).toISOString();
  const endOfDay = new Date(today.getFullYear(), today.getMonth(), today.getDate() + 1).toISOString();
  const { eventsQuery } = useCalendarEvents(startOfDay, endOfDay);

  const todos = todosQuery.data ?? [];
  const active = todos.filter(t => !t.completed).length;
  const overdue = todos.filter(t => t.is_overdue).length;

  const nutrients = nutritionData?.nutrients ?? [];
  const energy = nutrients.find(n => n.slug === 'energy_kcal');
  const protein = nutrients.find(n => n.slug === 'protein_g');
  const energyPct = energy?.percent_of_goal;

  const eventCount = eventsQuery.data?.events?.length ?? 0;

  const hasAnyData = todosQuery.data || nutritionData || eventsQuery.data;
  if (!hasAnyData) return null;

  const chips: { label: string; value: string }[] = [];

  if (todosQuery.data) {
    let val = `${active} active`;
    if (overdue > 0) val += `, ${overdue} overdue`;
    chips.push({ label: 'Tasks', value: val });
  }

  if (energy) {
    const pct = energyPct != null ? `${Math.round(energyPct)}%` : '—';
    const detail = protein?.amount != null ? ` · ${Math.round(protein.amount)}g protein` : '';
    chips.push({ label: 'Nutrition', value: `${pct} kcal goal${detail}` });
  }

  if (eventsQuery.data) {
    chips.push({ label: 'Schedule', value: `${eventCount} event${eventCount !== 1 ? 's' : ''}` });
  }

  if (chips.length === 0) return null;

  return (
    <Strip>
      {chips.map((chip, i) => (
        <Chip key={chip.label}>
          {i > 0 && <Separator>·</Separator>}
          <ChipLabel>{chip.label}</ChipLabel>
          <ChipValue>{chip.value}</ChipValue>
        </Chip>
      ))}
    </Strip>
  );
}
