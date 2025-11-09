import { useMemo, useState } from 'react';
import styled from 'styled-components';
import { Card } from '../common/Card';
import { useNutritionMenu } from '../../hooks/useNutritionMenu';
import { useNutritionFoods } from '../../hooks/useNutritionFoods';

const PanelHeader = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
`;

const HeaderActions = styled.div`
  display: flex;
  gap: 8px;
  align-items: center;
  font-size: 0.85rem;
  opacity: 0.85;
`;

const ToggleButton = styled.button`
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 999px;
  background: transparent;
  color: ${({ theme }) => theme.colors.textPrimary};
  padding: 6px 12px;
  font-weight: 600;
  cursor: pointer;
  letter-spacing: 0.05em;
`;

const Entries = styled.div`
  display: flex;
  flex-direction: column;
  gap: 10px;
`;

const EntryCard = styled.div`
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.09);
  padding: 10px 12px;
  background: rgba(0, 0, 0, 0.2);
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 10px;
`;

const Field = styled.div`
  display: flex;
  flex-direction: column;
  gap: 4px;

  input {
    width: 100%;
    padding: 6px 8px;
    border-radius: 10px;
    border: 1px solid rgba(255, 255, 255, 0.12);
    background: rgba(0, 0, 0, 0.12);
    color: ${({ theme }) => theme.colors.textPrimary};
  }
`;

const Actions = styled.div`
  display: flex;
  flex-direction: column;
  gap: 6px;

  button {
    border: none;
    border-radius: 999px;
    padding: 6px 10px;
    cursor: pointer;
    font-weight: 600;
  }

  button:first-of-type {
    background: ${({ theme }) => theme.colors.accentPrimary};
    color: #0b0f19;
  }

  button:last-of-type {
    background: rgba(255, 0, 0, 0.18);
    color: ${({ theme }) => theme.colors.textPrimary};
  }
`;

const Collapse = styled.div<{ $expanded: boolean }>`
  display: ${({ $expanded }) => ($expanded ? 'block' : 'none')};
`;

type Draft = Record<
  number,
  {
    quantity: number;
    unit: string;
  }
>;

export function MenuPanel() {
  const { menuQuery, updateEntry, deleteEntry } = useNutritionMenu();
  const { foodsQuery } = useNutritionFoods();
  const [drafts, setDrafts] = useState<Draft>({});
  const [expanded, setExpanded] = useState(false);

  const entries = menuQuery.data?.entries ?? [];
  const foods = foodsQuery.data ?? [];
  const foodMap = useMemo(() => new Map(foods.map((food) => [food.id, food.name])), [foods]);

  const handleChange = (
    id: number,
    field: 'quantity' | 'unit',
    value: string
  ) => {
    setDrafts((prev) => ({
      ...prev,
      [id]: {
        quantity:
          field === 'quantity' ? Number(value) : prev[id]?.quantity ?? 1,
        unit: field === 'unit' ? value : prev[id]?.unit ?? ''
      }
    }));
  };

  const handleSave = async (id: number) => {
    const draft = drafts[id];
    if (!draft) return;
    await updateEntry({ id, ...draft });
    setDrafts((prev) => {
      const next = { ...prev };
      delete next[id];
      return next;
    });
  };

  const handleDelete = async (id: number) => {
    await deleteEntry(id);
    setDrafts((prev) => {
      const next = { ...prev };
      delete next[id];
      return next;
    });
  };

  return (
    <Card>
      <PanelHeader>
        <h3 data-halo="heading">Menu</h3>
        <HeaderActions>
          {!menuQuery.isLoading && entries.length > 0 && (
            <span>{entries.length} {entries.length === 1 ? 'item' : 'items'}</span>
          )}
          <ToggleButton type="button" onClick={() => setExpanded((prev) => !prev)}>
            {expanded ? 'Hide' : 'Show'}
          </ToggleButton>
        </HeaderActions>
      </PanelHeader>
      {menuQuery.isLoading && <p style={{ opacity: 0.7 }}>Loading today&apos;s menu…</p>}
      <Collapse $expanded={expanded}>
        {entries.length === 0 ? (
          <p style={{ opacity: 0.7 }}>No meals logged today.</p>
        ) : (
          <Entries>
            {entries.map((entry) => (
              <EntryCard key={entry.id}>
                <div>
                  <strong>{entry.food_name ?? foodMap.get(entry.food_id)}</strong>
                  <div style={{ fontSize: '0.85rem', opacity: 0.7 }}>
                    Source: {entry.source}
                  </div>
                </div>
                <Actions>
                  <button onClick={() => handleSave(entry.id)}>Save</button>
                  <button onClick={() => handleDelete(entry.id)}>Remove</button>
                </Actions>
                <Field>
                  <label>Quantity</label>
                  <input
                    type="number"
                    step="0.1"
                    value={drafts[entry.id]?.quantity ?? Number(entry.quantity ?? 0)}
                    onChange={(e) => handleChange(entry.id, 'quantity', e.target.value)}
                  />
                </Field>
                <Field>
                  <label>Unit</label>
                  <input
                    value={drafts[entry.id]?.unit ?? entry.unit}
                    onChange={(e) => handleChange(entry.id, 'unit', e.target.value)}
                  />
                </Field>
              </EntryCard>
            ))}
          </Entries>
        )}
      </Collapse>
      {!expanded && entries.length > 0 && (
        <p style={{ opacity: 0.65, fontSize: '0.85rem' }}>
          Expand to adjust the meals Claude logged today.
        </p>
      )}
    </Card>
  );
}
