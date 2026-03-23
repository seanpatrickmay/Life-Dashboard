import { useMemo, useState } from 'react';
import styled from 'styled-components';
import { focusRing } from '../../styles/animations';
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
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  border-radius: 999px;
  background: transparent;
  color: ${({ theme }) => theme.colors.textPrimary};
  padding: 10px 12px;
  font-weight: 600;
  cursor: pointer;
  letter-spacing: 0.05em;
  ${focusRing}
`;

const Entries = styled.div`
  display: flex;
  flex-direction: column;
  gap: 10px;
`;

const EntryCard = styled.div`
  border-radius: 16px;
  border: 1px solid ${({ theme }) => theme.colors.overlay};
  padding: 10px 12px;
  background: ${({ theme }) => theme.colors.surfaceRaised};
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 10px;
`;

const RecipeGroup = styled.div`
  border-radius: 16px;
  border: 1px solid ${({ theme }) => theme.colors.overlay};
  background: ${({ theme }) => theme.colors.surfaceRaised};
  overflow: hidden;
`;

const RecipeHeader = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  border-bottom: 1px solid ${({ theme }) => theme.colors.overlay};
`;

const RecipeHeaderActions = styled.div`
  display: flex;
  gap: 6px;

  button {
    border: none;
    border-radius: 999px;
    padding: 6px 10px;
    cursor: pointer;
    font-weight: 600;
    background: ${({ theme }) => theme.colors.dangerSubtle};
    color: ${({ theme }) => theme.colors.textPrimary};
    ${focusRing}
  }
`;

const IngredientRow = styled.div`
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 8px;
  padding: 8px 12px 8px 20px;

  &:not(:last-child) {
    border-bottom: 1px solid ${({ theme }) => theme.colors.overlay};
  }
`;

const IngredientName = styled.span`
  font-size: 0.9rem;
  opacity: 0.85;
`;

const Field = styled.div`
  display: flex;
  flex-direction: column;
  gap: 4px;

  input {
    width: 100%;
    padding: 6px 8px;
    border-radius: 10px;
    border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
    background: ${({ theme }) => theme.colors.surfaceInset};
    color: ${({ theme }) => theme.colors.textPrimary};
  }
`;

const InlineFields = styled.div`
  display: flex;
  gap: 6px;
  align-items: center;

  input {
    padding: 4px 6px;
    border-radius: 8px;
    border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
    background: ${({ theme }) => theme.colors.surfaceInset};
    color: ${({ theme }) => theme.colors.textPrimary};
    font-size: 0.85rem;
  }

  input[type='number'] {
    width: 64px;
  }

  input[type='text'] {
    width: 56px;
  }
`;

const InlineActions = styled.div`
  display: flex;
  gap: 4px;

  button {
    border: none;
    border-radius: 999px;
    padding: 4px 8px;
    cursor: pointer;
    font-size: 0.8rem;
    font-weight: 600;
    ${focusRing}
  }

  button:first-of-type {
    background: ${({ theme }) => theme.palette?.pond?.['200'] ?? '#7ED7C4'};
    color: ${({ theme }) => theme.colors.backgroundPage};
  }

  button:last-of-type {
    background: ${({ theme }) => theme.colors.dangerSubtle};
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
    ${focusRing}
  }

  button:first-of-type {
    background: ${({ theme }) => theme.palette?.pond?.['200'] ?? '#7ED7C4'};
    color: ${({ theme }) => theme.colors.backgroundPage};
  }

  button:last-of-type {
    background: ${({ theme }) => theme.colors.dangerSubtle};
    color: ${({ theme }) => theme.colors.textPrimary};
  }
`;

const Collapse = styled.div<{ $expanded: boolean }>`
  display: grid;
  grid-template-rows: ${({ $expanded }) => ($expanded ? '1fr' : '0fr')};
  transition: grid-template-rows 0.25s ease;

  @media (prefers-reduced-motion: reduce) {
    transition-duration: 0.01ms;
  }

  > * {
    overflow: hidden;
  }
`;

type Draft = Record<
  number,
  {
    quantity: number;
    unit: string;
  }
>;

type MenuEntry = {
  id: number;
  ingredient_id: number;
  ingredient_name?: string | null;
  recipe_id?: number | null;
  recipe_name?: string | null;
  quantity: number;
  unit: string;
  source: string;
};

type MenuGroup = {
  key: string;
  recipe_id: number | null;
  recipe_name: string | null;
  entries: MenuEntry[];
};

function groupEntries(entries: MenuEntry[]): MenuGroup[] {
  const groups: MenuGroup[] = [];
  const recipeMap = new Map<number, MenuGroup>();

  for (const entry of entries) {
    if (entry.recipe_id != null) {
      let group = recipeMap.get(entry.recipe_id);
      if (!group) {
        group = {
          key: `recipe-${entry.recipe_id}`,
          recipe_id: entry.recipe_id,
          recipe_name: entry.recipe_name ?? null,
          entries: [],
        };
        recipeMap.set(entry.recipe_id, group);
        groups.push(group);
      }
      group.entries.push(entry);
    } else {
      groups.push({
        key: `standalone-${entry.id}`,
        recipe_id: null,
        recipe_name: null,
        entries: [entry],
      });
    }
  }
  return groups;
}

