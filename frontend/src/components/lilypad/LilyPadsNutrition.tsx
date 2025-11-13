import { useMemo, useState, useCallback, useEffect, useRef } from 'react';
import type { KeyboardEvent as ReactKeyboardEvent } from 'react';
import styled from 'styled-components';
import { LilyPadCard } from './LilyPadCard';
import { useNutritionMenu } from '../../hooks/useNutritionMenu';
import { useNutritionDailySummary, useNutritionHistory } from '../../hooks/useNutritionIntake';
import { useNutritionFoods } from '../../hooks/useNutritionFoods';
import { useClaudeChat, type ChatEntry } from '../../hooks/useClaudeChat';
import { GROUP_LABELS, GROUP_ORDER, type GroupKey } from '../nutrition/NutrientGroupUI';
import type { NutritionHistory, NutritionSummary, NutritionFood, NutritionGoal } from '../../services/api';
import { useNutritionGoals } from '../../hooks/useNutritionGoals';

const Stage = styled.div`
  position: relative;
  min-height: calc(100vh + 240px);
  padding-bottom: 320px;
  color: #ffffff;
`;

const PadList = styled.ul`
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
`;

const PadListItem = styled.li`
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  font-size: 0.92rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.12);
  padding: 6px 0 10px;
  &:last-of-type {
    border-bottom: none;
  }
`;

const PaletteRowButton = styled.button<{ $status?: string }>`
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  background: transparent;
  border: none;
  color: inherit;
  padding: 0;
  cursor: pointer;
  text-align: left;
  font: inherit;
  gap: 12px;
  .meta {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 0.8rem;
    opacity: 0.8;
    color: #ffffff;
  }
  .warn {
    color: #ffdf7a;
    font-size: 0.85rem;
  }
`;

const PaletteScroll = styled.div`
  max-height: clamp(180px, 28vh, 320px);
  overflow-y: auto;
  padding-right: 6px;
  margin-top: 10px;
`;

const MenuScroll = styled(PaletteScroll)``;

const PaletteSearch = styled.div`
  display: flex;
  gap: 10px;
  align-items: center;
  input {
    flex: 1;
    border-radius: 18px;
    border: 1px solid rgba(255, 255, 255, 0.2);
    background: rgba(7, 23, 44, 0.4);
    padding: 8px 14px;
    color: #ffffff;
    caret-color: #ffffff;
    font-family: ${({ theme }) => theme.fonts.body};
  }
`;

const Pill = styled.span`
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 0.75rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  border: 1px solid rgba(255, 255, 255, 0.38);
`;

const CycleControls = styled.div`
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-right: 16px;
`;

const ControlButton = styled.button<{ $active?: boolean }>`
  border: 1px solid rgba(255, 255, 255, 0.3);
  background: ${({ $active }) => ($active ? 'rgba(255,255,255,0.18)' : 'rgba(0, 0, 0, 0.08)')};
  color: #ffffff;
  border-radius: 18px;
  padding: 8px 12px;
  display: inline-flex;
  align-items: center;
  justify-content: flex-start;
  font-size: 0.78rem;
  letter-spacing: 0.08em;
  cursor: pointer;
  text-transform: uppercase;
  width: 120px;
`;

const PercentDial = styled.div<{ $value: number }>`
  position: relative;
  width: 100%;
  aspect-ratio: 1/1;
  border-radius: 50%;
  background: rgba(7, 23, 44, 0.65);
  border: 1px solid rgba(255, 255, 255, 0.25);
  display: flex;
  align-items: center;
  justify-content: center;

  &::before {
    content: '';
    position: absolute;
    inset: 8px;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.05);
  }

  &::after {
    content: '';
    position: absolute;
    inset: 0;
    border-radius: 50%;
    background: conic-gradient(
      ${({ theme }) => theme.colors.accent} ${(p) => Math.min(100, Math.max(0, p.$value))}%,
      rgba(255, 255, 255, 0.08) ${(p) => Math.min(100, Math.max(0, p.$value))}%
    );
    opacity: 0.65;
  }

  pointer-events: none;
`;

const PercentBar = styled.div<{ $value: number }>`
  position: relative;
  width: min(160px, 36%);
  height: 6px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.12);
  overflow: hidden;
  &::after {
    content: '';
    position: absolute;
    inset: 0;
    background: ${({ theme }) => theme.colors.accent};
    width: ${(p) => Math.min(100, Math.max(0, p.$value))}%;
  }
`;

const Hint = styled.p`
  margin: 12px 0 0;
  font-size: 0.8rem;
  opacity: 0.78;
`;

const Spacer = styled.div`
  width: 100%;
`;

const DialGrid = styled.div<{ $columns: number }>`
  display: grid;
  grid-template-columns: repeat(${(p) => p.$columns}, minmax(0, 1fr));
  gap: 12px;
  width: 100%;
  padding: 4px 2px 0;
`;

const DialStage = styled.div`
  display: flex;
  width: 100%;
  min-height: clamp(260px, 36vh, 420px);
  align-items: stretch;
  gap: 18px;
`;

