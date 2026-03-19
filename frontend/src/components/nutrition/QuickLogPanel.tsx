import { useState } from 'react';
import styled from 'styled-components';
import { focusRing } from '../../styles/animations';
import { useNutritionSuggestions } from '../../hooks/useNutritionSuggestions';
import type { NutritionSuggestionItem } from '../../services/api';

const ScrollRow = styled.div`
  display: flex;
  gap: 10px;
  overflow-x: auto;
  padding-bottom: 4px;

  &::-webkit-scrollbar {
    height: 4px;
  }
  &::-webkit-scrollbar-thumb {
    background: ${({ theme }) => theme.colors.scrollThumb};
    border-radius: 2px;
  }
`;

const Pill = styled.button<{ $logged?: boolean }>`
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 16px;
  border-radius: 999px;
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  background: ${({ $logged, theme }) =>
    $logged ? theme.palette?.pond?.['200'] ?? '#7ED7C4' : theme.colors.surfaceRaised};
  color: ${({ $logged, theme }) =>
    $logged ? theme.colors.backgroundPage : theme.colors.textPrimary};
  cursor: pointer;
  transition: all 0.2s ease;
  ${focusRing}

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
`;

const PillName = styled.span`
  font-weight: 600;
  font-size: 0.9rem;
  white-space: nowrap;
`;

const PillMeta = styled.span`
  font-size: 0.75rem;
  opacity: 0.7;
  white-space: nowrap;
`;

const EditOverlay = styled.div`
  display: flex;
  gap: 8px;
  align-items: center;
  margin-top: 8px;

  input {
    width: 60px;
    padding: 4px 8px;
    border-radius: 8px;
    border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
    background: ${({ theme }) => theme.colors.surfaceRaised};
    color: ${({ theme }) => theme.colors.textPrimary};
    font-size: 0.85rem;
    ${focusRing}
  }
`;

const EditButton = styled.button`
  background: none;
  border: none;
  cursor: pointer;
  font-size: 0.75rem;
  opacity: 0.5;
  padding: 2px 6px;
  color: ${({ theme }) => theme.colors.textPrimary};
  ${focusRing}

  &:hover {
    opacity: 1;
  }
`;

const LogButton = styled.button`
  padding: 4px 10px;
  border-radius: 999px;
  border: none;
  background: ${({ theme }) => theme.palette?.pond?.['200'] ?? '#7ED7C4'};
  color: ${({ theme }) => theme.colors.backgroundPage};
  font-weight: 600;
  font-size: 0.8rem;
  cursor: pointer;
  ${focusRing}
`;

const EmptyState = styled.p`
  font-size: 0.85rem;
  opacity: 0.6;
  margin: 0;
`;

const SkeletonPill = styled.div`
  flex-shrink: 0;
  width: 140px;
  height: 52px;
  border-radius: 999px;
  background: ${({ theme }) => theme.colors.overlay};
  animation: pulse 1.5s ease-in-out infinite;

  @keyframes pulse {
    0%, 100% { opacity: 0.4; }
    50% { opacity: 0.7; }
  }
`;

export function QuickLogPanel() {
  const { suggestionsQuery, quickLog, isLogging } = useNutritionSuggestions();
  const [loggedIds, setLoggedIds] = useState<Set<string>>(new Set());
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editQuantity, setEditQuantity] = useState<number>(0);
  const [editUnit, setEditUnit] = useState<string>('');

  const suggestions = suggestionsQuery.data?.suggestions ?? [];

  const getSuggestionKey = (s: NutritionSuggestionItem) =>
    `${s.ingredient_id ?? 'r' + s.recipe_id}`;

  const handleQuickLog = async (s: NutritionSuggestionItem, qty?: number, unit?: string) => {
    const key = getSuggestionKey(s);
    try {
      await quickLog({
        ingredient_id: s.ingredient_id,
        recipe_id: s.recipe_id,
        quantity: qty ?? s.quantity,
        unit: unit ?? s.unit,
      });
      setLoggedIds((prev) => new Set(prev).add(key));
      setEditingId(null);
      setTimeout(() => {
        setLoggedIds((prev) => {
          const next = new Set(prev);
          next.delete(key);
          return next;
        });
      }, 2000);
    } catch {
      // mutation error handled by react-query
    }
  };

  const handleEditClick = (s: NutritionSuggestionItem) => {
    const key = getSuggestionKey(s);
    if (editingId === key) {
      setEditingId(null);
    } else {
      setEditingId(key);
      setEditQuantity(s.quantity);
      setEditUnit(s.unit);
    }
  };

  if (suggestionsQuery.isLoading) {
    return (
      <ScrollRow>
        {Array.from({ length: 5 }).map((_, i) => (
          <SkeletonPill key={i} />
        ))}
      </ScrollRow>
    );
  }

  if (suggestions.length === 0) {
    return <EmptyState>Log a few meals to get personalized suggestions.</EmptyState>;
  }

  return (
    <>
      <ScrollRow>
        {suggestions.map((s) => {
          const key = getSuggestionKey(s);
          const logged = loggedIds.has(key);
          return (
            <div key={key} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
              <Pill
                type="button"
                $logged={logged}
                disabled={isLogging || logged}
                onClick={() => handleQuickLog(s)}
                title={s.reason}
              >
                <PillName>{logged ? 'Logged!' : s.name}</PillName>
                <PillMeta>
                  {s.quantity} {s.unit} · {s.calories_estimate} cal
                </PillMeta>
              </Pill>
              {!logged && (
                <EditButton type="button" onClick={() => handleEditClick(s)}>
                  edit
                </EditButton>
              )}
            </div>
          );
        })}
      </ScrollRow>
      {editingId && (() => {
        const s = suggestions.find((s) => getSuggestionKey(s) === editingId);
        if (!s) return null;
        return (
          <EditOverlay>
            <input
              type="number"
              step="0.1"
              value={editQuantity}
              onChange={(e) => setEditQuantity(Number(e.target.value))}
              aria-label="Quantity"
            />
            <input
              value={editUnit}
              onChange={(e) => setEditUnit(e.target.value)}
              aria-label="Unit"
              style={{ width: 80 }}
            />
            <LogButton
              type="button"
              disabled={isLogging}
              onClick={() => handleQuickLog(s, editQuantity, editUnit)}
            >
              Log
            </LogButton>
          </EditOverlay>
        );
      })()}
    </>
  );
}
