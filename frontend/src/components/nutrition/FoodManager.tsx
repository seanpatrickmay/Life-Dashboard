import { useEffect, useMemo, useState } from 'react';
import styled from 'styled-components';
import { Card } from '../common/Card';
import { useNutritionFoods } from '../../hooks/useNutritionFoods';
import { useNutritionNutrients } from '../../hooks/useNutritionNutrients';
import { useNutritionGoals } from '../../hooks/useNutritionGoals';
import {
  GROUP_LABELS,
  GROUP_ORDER,
  GroupBody,
  GroupEmpty,
  GroupHeader,
  GroupSection,
  type GroupKey,
  Chevron
} from './NutrientGroupUI';

const Layout = styled.div`
  display: grid;
  gap: 16px;
  grid-template-columns: minmax(0, 1.8fr) minmax(0, 1fr);

  @media (max-width: 1100px) {
    grid-template-columns: 1fr;
  }
`;

const TableCard = styled(Card)`
  overflow: hidden;
`;

const Table = styled.table`
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;

  th,
  td {
    padding: 8px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    text-align: left;
  }

  tbody tr {
    cursor: pointer;
    transition: background 0.2s ease;

    &:hover {
      background: rgba(255, 255, 255, 0.03);
    }
  }
`;

const StatusBadge = styled.span`
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: 2px solid ${({ theme }) => theme.colors.accentPrimary};
  font-size: 0.65rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
`;

const TableRow = styled.tr<{ $selected?: boolean }>`
  background: ${({ $selected }) => ($selected ? 'rgba(255, 255, 255, 0.06)' : 'transparent')};
`;

const Controls = styled.div`
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 12px;
  font-size: 0.9rem;
`;

const Select = styled.select`
  padding: 6px 8px;
  border-radius: 10px;
  background: rgba(0, 0, 0, 0.15);
  color: ${({ theme }) => theme.colors.textPrimary};
  border: 1px solid rgba(255, 255, 255, 0.08);
`;

const FieldGroup = styled.div`
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 12px;

  label {
    font-size: 0.85rem;
    opacity: 0.75;
  }

  input,
  select {
    width: 100%;
    padding: 6px 8px;
    border-radius: 10px;
    border: 1px solid rgba(255, 255, 255, 0.12);
    background: rgba(0, 0, 0, 0.15);
    color: ${({ theme }) => theme.colors.textPrimary};
  }
`;

const NutrientGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 8px;
`;

const NutrientField = styled.div`
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 0.8rem;

  input {
    width: 100%;
    padding: 4px 6px;
    border-radius: 8px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    background: rgba(0, 0, 0, 0.15);
    color: ${({ theme }) => theme.colors.textPrimary};
  }
`;

const Actions = styled.div`
  display: flex;
  gap: 8px;
  margin-top: 12px;
  flex-wrap: wrap;
`;

const Button = styled.button<{ $variant?: 'primary' | 'ghost' }>`
  padding: 8px 12px;
  border-radius: 999px;
  border: ${({ $variant }) => ($variant === 'ghost' ? '1px solid rgba(255,255,255,0.2)' : 'none')};
  background: ${({ $variant, theme }) =>
    $variant === 'ghost' ? 'transparent' : theme.colors.accentPrimary};
  color: ${({ $variant, theme }) =>
    $variant === 'ghost' ? theme.colors.textPrimary : '#0b0f19'};
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.2s ease;

  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