const DialStageContent = styled.div`
  flex: 1;
  display: flex;
  align-items: center;
`;

const DialButton = styled.button<{ $active?: boolean }>`
  border: none;
  background: transparent;
  padding: 0;
  width: 100%;
  cursor: pointer;
  opacity: ${(p) => (p.$active ? 1 : 0.92)};
  transform: ${(p) => (p.$active ? 'scale(1.03)' : 'scale(1)')};
  transition: transform 0.2s ease, opacity 0.2s ease;
`;

const DialLabel = styled.div`
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 4px;
  padding: 0 6px;

  strong {
    font-size: clamp(0.7rem, 1.6vw, 0.95rem);
    letter-spacing: 0.04em;
    text-transform: capitalize;
    color: ${({ theme }) => theme.colors.textPrimary};
  }

  .value {
    font-family: ${({ theme }) => theme.fonts.heading};
    font-size: clamp(0.75rem, 2vw, 1rem);
    color: ${({ theme }) => theme.colors.textPrimary};
    opacity: 0.95;
  }

  .amount {
    font-size: clamp(0.6rem, 1.4vw, 0.8rem);
    opacity: 0.78;
  }
`;

const FoodDetailWrapper = styled.div`
  width: 100%;
`;

const FoodDetailHeader = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 12px;
  strong {
    font-size: clamp(1rem, 2.4vw, 1.4rem);
  }
  span {
    opacity: 0.8;
    font-size: 0.9rem;
  }
`;

const BackButton = styled.button`
  border: 1px solid rgba(255, 255, 255, 0.3);
  background: rgba(0, 0, 0, 0.2);
  color: ${({ theme }) => theme.colors.textPrimary};
  border-radius: 20px;
  padding: 6px 14px;
  font-size: 0.8rem;
  letter-spacing: 0.08em;
  cursor: pointer;
`;

const FoodDetailContent = styled.div`
  display: flex;
  align-items: center;
  width: 100%;
  gap: 16px;
  min-height: clamp(260px, 36vh, 420px);
`;

const GoalEditor = styled.form`
  margin-top: 18px;
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
`;

const GoalInput = styled.input`
  padding: 8px 12px;
  border-radius: 14px;
  border: 1px solid rgba(255, 255, 255, 0.25);
  background: rgba(7, 23, 44, 0.5);
  color: #ffffff;
  font-family: ${({ theme }) => theme.fonts.heading};
  width: clamp(120px, 18vw, 200px);
`;

const GoalActions = styled.div`
  display: flex;
  gap: 10px;
  button {
    border: 1px solid rgba(255, 255, 255, 0.3);
    border-radius: 16px;
    background: rgba(255, 255, 255, 0.1);
    color: #ffffff;
    padding: 8px 16px;
    letter-spacing: 0.08em;
    cursor: pointer;
  }
`;

const GoalEditorHint = styled.p`
  width: 100%;
  margin: 4px 0 0;
  font-size: 0.8rem;
  opacity: 0.78;
`;

const GoalError = styled.p`
  width: 100%;
  margin: 0;
  font-size: 0.8rem;
  color: #ff9898;
