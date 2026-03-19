import styled from 'styled-components';
import { Card as BaseCard } from '../common/Card';
import { useTodos } from '../../hooks/useTodos';
import { useNutritionDailySummary } from '../../hooks/useNutritionIntake';
import { useCalendarEvents } from '../../hooks/useCalendar';
import { fadeUp, reducedMotion } from '../../styles/animations';

const ContextGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: clamp(12px, 2vw, 20px);
`;

const ContextCard = styled(BaseCard)`
  padding: clamp(14px, 2vw, 20px);
  display: flex;
  flex-direction: column;
  gap: 8px;
  animation: ${fadeUp} 0.4s ease-out both;
  ${reducedMotion}
`;

const ContextLabel = styled.span`
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.8rem;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: ${({ theme }) => theme.colors.textSecondary};
`;

const ContextValue = styled.div`
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 1.4rem;
  line-height: 1;
  color: ${({ theme }) => theme.colors.textPrimary};
`;

const ContextDetail = styled.span`
  font-size: 0.85rem;
  color: ${({ theme }) => theme.colors.textSecondary};
`;

const SectionLabel = styled.div`
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.85rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: ${({ theme }) => theme.colors.textSecondary};
`;

export function LifeContextPanel() {
  const { todosQuery } = useTodos();
  const { data: nutritionData } = useNutritionDailySummary();

  const today = new Date();
  const startOfDay = new Date(today.getFullYear(), today.getMonth(), today.getDate()).toISOString();
  const endOfDay = new Date(today.getFullYear(), today.getMonth(), today.getDate() + 1).toISOString();
  const { eventsQuery } = useCalendarEvents(startOfDay, endOfDay);

  // Todos
  const todos = todosQuery.data ?? [];
  const totalActive = todos.filter(t => !t.completed).length;
  const completed = todos.filter(t => t.completed).length;
  const overdue = todos.filter(t => t.is_overdue).length;

  // Nutrition — find key macros
  const nutrients = nutritionData?.nutrients ?? [];
  const energy = nutrients.find(n => n.slug === 'energy_kcal');
  const protein = nutrients.find(n => n.slug === 'protein_g');
  const energyPct = energy?.percent_of_goal;

  // Calendar
  const eventCount = eventsQuery.data?.events?.length ?? 0;

  // Only render if we have at least some data
  const hasAnyData = todosQuery.data || nutritionData || eventsQuery.data;
  if (!hasAnyData) return null;

  return (
    <div>
      <SectionLabel data-halo="heading">Life Context</SectionLabel>
      <ContextGrid style={{ marginTop: '12px' }}>
        {/* Tasks */}
        <ContextCard>
          <ContextLabel data-halo="heading">Tasks</ContextLabel>
          <ContextValue>{totalActive} active</ContextValue>
          <ContextDetail>
            {completed} done{overdue > 0 ? ` · ${overdue} overdue` : ''}
          </ContextDetail>
        </ContextCard>

        {/* Nutrition */}
        <ContextCard>
          <ContextLabel data-halo="heading">Nutrition</ContextLabel>
          <ContextValue>
            {energyPct != null ? `${Math.round(energyPct)}%` : '—'}
          </ContextValue>
          <ContextDetail>
            {energy ? `${Math.round(energy.amount ?? 0)} / ${Math.round(energy.goal ?? 0)} kcal` : 'No data'}
            {protein && protein.amount != null ? ` · ${Math.round(protein.amount)}g protein` : ''}
          </ContextDetail>
        </ContextCard>

        {/* Calendar */}
        <ContextCard>
          <ContextLabel data-halo="heading">Schedule</ContextLabel>
          <ContextValue>
            {eventCount} event{eventCount !== 1 ? 's' : ''}
          </ContextValue>
          <ContextDetail>
            {eventCount >= 5 ? 'Heavy day' : eventCount >= 3 ? 'Moderate day' : eventCount > 0 ? 'Light day' : 'Clear day'}
          </ContextDetail>
        </ContextCard>

        {/* Energy expenditure - show if nutrition has data, otherwise skip */}
        {energy && energy.goal != null && (
          <ContextCard>
            <ContextLabel data-halo="heading">Balance</ContextLabel>
            <ContextValue>
              {protein?.percent_of_goal != null ? `${Math.round(protein.percent_of_goal)}%` : '—'}
            </ContextValue>
            <ContextDetail>protein target</ContextDetail>
          </ContextCard>
        )}
      </ContextGrid>
    </div>
  );
}
