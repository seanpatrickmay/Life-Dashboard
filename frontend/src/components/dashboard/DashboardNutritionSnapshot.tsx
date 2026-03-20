import { useState } from 'react';
import styled from 'styled-components';

import { Card } from '../common/Card';
import { useNutritionDailySummary } from '../../hooks/useNutritionIntake';
import { useNutritionSuggestions } from '../../hooks/useNutritionSuggestions';
import type { NutritionSuggestionItem } from '../../services/api';

const Panel = styled(Card)`
  display: flex;
  flex-direction: column;
  gap: 10px;
  box-shadow: 0 0 0 1px ${({ theme }) => theme.colors.borderSubtle}, 0 0 32px rgba(120, 170, 255, 0.35);
`;

const Heading = styled.h3`
  margin: 0;
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: clamp(0.85rem, 1.8vw, 0.95rem);
  letter-spacing: 0.16em;
  text-transform: uppercase;
`;

const MacroList = styled.div`
  display: flex;
  flex-direction: column;
  gap: 8px;
`;

const MacroRow = styled.div`
  display: flex;
  flex-direction: column;
  gap: 4px;
`;

const MacroHeader = styled.div`
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
`;

const Label = styled.span`
  font-size: 0.78rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  opacity: 0.65;
`;

const ValueGroup = styled.span`
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.95rem;
  letter-spacing: 0.02em;
`;

const GoalText = styled.span`
  font-size: 0.78rem;
  opacity: 0.5;
`;

const Bar = styled.div<{ $percent: number }>`
  position: relative;
  width: 100%;
  height: 5px;
  border-radius: 999px;
  overflow: hidden;
  background: ${({ theme }) => theme.colors.overlay};

  &::after {
    content: '';
    position: absolute;
    inset: 0;
    background: ${({ $percent, theme }) => {
      if ($percent > 100) {
        return theme.palette?.ember?.['300'] ?? theme.colors.accent;
      }
      return theme.palette?.pond?.['200'] ?? theme.colors.success;
    }};
    width: ${({ $percent }) => Math.min(100, Math.max(0, $percent))}%;
    transition: width 0.3s ease, background 0.3s ease;
  }
  ${({ $percent, theme }) =>
    $percent > 100
      ? `box-shadow: 0 0 6px ${theme.palette?.ember?.['200'] ?? theme.colors.accent}40;`
      : ''}
`;

const Divider = styled.hr`
  border: none;
  border-top: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  margin: 2px 0;
`;

const SuggestionsLabel = styled.span`
  font-size: 0.68rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  opacity: 0.45;
`;

const SuggestionsRow = styled.div`
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
`;

const QuickPill = styled.button<{ $logged?: boolean }>`
  flex-shrink: 0;
  padding: 4px 10px;
  border-radius: 999px;
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  background: ${({ $logged, theme }) =>
    $logged ? theme.palette?.pond?.['200'] ?? '#7ED7C4' : theme.colors.surfaceRaised};
  color: ${({ $logged, theme }) =>
    $logged ? theme.colors.backgroundPage : theme.colors.textPrimary};
  cursor: pointer;
  font-size: 0.72rem;
  transition: all 0.15s ease;
  white-space: nowrap;

  &:hover {
    background: ${({ $logged, theme }) =>
      $logged
        ? theme.palette?.pond?.['200'] ?? '#7ED7C4'
        : theme.colors.overlayHover};
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: 2px;
  }
`;

const Note = styled.p`
  margin: 0;
  font-size: 0.78rem;
  opacity: 0.7;
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
  const { suggestionsQuery, quickLog, isLogging } = useNutritionSuggestions();
  const [loggedIds, setLoggedIds] = useState<Set<string>>(new Set());
  const nutrients = summaryQuery.data?.nutrients ?? [];
  const suggestions = suggestionsQuery.data?.suggestions ?? [];

  const cards = MACROS.map((macro) => {
    const entry = findEntry(nutrients, macro.keywords);
    const amount = entry?.amount ?? null;
    const goal = entry?.goal ?? null;
    const percent = goal && amount != null ? (amount / goal) * 100 : 0;
    const formatted = amount != null ? Math.round(amount) : null;
    const unit = entry?.unit ?? macro.unit;
    const goalRounded = goal ? Math.round(goal) : null;
    return {
      key: macro.key,
      label: macro.label,
      unit,
      amount: formatted,
      goal: goalRounded,
      percent,
      isMissing: entry == null,
    };
  });

  const missingAll = cards.every((card) => card.isMissing);

  const getKey = (s: NutritionSuggestionItem) =>
    `${s.ingredient_id ?? 'r' + s.recipe_id}`;

  const handleQuickLog = async (s: NutritionSuggestionItem) => {
    const key = getKey(s);
    try {
      await quickLog({
        ingredient_id: s.ingredient_id,
        recipe_id: s.recipe_id,
        quantity: s.quantity,
        unit: s.unit,
      });
      setLoggedIds((prev) => new Set(prev).add(key));
      setTimeout(() => {
        setLoggedIds((prev) => {
          const next = new Set(prev);
          next.delete(key);
          return next;
        });
      }, 2000);
    } catch { /* handled by react-query */ }
  };

  return (
    <Panel>
      <Heading data-halo="heading">Daily Intake</Heading>
      {missingAll && !summaryQuery.isLoading ? (
        <Note>No nutrition entries logged yet today.</Note>
      ) : null}
      <MacroList>
        {cards.map((card) => (
          <MacroRow key={card.key}>
            <MacroHeader>
              <Label data-halo="body">{card.label}</Label>
              <ValueGroup data-halo="heading">
                {summaryQuery.isLoading ? '…' : (
                  <>
                    {card.amount ?? 0}
                    {card.goal != null && (
                      <GoalText> / {card.goal} {card.unit}</GoalText>
                    )}
                    {card.goal == null && <GoalText> {card.unit}</GoalText>}
                  </>
                )}
              </ValueGroup>
            </MacroHeader>
            {!card.isMissing ? <Bar aria-hidden $percent={card.percent ?? 0} /> : null}
          </MacroRow>
        ))}
      </MacroList>
      {suggestions.length > 0 && (
        <>
          <Divider />
          <SuggestionsLabel data-halo="body">Quick log</SuggestionsLabel>
          <SuggestionsRow>
            {suggestions.slice(0, 5).map((s) => {
              const key = getKey(s);
              const logged = loggedIds.has(key);
              return (
                <QuickPill
                  key={key}
                  type="button"
                  $logged={logged}
                  disabled={isLogging || logged}
                  onClick={() => handleQuickLog(s)}
                  title={`${s.quantity} ${s.unit} · ${s.calories_estimate} cal`}
                >
                  {logged ? '✓' : s.name}
                </QuickPill>
              );
            })}
          </SuggestionsRow>
        </>
      )}
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