`;

const formatPercent = (value?: number | null) => {
  if (value == null) return '—';
  return `${Math.round(value)}%`;
};

const formatAmount = (amount?: number | null, unit?: string | null) => {
  if (amount == null) return '—';
  return `${amount}${unit ? ` ${unit}` : ''}`;
};

const NAME_ABBREVIATIONS: Record<string, string> = {
  calorie: 'Cal',
  calories: 'Cal',
  kilocalorie: 'Cal',
  kilocalories: 'Cal',
  energy: 'Cal',
  proteins: 'Prot',
  protein: 'Prot',
  carbohydrate: 'Carb',
  carbohydrates: 'Carb',
  carb: 'Carb',
  carbs: 'Carb',
  dietaryfiber: 'Fiber',
  fiber: 'Fiber',
  sugar: 'Sugar',
  sugars: 'Sugar',
  addedsugar: 'AddSug',
  fat: 'Fat',
  totalfat: 'TotFat',
  saturatedfat: 'SatFat',
  monounsaturatedfat: 'MonoF',
  polyunsaturatedfat: 'PolyF',
  transfat: 'TransF',
  cholesterol: 'Chol',
  sodium: 'Sodium',
  potassium: 'Potas',
  chloride: 'Chlor',
  calcium: 'Calc',
  magnesium: 'Mag',
  manganese: 'Mnese',
  phosphorus: 'Phos',
  selenium: 'Selen',
  fluoride: 'Fluor',
  zinc: 'Zinc',
  copper: 'Copper',
  iron: 'Iron',
  iodine: 'Iodine',
  molybdenum: 'Moly',
  chromium: 'Chrom',
  choline: 'Cholin',
  folate: 'Folate',
  pantothenicacid: 'B5',
  riboflavin: 'B2',
  niacin: 'B3',
  thiamin: 'B1',
  pyridoxine: 'B6',
  biotin: 'B7',
  cobalamin: 'B12',
  b12: 'B12',
  b6: 'B6',
  b5: 'B5',
  b3: 'B3',
  b2: 'B2',
  b1: 'B1',
  b7: 'B7',
  folicacid: 'Folate'
};

const tidyDisplayName = (name: string, group: GroupKey) => {
  let base = name;
  if (group === 'vitamin') {
    const withoutPrefix = name.replace(/^vitamin\s+/i, '').trim();
    base = withoutPrefix.replace(/\s*\(.*?\)/g, '').trim() || withoutPrefix;
  }
  const normalized = base.toLowerCase().replace(/[^a-z0-9]/g, '');
  const lower = base.toLowerCase();
  const abbr = NAME_ABBREVIATIONS[normalized] ?? NAME_ABBREVIATIONS[lower];
  let final = abbr ?? base;
  if (final.length <= 6) return final;
  const consonantTrim = final.replace(/[aeiou\s]/gi, '');
  if (consonantTrim.length >= 3) {
    final = consonantTrim.slice(0, 6);
  } else {
    final = final.slice(0, 6);
  }
  return final;
};

const MACRO_KEYS = ['calorie', 'calories', 'protein', 'carbohydrate', 'carbohydrates', 'carb', 'carbs'];
const isMacroTarget = (slug?: string | null, label?: string | null) => {
  const source = `${slug ?? ''} ${label ?? ''}`.toLowerCase();
  return MACRO_KEYS.some((key) => source.includes(key));
};

const ENCOURAGEMENTS = [
  'Lovely pick',
  'Nice choice',
  'Tasteful snack',
  'Beautiful fuel',
  'Charming plate',
  'Peaceful bite'
];

const pickEncouragement = (seed: string) => {
  const index = Math.abs(seed.charCodeAt(0)) % ENCOURAGEMENTS.length;
  return ENCOURAGEMENTS[index];
};

const getAssistantMessage = (entry: ChatEntry): string => {
  const trimmed = entry.text?.trim();
  if (trimmed) return trimmed;
  if (entry.meta && entry.meta.length > 0) {
    const first = entry.meta[0];
    const seed = first.food_name ?? 'dish';
    const encouragement = pickEncouragement(seed);
    return `${encouragement} — ${seed}`;
  }
  return 'Appreciate the update!';
};

export function LilyPadsNutrition() {
  const { menuQuery } = useNutritionMenu();
  const { data: summaryData } = useNutritionDailySummary();
  const { data: historyData } = useNutritionHistory();
  const { foodsQuery } = useNutritionFoods();
  const { goalsQuery, updateGoal } = useNutritionGoals();
  const { history, sendMessage, isSending } = useClaudeChat();
  const chatHistoryRef = useRef<HTMLDivElement | null>(null);
  const [chatText, setChatText] = useState('');
  const [paletteFilter, setPaletteFilter] = useState('');
  const [groupIndex, setGroupIndex] = useState(0);
  const [historyGroupIndex, setHistoryGroupIndex] = useState(0);
  const [selectedFoodId, setSelectedFoodId] = useState<number | null>(null);
  const [foodDetailGroup, setFoodDetailGroup] = useState<GroupKey>('macro');
  const [selectedMenuEntryId, setSelectedMenuEntryId] = useState<number | null>(null);
  const [menuDetailGroup, setMenuDetailGroup] = useState<GroupKey>('macro');
  const [goalGroupIndex, setGoalGroupIndex] = useState(0);
  const [editingGoalSlug, setEditingGoalSlug] = useState<string | null>(null);
  const [editingGoalValue, setEditingGoalValue] = useState('');
  const [goalError, setGoalError] = useState<string | null>(null);
  const [savingGoal, setSavingGoal] = useState(false);

  const menuEntries = menuQuery.data?.entries ?? [];
  // Entire menu shown; no preview subset.

  type SummaryEntry = NutritionSummary['nutrients'][number];
  type HistoryEntry = NutritionHistory['nutrients'][number];
type FoodDialEntry = { slug: string; display: string; percent: number; amount: string };

const buildDialEntries = (
  food: NutritionFood,
  group: GroupKey,
  goals: NutritionGoal[],
  multiplier = 1
): FoodDialEntry[] => {
  const relevantGoals = goals.filter((goal) => (goal.group as GroupKey) === group);
  const filteredGoals =
    group === 'macro'
      ? relevantGoals.filter((goal) => isMacroTarget(goal.slug, goal.display_name))
      : relevantGoals;
  return filteredGoals
    .map((goal) => {
      const rawAmount = food.nutrients?.[goal.slug];
      if (rawAmount == null) return null;
      const amount = Number(rawAmount) * multiplier;
      if (!Number.isFinite(amount) || amount < 0) return null;
      const percent = goal.goal ? (amount / goal.goal) * 100 : 0;
      return {
        slug: goal.slug,
        display: tidyDisplayName(goal.display_name, goal.group as GroupKey),
        percent,
        amount: formatAmount(amount, goal.unit)
      };
    })
    .filter((entry): entry is FoodDialEntry => entry !== null);
};

  const summaryGroups = useMemo<Record<GroupKey, SummaryEntry[]>>(() => {
    const base: Record<GroupKey, SummaryEntry[]> = {
      macro: [],
      vitamin: [],
      mineral: []
    };
    (summaryData?.nutrients ?? []).forEach((item) => {
      const key = (item.group as GroupKey) ?? 'macro';
      base[key] = [...(base[key] ?? []), item];
    });
    return base;
  }, [summaryData]);

  const activeGroup = GROUP_ORDER[groupIndex];
  const activeGroupLabel = GROUP_LABELS[activeGroup];
  const rawItems = summaryGroups[activeGroup] ?? [];
  const macroFiltered = rawItems.filter((item) => isMacroTarget(item.slug, item.display_name));
  const activeItems =
    activeGroup === 'macro'
      ? macroFiltered
      : activeGroup === 'vitamin'
        ? rawItems
        : rawItems.slice(0, 9);

  const historyGroups = useMemo<
    Record<GroupKey, { label: string; avg: number; entries: HistoryEntry[] }>
  >(() => {
    const base: Record<GroupKey, { label: string; avg: number; entries: HistoryEntry[] }> = {
      macro: { label: GROUP_LABELS.macro, avg: 0, entries: [] },
      vitamin: { label: GROUP_LABELS.vitamin, avg: 0, entries: [] },
      mineral: { label: GROUP_LABELS.mineral, avg: 0, entries: [] }
    };
    (historyData?.nutrients ?? []).forEach((item) => {
      const key = (item.group as GroupKey) ?? 'macro';
      const bucket = base[key];
      bucket.entries = [...bucket.entries, item];
    });
    (Object.keys(base) as GroupKey[]).forEach((key) => {
      const bucket = base[key];
      if (!bucket.entries.length) {
        bucket.avg = 0;
      } else {
        const valid = bucket.entries.filter((entry) => entry.percent_of_goal != null);
        const avg =
          valid.reduce((sum, entry) => sum + (entry.percent_of_goal ?? 0), 0) /
          (valid.length || 1);
        bucket.avg = avg;
      }
    });
    return base;
  }, [historyData]);

  const foods = foodsQuery.data ?? [];
  const nutritionGoals = goalsQuery.data ?? [];
const filteredFoods = useMemo(() => {
  const query = paletteFilter.trim().toLowerCase();
  if (!query) return foods;
  return foods.filter((food) => food.name.toLowerCase().includes(query));
}, [foods, paletteFilter]);
  const selectedFood = useMemo(
    () => foods.find((food) => food.id === selectedFoodId) ?? null,
    [foods, selectedFoodId]
  );
  const selectedMenuEntry = useMemo(
    () => menuEntries.find((entry) => entry.id === selectedMenuEntryId) ?? null,
    [menuEntries, selectedMenuEntryId]
  );
  const selectedMenuFood = useMemo(() => {
    if (!selectedMenuEntry) return null;
    return foods.find((food) => food.id === selectedMenuEntry.food_id) ?? null;
  }, [foods, selectedMenuEntry]);

  useEffect(() => {
    if (selectedFoodId && !selectedFood) {
      setSelectedFoodId(null);
    }
  }, [selectedFoodId, selectedFood]);

  useEffect(() => {
    setFoodDetailGroup('macro');
  }, [selectedFoodId]);

  useEffect(() => {
    if (selectedMenuEntryId && !selectedMenuEntry) {
      setSelectedMenuEntryId(null);
    }
  }, [selectedMenuEntryId, selectedMenuEntry]);

  useEffect(() => {
    if (selectedMenuEntryId === null) {
      setMenuDetailGroup('macro');
    }
  }, [selectedMenuEntryId]);

  const goalGroups = useMemo(() => {
    const buckets: Record<GroupKey, NutritionGoalItem[]> = {
      macro: [],
      vitamin: [],
      mineral: []
    };
    nutritionGoals.forEach((goal) => {
      const group = (goal.group as GroupKey) ?? 'macro';
      if (group === 'macro' && !isMacroTarget(goal.slug, goal.display_name)) {
        return;
      }
      if (!buckets[group]) buckets[group] = [];
      buckets[group].push(goal);
    });
    return buckets;
  }, [nutritionGoals]);

  useEffect(() => {
    if (chatHistoryRef.current) {
      chatHistoryRef.current.scrollTo({
        top: chatHistoryRef.current.scrollHeight,
        behavior: 'smooth'
      });
    }
  }, [history]);

  const paletteDialItems = useMemo<FoodDialEntry[]>(() => {
    if (!selectedFood) return [];
    return buildDialEntries(selectedFood, foodDetailGroup, nutritionGoals, 1);
  }, [selectedFood, nutritionGoals, foodDetailGroup]);

  const menuDialItems = useMemo<FoodDialEntry[]>(() => {
    if (!selectedMenuEntry || !selectedMenuFood) return [];
    const qty = Number(selectedMenuEntry.quantity ?? 1);
    const multiplier = Number.isFinite(qty) && qty > 0 ? qty : 1;
    return buildDialEntries(selectedMenuFood, menuDetailGroup, nutritionGoals, multiplier);
  }, [selectedMenuEntry, selectedMenuFood, menuDetailGroup, nutritionGoals]);

  const activeGoalGroup = GROUP_ORDER[goalGroupIndex];
  const goalDialEntries = useMemo(() => {
    const items = goalGroups[activeGoalGroup] ?? [];
    return items.map((goal) => {
      const percent = goal.default_goal ? (goal.goal / goal.default_goal) * 100 : 100;
      return {
        slug: goal.slug,
        display: tidyDisplayName(goal.display_name, goal.group as GroupKey),
        percent,
        amount: formatAmount(goal.goal, goal.unit),
        raw: goal
      };
    });
  }, [goalGroups, activeGoalGroup]);

  const editingGoal = useMemo(
    () => nutritionGoals.find((goal) => goal.slug === editingGoalSlug) ?? null,
    [nutritionGoals, editingGoalSlug]
  );

  const cycleGroup = (direction: 1 | -1) => {
    setGroupIndex((prev) => {
      const next = (prev + direction + GROUP_ORDER.length) % GROUP_ORDER.length;
      return next;
    });
  };

  const sendChatMessage = useCallback(async () => {
    if (!chatText.trim()) return;
    const payload = chatText.trim();
    setChatText('');
    await sendMessage(payload);
  }, [chatText, sendMessage]);

  const onSubmitChat = useCallback(
    async (event: React.FormEvent) => {
      event.preventDefault();
      await sendChatMessage();
    },
    [sendChatMessage]
  );

  const onChatKeyDown = (event: ReactKeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      void sendChatMessage();
    }
  };

  const onSelectGoal = (goal: NutritionGoal) => {
    setEditingGoalSlug(goal.slug);
    setEditingGoalValue(goal.goal.toString());
    setGoalError(null);
  };

  const onCancelGoalEdit = () => {
    setEditingGoalSlug(null);
    setEditingGoalValue('');
    setGoalError(null);
  };

  const onSubmitGoal = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!editingGoalSlug) return;
    const nextValue = Number(editingGoalValue);
    if (!Number.isFinite(nextValue) || nextValue <= 0) {
      setGoalError('Goal must be a positive number.');
      return;
    }
    setSavingGoal(true);
    setGoalError(null);
    try {
      await updateGoal({ slug: editingGoalSlug, goal: nextValue });
      setEditingGoalSlug(null);
      setEditingGoalValue('');
    } catch (error) {
      setGoalError(error instanceof Error ? error.message : 'Unable to save goal.');
    } finally {
      setSavingGoal(false);
    }
  };

  const padSpacer = 1680;

  return (
    <Stage>
      <LilyPadCard
        id="nutrition-chat"
        side="left"
        topOffsetPx={40}
        scale={0.92}
        title="Log Foods with Claude"
        interactive
        edgeOffsetPx={-52}
        sideShiftPercent={22}
        contentWidthPct={0.8}
      >
        <ChatPadBody>
          <ChatHistory ref={chatHistoryRef}>
            {history.length === 0 ? (
              <ChatBubble $role="assistant">
                Tell me what you ate and I’ll log it in your menu.
              </ChatBubble>
            ) : (
              history.slice(-6).map((entry) => (
                <ChatBubble key={entry.id} $role={entry.role}>
                  {entry.role === 'assistant' ? getAssistantMessage(entry) : entry.text}
                  {entry.meta && entry.meta.length > 0 && (
                    <ChatMeta>
                      {entry.meta.map((meta, idx) => (
                        <li key={idx}>
                          {meta.quantity} {meta.unit} {meta.food_name} ({meta.status})
                        </li>
                      ))}
                    </ChatMeta>
                  )}
                </ChatBubble>
              ))
            )}
          </ChatHistory>
          <ChatForm onSubmit={onSubmitChat}>
            <ChatInput
              placeholder="e.g. Logged 1 bowl miso soup and 2 rice balls"
              value={chatText}
              onChange={(e) => setChatText(e.target.value)}
              onKeyDown={onChatKeyDown}
            />
            <ChatButton type="submit" disabled={isSending}>
              {isSending ? '...' : 'Send'}
            </ChatButton>
          </ChatForm>
        </ChatPadBody>
      </LilyPadCard>

      <LilyPadCard
        id="nutrition-menu"
        side="right"
        topOffsetPx={220}
        scale={0.94}
        title="Today’s Menu"
        interactive
        edgeOffsetPx={-56}
        sideShiftPercent={24}
        contentWidthPct={0.78}
      >
        {menuQuery.isLoading ? (
          <p style={{ opacity: 0.75 }}>Fetching meals logged today…</p>
        ) : menuEntries.length === 0 ? (
          <p style={{ opacity: 0.78 }}>No meals logged yet. Ask Claude to record breakfast, lunch, or dinner to populate today’s menu.</p>
        ) : selectedMenuEntry && selectedMenuFood ? (
          <FoodDetailWrapper>
            <FoodDetailHeader>
              <div>
                <strong>{selectedMenuEntry.food_name ?? selectedMenuFood.name ?? 'Meal'}</strong>
                <span>
                  ({selectedMenuEntry.quantity ?? 1} {selectedMenuEntry.unit ?? selectedMenuFood.default_unit ?? 'unit'})
                </span>
              </div>
              <BackButton type="button" onClick={() => setSelectedMenuEntryId(null)}>
                Back to menu
              </BackButton>
            </FoodDetailHeader>
            {goalsQuery.isError ? (
              <p style={{ opacity: 0.75 }}>Unable to load nutrient targets right now.</p>
            ) : goalsQuery.isLoading ? (
              <p style={{ opacity: 0.75 }}>Loading nutrient targets…</p>
            ) : menuDialItems.length === 0 ? (
              <p style={{ opacity: 0.75 }}>No nutrient data available for this meal.</p>
            ) : (
              <FoodDetailContent>
                <CycleControls>
                  {GROUP_ORDER.map((key) => (
                    <ControlButton
                      key={key}
                      type="button"
                      onClick={() => setMenuDetailGroup(key)}
                      $active={menuDetailGroup === key}
                    >
                      {GROUP_LABELS[key]}
                    </ControlButton>
                  ))}
                </CycleControls>
                <DialGrid $columns={menuDetailGroup === 'vitamin' ? 4 : 3}>
                  {menuDialItems.map((entry) => (
                    <PercentDial key={entry.slug} $value={entry.percent}>
                      <DialLabel>
                        <strong>{entry.display}</strong>
                        <span className="value">{formatPercent(entry.percent)}</span>
                        {menuDetailGroup === 'macro' && <span className="amount">{entry.amount}</span>}
                      </DialLabel>
                    </PercentDial>
                  ))}
                </DialGrid>
              </FoodDetailContent>
            )}
          </FoodDetailWrapper>
        ) : (
          <>
            <MenuScroll>
              <PadList>
                {menuEntries.map((entry) => (
                  <PadListItem key={entry.id}>
                    <PaletteRowButton type="button" onClick={() => setSelectedMenuEntryId(entry.id)}>
                      <div>
                        <strong>{entry.food_name ?? 'Untitled dish'}</strong>
                      </div>
                      <div className="meta">
                        <span>
                          {entry.quantity} {entry.unit}
                        </span>
                      </div>
                    </PaletteRowButton>
                  </PadListItem>
                ))}
              </PadList>
            </MenuScroll>
          </>
        )}
      </LilyPadCard>

      <LilyPadCard
        id="nutrition-stats"
        side="left"
        topOffsetPx={420}
        scale={1.02}
        aspectRatio={14 / 5}
        title={`Daily Intake — ${activeGroupLabel}`}
        interactive
        edgeOffsetPx={-10}
        sideShiftPercent={10}
        contentWidthPct={0.95}
      >
        <DialStage>
          <CycleControls>
            {GROUP_ORDER.map((key) => (
              <ControlButton
                key={key}
                type="button"
                onClick={() => setGroupIndex(GROUP_ORDER.indexOf(key))}
                $active={activeGroup === key}
              >
                {GROUP_LABELS[key]}
              </ControlButton>
            ))}
          </CycleControls>
          <DialStageContent>
            {summaryData ? (
              activeItems.length === 0 ? (
                <p style={{ opacity: 0.75 }}>No {activeGroupLabel.toLowerCase()} logged yet.</p>
              ) : (
                <DialGrid $columns={activeGroup === 'vitamin' ? 4 : 3}>
                  {activeItems.map((item) => {
                    const percent = item.percent_of_goal ?? 0;
                    const displayName = tidyDisplayName(item.display_name ?? '', activeGroup);
                    const showAmount = activeGroup === 'macro';
                    const amountLabel = showAmount ? formatAmount(item.amount, item.unit) : null;
                    return (
                      <PercentDial key={item.slug} $value={percent}>
                        <DialLabel>
                          <strong>{displayName}</strong>
                          <span className="value">{formatPercent(percent)}</span>
                          {showAmount && <span className="amount">{amountLabel}</span>}
                        </DialLabel>
                      </PercentDial>
                    );
                  })}
                </DialGrid>
              )
            ) : (
              <p style={{ opacity: 0.75 }}>Loading intake summary…</p>
            )}
          </DialStageContent>
        </DialStage>
      </LilyPadCard>

      <LilyPadCard
        id="nutrition-palette"
        side="right"
        topOffsetPx={580}
        scale={0.94}
        title="Pallete"
        interactive
        edgeOffsetPx={-40}
        sideShiftPercent={24}
        contentWidthPct={0.86}
      >
        {foodsQuery.isLoading ? (
          <p style={{ opacity: 0.75 }}>Loading pallete…</p>
        ) : foods.length === 0 ? (
          <p style={{ opacity: 0.78 }}>No foods saved yet. Logged foods will appear here so you can reuse them quickly.</p>
        ) : selectedFood ? (
          <FoodDetailWrapper>
            <FoodDetailHeader>
              <div>
                <strong>{selectedFood.name}</strong>
                <span>(1 {selectedFood.default_unit ?? 'unit'})</span>
              </div>
              <BackButton type="button" onClick={() => setSelectedFoodId(null)}>
                Back to list
              </BackButton>
            </FoodDetailHeader>
            {goalsQuery.isError ? (
              <p style={{ opacity: 0.75 }}>Unable to load nutrient targets right now.</p>
            ) : goalsQuery.isLoading ? (
              <p style={{ opacity: 0.75 }}>Loading nutrient targets…</p>
            ) : paletteDialItems.length === 0 ? (
              <p style={{ opacity: 0.75 }}>No nutrient data available for this food.</p>
            ) : (
              <FoodDetailContent>
                <CycleControls>
                  {GROUP_ORDER.map((key) => (
                    <ControlButton
                      key={key}
                      type="button"
                      onClick={() => setFoodDetailGroup(key)}
                      $active={foodDetailGroup === key}
                    >
                      {GROUP_LABELS[key]}
                    </ControlButton>
                  ))}
                </CycleControls>
                <DialGrid $columns={foodDetailGroup === 'vitamin' ? 4 : 3}>
                  {paletteDialItems.map((entry) => (
                    <PercentDial key={entry.slug} $value={entry.percent}>
                      <DialLabel>
                        <strong>{entry.display}</strong>
                        <span className="value">{formatPercent(entry.percent)}</span>
                        {foodDetailGroup === 'macro' && <span className="amount">{entry.amount}</span>}
                      </DialLabel>
                    </PercentDial>
                  ))}
                </DialGrid>
              </FoodDetailContent>
            )}
          </FoodDetailWrapper>
        ) : (
          <>
            <PaletteSearch>
              <input
                type="search"
                placeholder="Search foods…"
                value={paletteFilter}
                onChange={(e) => setPaletteFilter(e.target.value)}
              />
            </PaletteSearch>
            <PaletteScroll>
              <PadList>
                {filteredFoods.length === 0 ? (
                  <PadListItem>
                    <div>
                      <strong>No foods match “{paletteFilter}”.</strong>
                    </div>
                  </PadListItem>
                ) : (
                  filteredFoods.map((food) => (
                    <PadListItem key={food.id}>
                      <PaletteRowButton type="button" onClick={() => setSelectedFoodId(food.id)} $status={food.status}>
                        <div>
                          <strong>{food.name}</strong>
                        </div>
                        <div className="meta">
                          {(!food.status || food.status === 'unconfirmed') && (
                            <span className="warn" title="Unconfirmed food">⚠︎</span>
                          )}
                          <span>{food.default_unit}</span>
                        </div>
                      </PaletteRowButton>
                    </PadListItem>
                  ))
                )}
              </PadList>
            </PaletteScroll>
          </>
        )}
      </LilyPadCard>

      <LilyPadCard
        id="nutrition-averages"
        side="left"
        topOffsetPx={760}
        scale={0.96}
        aspectRatio={14 / 5}
        title="14-day Goal %"
        interactive
        edgeOffsetPx={-16}
        sideShiftPercent={12}
        contentWidthPct={0.92}
      >
        {historyData ? (
          <DialStage>
            <CycleControls>
              {GROUP_ORDER.map((key) => (
                <ControlButton
                  key={key}
                  type="button"
                  onClick={() => setHistoryGroupIndex(GROUP_ORDER.indexOf(key))}
                  $active={GROUP_ORDER[historyGroupIndex] === key}
                >
                  {GROUP_LABELS[key]}
                </ControlButton>
              ))}
            </CycleControls>
            <DialStageContent>
              {(() => {
                const activeHistoryGroup = GROUP_ORDER[historyGroupIndex];
                const items = historyGroups[activeHistoryGroup]?.entries ?? [];
                const macroItems = items.filter((item) => isMacroTarget(item.slug, item.display_name));
                const displayItems =
                  activeHistoryGroup === 'macro'
                    ? macroItems
                    : activeHistoryGroup === 'vitamin'
                      ? items
                      : items.slice(0, Math.max(items.length, 9));
                if (items.length === 0) {
                  return (
                    <p style={{ opacity: 0.75 }}>
                      No {GROUP_LABELS[activeHistoryGroup].toLowerCase()} logged over this window.
                    </p>
                  );
                }
                return (
                  <div style={{ width: '100%' }}>
                    <DialGrid $columns={activeHistoryGroup === 'vitamin' ? 4 : 3}>
                      {displayItems.map((item) => {
                        const percent = item.percent_of_goal ?? 0;
                        const displayName = tidyDisplayName(
                          item.display_name ?? '',
                          activeHistoryGroup
                        );
                        const showAmount = activeHistoryGroup === 'macro';
                        const amountLabel = showAmount ? formatAmount(item.average_amount, item.unit) : null;
                        return (
                          <PercentDial key={item.slug} $value={percent}>
                            <DialLabel>
                              <strong>{displayName}</strong>
                              <span className="value">{formatPercent(percent)}</span>
                              {showAmount && <span className="amount">{amountLabel}</span>}
                            </DialLabel>
                          </PercentDial>
                        );
                      })}
                    </DialGrid>
                    <Hint>Percent reflects intake vs. goal over {historyData.window_days}-day window.</Hint>
                  </div>
                );
              })()}
            </DialStageContent>
          </DialStage>
        ) : (
          <p style={{ opacity: 0.75 }}>Retrieving 14-day trends…</p>
        )}
      </LilyPadCard>

      <LilyPadCard
        id="nutrition-goals"
        side="right"
        topOffsetPx={940}
        scale={0.96}
        aspectRatio={14 / 5}
        title="Nutrient Goals"
        interactive
        edgeOffsetPx={-20}
        sideShiftPercent={10}
        contentWidthPct={0.94}
      >
        {goalsQuery.isLoading ? (
          <p style={{ opacity: 0.75 }}>Loading goals…</p>
        ) : goalsQuery.isError ? (
          <p style={{ opacity: 0.75 }}>Unable to load goals.</p>
        ) : (
          <>
            <DialStage>
              <CycleControls>
                {GROUP_ORDER.map((key) => (
                  <ControlButton
                    key={key}
                    type="button"
                    onClick={() => setGoalGroupIndex(GROUP_ORDER.indexOf(key))}
                    $active={activeGoalGroup === key}
                  >
                    {GROUP_LABELS[key]}
                  </ControlButton>
                ))}
              </CycleControls>
              <DialStageContent>
                {goalDialEntries.length === 0 ? (
                  <p style={{ opacity: 0.75 }}>
                    No {GROUP_LABELS[activeGoalGroup].toLowerCase()} configured.
                  </p>
                ) : (
                  <DialGrid $columns={activeGoalGroup === 'vitamin' ? 4 : 3}>
                    {goalDialEntries.map((entry) => (
                      <DialButton
                        key={entry.slug}
                        type="button"
                        onClick={() => onSelectGoal(entry.raw)}
                        $active={editingGoalSlug === entry.slug}
                      >
                        <PercentDial $value={entry.percent}>
                          <DialLabel>
                            <strong>{entry.display}</strong>
                            <span className="value">{formatPercent(entry.percent)}</span>
                            <span className="amount">{entry.amount}</span>
                          </DialLabel>
                        </PercentDial>
                      </DialButton>
                    ))}
                  </DialGrid>
                )}
              </DialStageContent>
            </DialStage>
            {editingGoal ? (
              <GoalEditor onSubmit={onSubmitGoal}>
                <GoalInput
                  type="number"
                  step="0.1"
                  value={editingGoalValue}
                  onChange={(e) => setEditingGoalValue(e.target.value)}
                />
                <GoalActions>
                  <button type="submit" disabled={savingGoal}>
                    {savingGoal ? 'Saving…' : 'Save'}
                  </button>
                  <button type="button" onClick={onCancelGoalEdit} disabled={savingGoal}>
                    Cancel
                  </button>
                </GoalActions>
                {editingGoal && (
                  <GoalEditorHint>
                    Editing {tidyDisplayName(editingGoal.display_name, editingGoal.group as GroupKey)} ({editingGoal.unit})
                  </GoalEditorHint>
                )}
                {goalError && <GoalError>{goalError}</GoalError>}
              </GoalEditor>
            ) : (
              <GoalEditorHint>Select a goal to edit its target.</GoalEditorHint>
            )}
          </>
        )}
      </LilyPadCard>

      <Spacer aria-hidden style={{ height: `${padSpacer}px` }} />
    </Stage>
  );
}
const ChatPadBody = styled.div`
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-height: clamp(260px, 32vh, 360px);
`;

const ChatHistory = styled.div`
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: clamp(120px, 22vh, 220px);
  overflow-y: auto;
  padding-right: 4px;
  flex: 1;