`;

type FormState = {
  name: string;
  default_unit: string;
  status: string;
  nutrients: Record<string, number | null>;
};

export function FoodManager() {
  const { foodsQuery, updateFood } = useNutritionFoods();
  const nutrientDefsQuery = useNutritionNutrients();
  const { goalsQuery } = useNutritionGoals();
  const [filter, setFilter] = useState('all');
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [formState, setFormState] = useState<FormState | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedGroups, setExpandedGroups] = useState<Record<GroupKey, boolean>>({
    macro: true,
    vitamin: false,
    mineral: false
  });

  const foods = foodsQuery.data ?? [];

  const filtered = useMemo(() => {
    if (filter === 'unconfirmed') return foods.filter((food) => food.status === 'unconfirmed');
    if (filter === 'confirmed') return foods.filter((food) => food.status === 'confirmed');
    return foods;
  }, [foods, filter]);

  useEffect(() => {
    if (!filtered.length) {
      setSelectedId(null);
      return;
    }
    if (!selectedId || !filtered.some((food) => food.id === selectedId)) {
      setSelectedId(filtered[0].id);
    }
  }, [filtered, selectedId]);

  const selectedFood = filtered.find((food) => food.id === selectedId) ?? null;

  useEffect(() => {
    if (!selectedFood) {
      setFormState(null);
      return;
    }
    setFormState({
      name: selectedFood.name,
      default_unit: selectedFood.default_unit,
      status: selectedFood.status,
      nutrients: { ...selectedFood.nutrients }
    });
    setError(null);
  }, [selectedFood]);

  const handleFieldChange = (field: keyof Omit<FormState, 'nutrients'>, value: string) => {
    setFormState((prev) => (prev ? { ...prev, [field]: value } : prev));
  };

  const handleNutrientChange = (slug: string, value: string) => {
    setFormState((prev) => {
      if (!prev) return prev;
      const parsed = value === '' ? null : Number(value);
      return {
        ...prev,
        nutrients: {
          ...prev.nutrients,
          [slug]: Number.isNaN(parsed) ? prev.nutrients[slug] : parsed
        }
      };
    });
  };

  const handleSave = async (nextStatus?: string) => {
    if (!selectedFood || !formState) return;
    setSaving(true);
    setError(null);
    try {
      const payload = {
        name: formState.name,
        default_unit: formState.default_unit,
        status: nextStatus ?? formState.status,
        nutrients: formState.nutrients
      };
      await updateFood({ id: selectedFood.id, payload });
      if (nextStatus && nextStatus !== formState.status) {
        setFormState((prev) => (prev ? { ...prev, status: nextStatus } : prev));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save changes');
    } finally {
      setSaving(false);
    }
  };

  const nutrientDefinitions = nutrientDefsQuery.data ?? goalsQuery.data ?? [];
  const nutrientsLoading =
    nutrientDefinitions.length === 0 &&
    (nutrientDefsQuery.isLoading || goalsQuery.isLoading);

  const groupedDefinitions = useMemo(() => {
    const buckets: Record<GroupKey, typeof nutrientDefinitions> = {
      macro: [],
      vitamin: [],
      mineral: []
    };
    nutrientDefinitions.forEach((definition) => {
      const key = (definition.group as GroupKey) ?? 'macro';
      buckets[key].push(definition);
    });
    return GROUP_ORDER.map((key) => ({
      key,
      label: GROUP_LABELS[key],
      items: buckets[key]
    }));
  }, [nutrientDefinitions]);

  const toggleGroup = (group: GroupKey) => {
    setExpandedGroups((prev) => ({ ...prev, [group]: !prev[group] }));
  };

  return (
    <Layout>
      <TableCard>
        <h3 data-halo="heading">Pallete</h3>
        <Controls>
          <label>
            Filter:
            <Select value={filter} onChange={(e) => setFilter(e.target.value)}>
              <option value="all">All</option>
              <option value="confirmed">Confirmed</option>
              <option value="unconfirmed">Unconfirmed</option>
            </Select>
          </label>
        </Controls>
        <Table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Unit</th>
              <th style={{ width: 32 }} />
            </tr>
         </thead>
          <tbody>
            {filtered.map((food) => (
              <TableRow
                key={food.id}
                $selected={food.id === selectedId}
                onClick={() => setSelectedId(food.id)}
              >
                <td>{food.name}</td>
                <td>{food.default_unit}</td>
                <td>
                  {!food.status || food.status === 'unconfirmed' ? (
                    <StatusBadge title="Unconfirmed">!</StatusBadge>
                  ) : null}
                </td>
              </TableRow>
            ))}
            {!filtered.length && (
              <tr>
                <td colSpan={3} style={{ opacity: 0.7, padding: '12px 8px' }}>
                  No foods recorded yet. Log meals with Claude to populate your pallete.
                </td>
              </tr>
            )}
          </tbody>
        </Table>
        {foodsQuery.isLoading && <p>Loading palette…</p>}
      </TableCard>

      <Card>
        <h3 data-halo="heading">Pallete Details</h3>
        {!selectedFood || !formState ? (
          <p style={{ opacity: 0.75 }}>Select a food to review or edit its details.</p>
        ) : (
          <>
            <FieldGroup>
              <label htmlFor="food-name">Name</label>
              <input
                id="food-name"
                value={formState.name}
                onChange={(e) => handleFieldChange('name', e.target.value)}
              />
            </FieldGroup>
            <FieldGroup>
              <label htmlFor="food-unit">Default unit</label>
              <input
                id="food-unit"
                value={formState.default_unit}
                onChange={(e) => handleFieldChange('default_unit', e.target.value)}
              />
            </FieldGroup>
            <FieldGroup>
              <label htmlFor="food-status">Status</label>
              <select
                id="food-status"
                value={formState.status}
                onChange={(e) => handleFieldChange('status', e.target.value)}
              >
                <option value="unconfirmed">Unconfirmed</option>
                <option value="confirmed">Confirmed</option>
              </select>
            </FieldGroup>
            <FieldGroup>
              <label>Pallete nutrients</label>
              {nutrientsLoading && <p style={{ opacity: 0.7 }}>Loading nutrients…</p>}
              <SectionStack>
                {groupedDefinitions.map(({ key, label, items }) => (
                  <GroupSection key={key}>
                    <GroupHeader type="button" onClick={() => toggleGroup(key)}>
                      {label}
                      <Chevron $expanded={expandedGroups[key]}>›</Chevron>
                    </GroupHeader>
                    <GroupBody $expanded={expandedGroups[key]}>
                      {items.length === 0 ? (
                        <GroupEmpty>No {label.toLowerCase()} configured.</GroupEmpty>
                      ) : (
                        <NutrientGrid>
                          {items.map((nutrient) => (
                            <NutrientField key={nutrient.slug}>
                              <span>
                                {nutrient.display_name} ({nutrient.unit})
                              </span>
                              <input
                                inputMode="decimal"
                                value={
                                  formState.nutrients?.[nutrient.slug] ??
                                  ''
                                }
                                onChange={(e) =>
                                  handleNutrientChange(nutrient.slug, e.target.value)
                                }
                              />
                            </NutrientField>
                          ))}
                        </NutrientGrid>
                      )}
                    </GroupBody>
                  </GroupSection>
                ))}
              </SectionStack>
            </FieldGroup>
            {error && <p style={{ color: '#ff8a8a' }}>{error}</p>}
            <Actions>
              <Button disabled={saving} onClick={() => handleSave()}>
                {saving ? 'Saving…' : 'Save Pallete Entry'}
              </Button>
              {formState.status !== 'confirmed' && (
                <Button
                  $variant="ghost"
                  disabled={saving}
                  onClick={() => handleSave('confirmed')}
                >
                  {saving ? 'Confirming…' : 'Mark as Confirmed'}
                </Button>
              )}
            </Actions>
          </>
        )}
      </Card>
    </Layout>
  );
}
const SectionStack = styled.div`
  display: flex;
  flex-direction: column;
  gap: 10px;
`;