export function MenuPanel() {
  const { menuQuery, updateEntry, deleteEntry } = useNutritionMenu();
  const { foodsQuery } = useNutritionFoods();
  const [drafts, setDrafts] = useState<Draft>({});
  const [expanded, setExpanded] = useState(false);
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | string | null>(null);

  const entries = menuQuery.data?.entries ?? [];
  const foods = foodsQuery.data ?? [];
  const foodMap = useMemo(() => new Map(foods.map((food) => [food.id, food.name])), [foods]);
  const groups = useMemo(() => groupEntries(entries), [entries]);

  const foodCount = groups.length;

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

  const handleDeleteClick = (id: number) => {
    if (confirmDeleteId === id) {
      deleteEntry(id);
      setDrafts((prev) => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
      setConfirmDeleteId(null);
    } else {
      setConfirmDeleteId(id);
    }
  };

  const handleDeleteGroup = (group: MenuGroup) => {
    const groupKey = `group-${group.key}`;
    if (confirmDeleteId === groupKey) {
      for (const entry of group.entries) {
        deleteEntry(entry.id);
        setDrafts((prev) => {
          const next = { ...prev };
          delete next[entry.id];
          return next;
        });
      }
      setConfirmDeleteId(null);
    } else {
      setConfirmDeleteId(groupKey);
    }
  };

  const renderIngredientRow = (entry: MenuEntry) => (
    <IngredientRow key={entry.id}>
      <IngredientName>
        {entry.ingredient_name ?? foodMap.get(entry.ingredient_id)}
      </IngredientName>
      <InlineFields>
        <input
          type="number"
          step="0.1"
          aria-label="Quantity"
          value={drafts[entry.id]?.quantity ?? Number(entry.quantity ?? 0)}
          onChange={(e) => handleChange(entry.id, 'quantity', e.target.value)}
        />
        <input
          type="text"
          aria-label="Unit"
          value={drafts[entry.id]?.unit ?? entry.unit}
          onChange={(e) => handleChange(entry.id, 'unit', e.target.value)}
        />
        <InlineActions>
          <button onClick={() => handleSave(entry.id)}>Save</button>
          <button onClick={() => handleDeleteClick(entry.id)}>
            {confirmDeleteId === entry.id ? 'Confirm?' : 'X'}
          </button>
        </InlineActions>
      </InlineFields>
    </IngredientRow>
  );

  const renderStandaloneEntry = (entry: MenuEntry) => (
    <EntryCard key={entry.id}>
      <div>
        <strong>{entry.ingredient_name ?? foodMap.get(entry.ingredient_id)}</strong>
        <div style={{ fontSize: '0.85rem', opacity: 0.7 }}>
          Source: {entry.source}
        </div>
      </div>
      <Actions>
        <button onClick={() => handleSave(entry.id)}>Save</button>
        <button onClick={() => handleDeleteClick(entry.id)}>
          {confirmDeleteId === entry.id ? 'Confirm?' : 'Remove'}
        </button>
      </Actions>
      <Field>
        <label>Quantity</label>
        <input
          type="number"
          step="0.1"
          aria-label="Quantity"
          value={drafts[entry.id]?.quantity ?? Number(entry.quantity ?? 0)}
          onChange={(e) => handleChange(entry.id, 'quantity', e.target.value)}
        />
      </Field>
      <Field>
        <label>Unit</label>
        <input
          aria-label="Unit"
          value={drafts[entry.id]?.unit ?? entry.unit}
          onChange={(e) => handleChange(entry.id, 'unit', e.target.value)}
        />
      </Field>
    </EntryCard>
  );

  const renderRecipeGroup = (group: MenuGroup) => (
    <RecipeGroup key={group.key}>
      <RecipeHeader>
        <strong>{group.recipe_name}</strong>
        <RecipeHeaderActions>
          <button onClick={() => handleDeleteGroup(group)}>
            {confirmDeleteId === `group-${group.key}` ? 'Confirm?' : 'Remove All'}
          </button>
        </RecipeHeaderActions>
      </RecipeHeader>
      {group.entries.map(renderIngredientRow)}
    </RecipeGroup>
  );

  return (
    <Card>
      <PanelHeader>
        <h3 data-halo="heading">Menu</h3>
        <HeaderActions>
          {!menuQuery.isLoading && foodCount > 0 && (
            <span>{foodCount} {foodCount === 1 ? 'item' : 'items'}</span>
          )}
          <ToggleButton type="button" aria-expanded={expanded} onClick={() => setExpanded((prev) => !prev)}>
            {expanded ? 'Hide' : 'Show'}
          </ToggleButton>
        </HeaderActions>
      </PanelHeader>
      {menuQuery.isLoading && <p style={{ opacity: 0.7 }}>Loading today&apos;s menu…</p>}
      <Collapse $expanded={expanded}>
        <div>
          {entries.length === 0 ? (
            <p style={{ opacity: 0.7 }}>No meals logged today.</p>
          ) : (
            <Entries>
              {groups.map((group) =>
                group.recipe_id != null
                  ? renderRecipeGroup(group)
                  : renderStandaloneEntry(group.entries[0])
              )}
            </Entries>
          )}
        </div>
      </Collapse>
      {!expanded && entries.length > 0 && (
        <p style={{ opacity: 0.65, fontSize: '0.85rem' }}>
          Expand to adjust the meals Monet logged today.
        </p>
      )}
    </Card>
  );
}