`;

const ChatBubble = styled.div<{ $role: 'user' | 'assistant' }>`
  align-self: ${({ $role }) => ($role === 'user' ? 'flex-end' : 'flex-start')};
  border-radius: 16px;
  padding: 10px 12px;
  max-width: clamp(240px, 70%, 360px);
  font-size: 0.85rem;
  background: ${({ $role }) => ($role === 'user' ? 'rgba(255,255,255,0.15)' : 'rgba(4, 22, 41, 0.55)')};
  border: 1px solid rgba(255, 255, 255, 0.1);
`;

const ChatMeta = styled.ul`
  margin: 8px 0 0;
  padding-left: 18px;
  font-size: 0.8rem;
  opacity: 0.85;
`;

const ChatForm = styled.form`
  display: flex;
  gap: 10px;
  margin-top: 14px;
`;

const ChatInput = styled.textarea`
  flex: 1;
  border-radius: 14px;
  border: 1px solid rgba(255, 255, 255, 0.25);
  background: rgba(7, 23, 44, 0.58);
  min-height: 58px;
  padding: 10px 12px;
  color: #ffffff;
  caret-color: #ffffff;
  font-family: ${({ theme }) => theme.fonts.body};
  resize: vertical;
`;

const ChatButton = styled.button`
  border: none;
  border-radius: 14px;
  padding: 12px 16px;
  font-family: ${({ theme }) => theme.fonts.heading};
  letter-spacing: 0.12em;
  background: ${({ theme }) => theme.colors.accent};
  color: ${({ theme }) => theme.colors.backgroundPage};
  cursor: pointer;
  min-width: 88px;
`;
