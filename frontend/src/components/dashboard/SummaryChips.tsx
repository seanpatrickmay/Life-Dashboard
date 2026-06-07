import styled from 'styled-components';
import { Link } from 'react-router-dom';
import { addDays } from 'date-fns';

import { useCalendarEvents } from '../../hooks/useCalendar';
import { useNutritionDailySummary } from '../../hooks/useNutritionIntake';
import { fadeUp, reducedMotion } from '../../styles/animations';
import { SecondaryNavCTAs } from './SecondaryNavCTAs';

// ── Styled components ─────────────────────────────────────────────────────────

const Row = styled.div`
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  animation: ${fadeUp} 0.35s ease-out 0.1s both;
  ${reducedMotion}
`;

const Chip = styled(Link)`
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  min-height: 44px;
  box-sizing: border-box;
  border-radius: 999px;
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  background: ${({ theme }) => theme.colors.overlay};
  color: ${({ theme }) => theme.colors.textPrimary};
  font-family: ${({ theme }) => theme.fonts.body};
  font-size: 0.82rem;
  letter-spacing: 0.02em;
  text-decoration: none;
  transition: background 0.15s ease, border-color 0.15s ease;
  ${reducedMotion}

  &:hover {
    background: ${({ theme }) => theme.colors.overlayHover};
    border-color: ${({ theme }) => theme.colors.accent}66;
  }

  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: 2px;
  }
`;

const ChipLabel = styled.span`
  opacity: 0.65;
  font-size: 0.72rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
`;

const ChipValue = styled.strong`
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.9rem;
`;


const Wrapper = styled.div`
  display: flex;
  flex-direction: column;
  gap: 10px;
`;

// ── Component ─────────────────────────────────────────────────────────────────

export function SummaryChips() {
  const today = new Date();
  const startDate = today.toISOString().split('T')[0];
  const endDate = addDays(today, 1).toISOString().split('T')[0];

  const { eventsQuery } = useCalendarEvents(startDate, endDate);
  const nutritionQuery = useNutritionDailySummary();

  // Count today's events only
  const todayEvents = (eventsQuery.data?.events ?? []).filter((ev) => {
    if (!ev.start_time) return false;
    const d = new Date(ev.start_time);
    return (
      d.getFullYear() === today.getFullYear() &&
      d.getMonth() === today.getMonth() &&
      d.getDate() === today.getDate()
    );
  });
  const eventCount = todayEvents.length;

  // Calories from nutrition summary
  const nutrients = nutritionQuery.data?.nutrients ?? [];
  const energyEntry = nutrients.find((n) => {
    const h = `${n.slug} ${n.display_name}`.toLowerCase();
    return ['calorie', 'energy', 'kcal'].some((k) => h.includes(k));
  });
  const energyAmount = energyEntry?.amount;
  const kcal = typeof energyAmount === 'number' && Number.isFinite(energyAmount) ? Math.round(energyAmount) : null;

  return (
    <Wrapper data-testid="summary-chips">
      <Row>
        <Chip to="/calendar" aria-label={`${eventCount} event${eventCount !== 1 ? 's' : ''} today — open calendar`}>
          <ChipLabel>Events</ChipLabel>
          <ChipValue>{eventsQuery.isLoading ? '…' : eventCount}</ChipValue>
        </Chip>

        <Chip to="/body" aria-label={`${kcal ?? '—'} kcal logged today — open body`}>
          <ChipLabel>Intake</ChipLabel>
          <ChipValue>
            {nutritionQuery.isLoading ? '…' : kcal != null ? `${kcal} kcal` : '— kcal'}
          </ChipValue>
        </Chip>
      </Row>

      <SecondaryNavCTAs />
    </Wrapper>
  );
}
