import { useEffect, useMemo, useState } from 'react';
import styled from 'styled-components';
import { Card } from '../common/Card';
import { useNutritionFoods } from '../../hooks/useNutritionFoods';
import { useNutritionNutrients } from '../../hooks/useNutritionNutrients';
import { useNutritionGoals } from '../../hooks/useNutritionGoals';
import { useNutritionRecipes } from '../../hooks/useNutritionRecipes';
import { type NutritionRecipe, type RecipeComponent } from '../../services/api';
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

const Tabs = styled.div`
  display: inline-flex;
  gap: 8px;
  margin-bottom: 12px;
`;

const TabButton = styled.button<{ $active?: boolean }>`
  border: 1px solid rgba(255, 255, 255, 0.2);
  background: ${({ $active, theme }) => ($active ? theme.colors.accentPrimary : 'transparent')};
  color: ${({ $active, theme }) => ($active ? '#0b0f19' : theme.colors.textPrimary)};
  padding: 8px 12px;
  border-radius: 999px;
  cursor: pointer;
  font-weight: 600;
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

type RecipeLine = {
  type: 'ingredient' | 'recipe';
  ingredient_id?: number | null;
  child_recipe_id?: number | null;
  quantity: number;
  unit: string;
};

type RecipeFormState = {
  name: string;
  default_unit: string;
  servings: number;
  status: string;
  components: RecipeLine[];
};

export function FoodManager() {
  const [tab, setTab] = useState<'ingredients' | 'recipes'>('ingredients');
  const [filter, setFilter] = useState('all');
  const [ingredientSearch, setIngredientSearch] = useState('');
  const [recipeSearch, setRecipeSearch] = useState('');
  const [ingredientPickerSearch, setIngredientPickerSearch] = useState('');
  const [recipePickerSearch, setRecipePickerSearch] = useState('');
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [formState, setFormState] = useState<FormState | null>(null);
  const [selectedRecipeId, setSelectedRecipeId] = useState<number | null>(null);
  const [recipeForm, setRecipeForm] = useState<RecipeFormState | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recentIngredientIds, setRecentIngredientIds] = useState<number[]>([]);
  const [recentRecipeIds, setRecentRecipeIds] = useState<number[]>([]);
  const { foodsQuery, updateFood } = useNutritionFoods();
  const { recipesQuery, recipeQuery, createRecipe, updateRecipe } = useNutritionRecipes(selectedRecipeId ?? undefined);
  const nutrientDefsQuery = useNutritionNutrients();
  const { goalsQuery } = useNutritionGoals();
  const [expandedGroups, setExpandedGroups] = useState<Record<GroupKey, boolean>>({
    macro: true,
    vitamin: false,
    mineral: false
  });

  const foods = foodsQuery.data ?? [];
  const recipes = recipesQuery.data ?? [];

  const filtered = useMemo(() => {
    const term = ingredientSearch.trim().toLowerCase();
    const base =
      filter === 'unconfirmed'
        ? foods.filter((food) => food.status === 'unconfirmed')
        : filter === 'confirmed'
          ? foods.filter((food) => food.status === 'confirmed')
          : foods;
    if (!term) return base;
    return base.filter((food) => food.name.toLowerCase().includes(term));
  }, [foods, filter, ingredientSearch]);

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

  useEffect(() => {
    if (!recipes.length) {
      setSelectedRecipeId(null);
      setRecipeForm(null);
      return;
    }
    if (!selectedRecipeId || !recipes.some((recipe) => recipe.id === selectedRecipeId)) {
      setSelectedRecipeId(recipes[0].id);
    }
  }, [recipes, selectedRecipeId, recipeQuery.data]);

  useEffect(() => {
    const recipe = recipeQuery.data ?? recipes.find((item) => item.id === selectedRecipeId);
    if (!recipe) {
      setRecipeForm(null);
      return;
    }
    const sortedComponents = [...(recipe.components ?? [])].sort((a, b) => (a.position ?? 0) - (b.position ?? 0));
    setRecipeForm({
      name: recipe.name,
      default_unit: recipe.default_unit,
      servings: recipe.servings,
      status: recipe.status,
      components: sortedComponents.map((component) => ({
        type: component.child_recipe_id ? 'recipe' : 'ingredient',
        ingredient_id: component.ingredient_id ?? null,
        child_recipe_id: component.child_recipe_id ?? null,
        quantity: component.quantity,
        unit: component.unit
      }))
    });
  }, [recipes, selectedRecipeId, recipeQuery.data]);

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

  const handleRecipeFieldChange = (field: keyof Omit<RecipeFormState, 'components'>, value: string) => {
    setRecipeForm((prev) => (prev ? { ...prev, [field]: field === 'servings' ? Number(value) : value } : prev));
  };

  const handleRecipeComponentChange = (index: number, patch: Partial<RecipeLine>) => {
    setRecipeForm((prev) => {
      if (!prev) return prev;
      const next = [...prev.components];
      next[index] = { ...next[index], ...patch } as RecipeLine;
      if (patch.type === 'ingredient') {
        next[index].child_recipe_id = null;
      }
      if (patch.type === 'recipe') {
        next[index].ingredient_id = null;
      }
      return { ...prev, components: next };
    });
    if (patch.ingredient_id) {
      setRecentIngredientIds((prev) => [patch.ingredient_id as number, ...prev.filter((id) => id !== patch.ingredient_id)].slice(0, 12));
    }
    if (patch.child_recipe_id) {
      setRecentRecipeIds((prev) => [patch.child_recipe_id as number, ...prev.filter((id) => id !== patch.child_recipe_id)].slice(0, 12));
    }
  };

  const addRecipeComponent = () => {
    setRecipeForm((prev) =>
      prev
        ? {
            ...prev,
            components: [
              ...prev.components,
              { type: 'ingredient', ingredient_id: null, child_recipe_id: null, quantity: 1, unit: '100g' }
            ]
          }
        : prev
    );
  };

  const removeRecipeComponent = (index: number) => {
    setRecipeForm((prev) => {
      if (!prev) return prev;
      const next = prev.components.filter((_, idx) => idx !== index);
      return { ...prev, components: next };
    });
  };

  const handleSaveRecipe = async (nextStatus?: string) => {
    if (!selectedRecipeId || !recipeForm) return;
    setSaving(true);
    setError(null);
    try {
      const payload = {
        name: recipeForm.name,
        default_unit: recipeForm.default_unit,
        servings: recipeForm.servings,
        status: nextStatus ?? recipeForm.status,
        components: recipeForm.components.map((comp, position) => ({
          ingredient_id: comp.type === 'ingredient' ? comp.ingredient_id ?? undefined : undefined,
          child_recipe_id: comp.type === 'recipe' ? comp.child_recipe_id ?? undefined : undefined,
          quantity: comp.quantity,
          unit: comp.unit,
          position
        }))
      };
      await updateRecipe({ id: selectedRecipeId, payload });
      if (nextStatus && nextStatus !== recipeForm.status) {
        setRecipeForm((prev) => (prev ? { ...prev, status: nextStatus } : prev));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save recipe');
    } finally {
      setSaving(false);
    }
  };

  const handleCreateRecipe = async () => {
    setSaving(true);
    setError(null);
    try {
      const created = await createRecipe({
        name: 'New recipe',
        default_unit: 'serving',
        servings: 1,
        status: 'unconfirmed',
        components: []
      });
      setSelectedRecipeId(created.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create recipe');
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

  const ingredientPane = (
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
          <label>
            Search:
            <input
              style={{ padding: '6px 8px', borderRadius: 10, border: '1px solid rgba(255,255,255,0.08)', background: 'rgba(0,0,0,0.15)', color: '#fff' }}
              value={ingredientSearch}
              onChange={(e) => setIngredientSearch(e.target.value)}
              placeholder="Find ingredient"
            />
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
                  No ingredients recorded yet. Log meals with Claude to populate your pallete.
                </td>
              </tr>
            )}
          </tbody>
        </Table>
        {foodsQuery.isLoading && <p>Loading palette…</p>}
      </TableCard>

      <Card>
        <h3 data-halo="heading">Ingredient Details</h3>
        {!selectedFood || !formState ? (
          <p style={{ opacity: 0.75 }}>Select an ingredient to review or edit its details.</p>
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
              <label>Ingredient nutrients (per default unit)</label>
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

  const selectedRecipeDetail = recipeQuery.data ?? recipes.find((item) => item.id === selectedRecipeId);
  const orderedRecipeOptions = useMemo(() => {
    const term = recipePickerSearch.trim().toLowerCase();
    const base = recipes.filter((recipe) => recipe.id !== selectedRecipeId);
    const filteredRecipes = term ? base.filter((recipe) => recipe.name.toLowerCase().includes(term)) : base;
    return [...filteredRecipes].sort((a, b) => {
      const aRecent = recentRecipeIds.indexOf(a.id);
      const bRecent = recentRecipeIds.indexOf(b.id);
      if (aRecent !== -1 && bRecent !== -1) return aRecent - bRecent;
      if (aRecent !== -1) return -1;
      if (bRecent !== -1) return 1;
      return a.name.localeCompare(b.name);
    });
  }, [recipes, recentRecipeIds, recipePickerSearch, selectedRecipeId]);

  const orderedIngredientOptions = useMemo(() => {
    const term = ingredientPickerSearch.trim().toLowerCase();
    const filteredIngredients = term ? foods.filter((food) => food.name.toLowerCase().includes(term)) : foods;
    return [...filteredIngredients].sort((a, b) => {
      const aRecent = recentIngredientIds.indexOf(a.id);
      const bRecent = recentIngredientIds.indexOf(b.id);
      if (aRecent !== -1 && bRecent !== -1) return aRecent - bRecent;
      if (aRecent !== -1) return -1;
      if (bRecent !== -1) return 1;
      return a.name.localeCompare(b.name);
    });
  }, [foods, recentIngredientIds, ingredientPickerSearch]);

  const recipeListFiltered = useMemo(() => {
    const term = recipeSearch.trim().toLowerCase();
    if (!term) return recipes;
    return recipes.filter((recipe) => recipe.name.toLowerCase().includes(term));
  }, [recipes, recipeSearch]);

  const recipePane = (
    <Layout>
      <TableCard>
        <h3 data-halo="heading">Recipes</h3>
        <Actions>
          <Button type="button" onClick={handleCreateRecipe} disabled={saving}>
            {saving ? 'Creating…' : 'New Recipe'}
          </Button>
        </Actions>
        <Controls>
          <label>
            Search:
            <input
              style={{ padding: '6px 8px', borderRadius: 10, border: '1px solid rgba(255,255,255,0.08)', background: 'rgba(0,0,0,0.15)', color: '#fff' }}
              value={recipeSearch}
              onChange={(e) => setRecipeSearch(e.target.value)}
              placeholder="Find recipe"
            />
          </label>
        </Controls>
        <Table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Servings</th>
              <th style={{ width: 32 }} />
            </tr>
          </thead>
          <tbody>
            {recipeListFiltered.map((recipe) => (
              <TableRow
                key={recipe.id}
                $selected={recipe.id === selectedRecipeId}
                onClick={() => setSelectedRecipeId(recipe.id)}
              >
                <td>{recipe.name}</td>
                <td>{recipe.servings}</td>
                <td>{recipe.status === 'unconfirmed' ? <StatusBadge title="Unconfirmed">!</StatusBadge> : null}</td>
              </TableRow>
            ))}
            {!recipes.length && (
              <tr>
                <td colSpan={3} style={{ opacity: 0.7, padding: '12px 8px' }}>
                  No recipes yet. Draft one from your common meals.
                </td>
              </tr>
            )}
          </tbody>
        </Table>
      </TableCard>

      <Card>
        <h3 data-halo="heading">Recipe Details</h3>
        {!recipeForm || !selectedRecipeId ? (
          <p style={{ opacity: 0.75 }}>Select a recipe to edit its components.</p>
        ) : (
          <>
            <FieldGroup>
              <label htmlFor="recipe-name">Name</label>
              <input
                id="recipe-name"
                value={recipeForm.name}
                onChange={(e) => handleRecipeFieldChange('name', e.target.value)}
              />
            </FieldGroup>
            <FieldGroup>
              <label htmlFor="recipe-unit">Default unit</label>
              <input
                id="recipe-unit"
                value={recipeForm.default_unit}
                onChange={(e) => handleRecipeFieldChange('default_unit', e.target.value)}
              />
            </FieldGroup>
            <FieldGroup>
              <label htmlFor="recipe-servings">Servings (batch)</label>
              <input
                id="recipe-servings"
                type="number"
                min={0.1}
                step={0.1}
                value={recipeForm.servings}
                onChange={(e) => handleRecipeFieldChange('servings', e.target.value)}
              />
            </FieldGroup>
            <FieldGroup>
              <label htmlFor="recipe-status">Status</label>
              <select
                id="recipe-status"
                value={recipeForm.status}
                onChange={(e) => handleRecipeFieldChange('status', e.target.value)}
              >
                <option value="unconfirmed">Unconfirmed</option>
                <option value="confirmed">Confirmed</option>
              </select>
            </FieldGroup>

            <FieldGroup>
              <label>Components</label>
              <Controls style={{ marginTop: 0 }}>
                <input
                  style={{ padding: '6px 8px', borderRadius: 10, border: '1px solid rgba(255,255,255,0.08)', background: 'rgba(0,0,0,0.15)', color: '#fff' }}
                  value={ingredientPickerSearch}
                  onChange={(e) => setIngredientPickerSearch(e.target.value)}
                  placeholder="Search ingredients"
                />
                <input
                  style={{ padding: '6px 8px', borderRadius: 10, border: '1px solid rgba(255,255,255,0.08)', background: 'rgba(0,0,0,0.15)', color: '#fff' }}
                  value={recipePickerSearch}
                  onChange={(e) => setRecipePickerSearch(e.target.value)}
                  placeholder="Search recipes"
                />
              </Controls>
              <SectionStack>
                {recipeForm.components.map((component, idx) => (
                  <Card key={idx} style={{ padding: 12 }}>
                    <Controls>
                      <label>
                        Type
                        <Select
                          value={component.type}
                          onChange={(e) => handleRecipeComponentChange(idx, { type: e.target.value as RecipeLine['type'] })}
                        >
                          <option value="ingredient">Ingredient</option>
                          <option value="recipe">Recipe</option>
                        </Select>
                      </label>
                      {component.type === 'ingredient' ? (
                        <Select
                          value={component.ingredient_id ?? ''}
                          onChange={(e) => {
                            const nextVal = e.target.value === '' ? null : Number(e.target.value);
                            handleRecipeComponentChange(idx, { ingredient_id: nextVal ?? undefined });
                          }}
                        >
                          <option value="">Select ingredient</option>
                          {orderedIngredientOptions.map((food) => (
                            <option key={food.id} value={food.id}>
                              {food.name}
                            </option>
                          ))}
                        </Select>
                      ) : (
                        <Select
                          value={component.child_recipe_id ?? ''}
                          onChange={(e) => {
                            const nextVal = e.target.value === '' ? null : Number(e.target.value);
                            handleRecipeComponentChange(idx, { child_recipe_id: nextVal ?? undefined });
                          }}
                        >
                          <option value="">Select recipe</option>
                          {orderedRecipeOptions.map((recipe) => (
                            <option key={recipe.id} value={recipe.id}>
                              {recipe.name}
                            </option>
                          ))}
                        </Select>
                      )}
                      <input
                        type="number"
                        step="0.1"
                        value={component.quantity}
                        onChange={(e) => handleRecipeComponentChange(idx, { quantity: Number(e.target.value) })}
                      />
                      <input
                        value={component.unit}
                        onChange={(e) => handleRecipeComponentChange(idx, { unit: e.target.value })}
                      />
                      <Button type="button" $variant="ghost" onClick={() => removeRecipeComponent(idx)}>
                        Remove
                      </Button>
                    </Controls>
                  </Card>
                ))}
                <Button type="button" onClick={addRecipeComponent}>
                  Add component
                </Button>
              </SectionStack>
            </FieldGroup>
            {selectedRecipeDetail?.derived_nutrients && (
              <FieldGroup>
                <label>Derived nutrients (per serving)</label>
                <p style={{ opacity: 0.75, fontSize: '0.9rem' }}>
                  Key macros: calories {selectedRecipeDetail.derived_nutrients.calories ?? '—'}, protein {selectedRecipeDetail.derived_nutrients.protein ?? '—'}
                </p>
              </FieldGroup>
            )}
            {error && <p style={{ color: '#ff8a8a' }}>{error}</p>}
            <Actions>
              <Button disabled={saving} onClick={() => handleSaveRecipe()}>
                {saving ? 'Saving…' : 'Save Recipe'}
              </Button>
              {recipeForm.status !== 'confirmed' && (
                <Button $variant="ghost" disabled={saving} onClick={() => handleSaveRecipe('confirmed')}>
                  {saving ? 'Confirming…' : 'Mark as Confirmed'}
                </Button>
              )}
            </Actions>
          </>
        )}
      </Card>
    </Layout>
  );

  return (
    <div>
      <Tabs>
        <TabButton type="button" $active={tab === 'ingredients'} onClick={() => setTab('ingredients')}>
          Ingredients
        </TabButton>
        <TabButton type="button" $active={tab === 'recipes'} onClick={() => setTab('recipes')}>
          Recipes
        </TabButton>
      </Tabs>
      {tab === 'ingredients' ? ingredientPane : recipePane}
    </div>
  );
}
const SectionStack = styled.div`
  display: flex;
  flex-direction: column;
  gap: 10px;
`;
