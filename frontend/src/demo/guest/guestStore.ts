import type {
  ClaudeChatResponse,
  ClaudeTodoResponse,
  GarminStatusResponse,
  InsightResponse,
  JournalCompletedItem,
  JournalDayResponse,
  JournalDaySummary,
  JournalEntry,
  JournalWeekDayStatus,
  JournalWeekResponse,
  MetricsOverview,
  MonetChatResponse,
  NutritionGoal,
  NutritionHistory,
  NutritionMenuResponse,
  NutritionSummary,
  RefreshStatusResponse,
  TodoItem,
  UserProfileData,
  UserProfileResponse,
  SceneTimeResponse,
  ReadinessMetricsSummary
} from '../../services/api';

const STORAGE_KEY = 'ld_guest_state';

const HRV_VALUES = [46, 48, 50, 49, 52, 51, 53, 54, 52, 55, 57, 56, 58, 52];
const RHR_VALUES = [52, 51, 51, 50, 50, 49, 48, 49, 50, 49, 48, 49, 49, 49];
const SLEEP_VALUES = [6.9, 7.2, 7.5, 7.0, 7.8, 7.6, 7.4, 7.9, 7.1, 7.7, 8.0, 7.3, 7.6, 7.6];
const LOAD_VALUES = [420, 460, 480, 510, 530, 560, 590, 610, 580, 600, 630, 640, 620, 610];

const startOfLocalDay = (date: Date) =>
  new Date(date.getFullYear(), date.getMonth(), date.getDate());

const addDays = (date: Date, offset: number) =>
  new Date(date.getFullYear(), date.getMonth(), date.getDate() + offset);

const toLocalDateKey = (date: Date) => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
};

const isoAt = (base: Date, dayOffset: number, hour: number, minute: number) =>
  new Date(
    base.getFullYear(),
    base.getMonth(),
    base.getDate() + dayOffset,
    hour,
    minute
  ).toISOString();

const resolveTimeZone = () => {
  if (typeof Intl === 'undefined') return 'UTC';
  return Intl.DateTimeFormat().resolvedOptions().timeZone ?? 'UTC';
};

const getMoment = (hour: number): SceneTimeResponse['moment'] => {
  if (hour >= 5 && hour < 11) return 'morning';
  if (hour >= 11 && hour < 16) return 'noon';
  if (hour >= 16 && hour < 20) return 'twilight';
  return 'night';
};

const includesAny = (value: string, needles: string[]) =>
  needles.some((needle) => value.includes(needle));

type GuestState = {
  base_date: string;
  todos: TodoItem[];
  next_todo_id: number;
  journal_entries: Record<string, JournalEntry[]>;
  journal_completed: Record<string, JournalCompletedItem[]>;
  journal_summaries: Record<string, JournalDaySummary | null>;
  next_journal_id: number;
  nutrition_menu: NutritionMenuResponse;
  nutrition_goals: NutritionGoal[];
  nutrition_summary: NutritionSummary;
  nutrition_history: NutritionHistory;
  user_profile: UserProfileResponse;
  garmin_status: GarminStatusResponse;
  insight: InsightResponse;
  metrics_overview: MetricsOverview;
};

let memoryState: GuestState | null = null;

const loadState = (): GuestState | null => {
  if (typeof window === 'undefined') return memoryState;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return memoryState;
    return JSON.parse(raw) as GuestState;
  } catch {
    return memoryState;
  }
};

const saveState = (state: GuestState) => {
  memoryState = state;
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // Ignore storage failures.
  }
};

const buildTrends = (baseDate: Date, values: number[]) =>
  values.map((value, index) => ({
    timestamp: isoAt(baseDate, index - (values.length - 1), 12, 0),
    value
  }));

const buildGuestState = (today: Date): GuestState => {
  const baseDate = startOfLocalDay(today);
  const baseKey = toLocalDateKey(baseDate);
  const nowIso = new Date().toISOString();

  const todos: TodoItem[] = [
    {
      id: 101,
      text:
        "Run intervals (track): 15' easy warm-up + drills; 6x800m @ ~3:10-3:15 (5K pace / RPE 8) w/ 400m jog (~2:30); 4x200m relaxed-fast @ ~40-42s w/ 200m walk; 10' cooldown (total ~7-8 mi).",
      completed: true,
      deadline_utc: isoAt(baseDate, 0, 7, 30),
      is_overdue: false,
      created_at: isoAt(baseDate, -1, 19, 10),
      updated_at: isoAt(baseDate, 0, 10, 30)
    },
    {
      id: 102,
      text:
        'Meal prep (3 lunches + 2 dinners): cook rice, roast 2 sheet pans of veggies, bake salmon; pre-wash greens; prep 3 yogurt + berry jars; portion everything into containers.',
      completed: true,
      deadline_utc: isoAt(baseDate, 0, 18, 0),
      is_overdue: false,
      created_at: isoAt(baseDate, -1, 18, 30),
      updated_at: isoAt(baseDate, 0, 13, 5)
    },
    {
      id: 103,
      text:
        'Finance admin: reconcile checking + credit cards; categorize last 30 days; adjust budget targets; schedule $250/week automatic savings transfer.',
      completed: true,
      deadline_utc: null,
      is_overdue: false,
      created_at: isoAt(baseDate, -2, 19, 30),
      updated_at: isoAt(baseDate, 0, 13, 15)
    },
    {
      id: 104,
      text:
        'Home reset: deep clean kitchen, clear fridge, restock staples, and set up a grab-and-go snack shelf for the week.',
      completed: true,
      deadline_utc: null,
      is_overdue: false,
      created_at: isoAt(baseDate, -1, 18, 40),
      updated_at: isoAt(baseDate, 0, 13, 55)
    },
    {
      id: 105,
      text:
        'Weekly planning: review calendar, pick top 3 outcomes, block 2x90m deep-work sessions, and schedule workouts + grocery run.',
      completed: true,
      deadline_utc: isoAt(baseDate, 0, 14, 30),
      is_overdue: false,
      created_at: isoAt(baseDate, 0, 12, 40),
      updated_at: isoAt(baseDate, 0, 14, 5)
    },
    {
      id: 106,
      text:
        'Record Loom: Dashboard → Insights → Nutrition → Journal → User (2–3 min walkthrough + what each screen solves).',
      completed: false,
      deadline_utc: isoAt(baseDate, 1, 19, 0),
      is_overdue: false,
      created_at: isoAt(baseDate, 0, 13, 20),
      updated_at: isoAt(baseDate, 0, 13, 20)
    },
    {
      id: 107,
      text: 'Health: schedule annual physical + labs (request lipid panel + A1C).',
      completed: false,
      deadline_utc: isoAt(baseDate, 7, 10, 0),
      is_overdue: false,
      created_at: isoAt(baseDate, 0, 13, 25),
      updated_at: isoAt(baseDate, 0, 13, 25)
    },
    {
      id: 108,
      text:
        'Admin: submit expense reimbursement (Dec/Jan receipts) with PDFs attached; update reimbursements tracker.',
      completed: false,
      deadline_utc: isoAt(baseDate, -1, 17, 0),
      is_overdue: true,
      created_at: isoAt(baseDate, -3, 16, 0),
      updated_at: isoAt(baseDate, -3, 16, 0)
    },
    {
      id: 109,
      text: 'Call insurance tomorrow morning: confirm labs coverage (lipid panel + A1C) and any pre-auth requirements.',
      completed: false,
      deadline_utc: isoAt(baseDate, 1, 9, 30),
      is_overdue: false,
      created_at: isoAt(baseDate, 0, 14, 20),
      updated_at: isoAt(baseDate, 0, 14, 20)
    }
  ].map((item) => ({
    ...item,
    deadline_is_date_only: item.deadline_is_date_only ?? false,
    is_overdue:
      !item.completed && item.deadline_utc
        ? new Date(item.deadline_utc).getTime() < Date.now()
        : false
  }));

  const completedToday: JournalCompletedItem[] = [
    { id: 101, text: todos[0].text, completed_at_utc: isoAt(baseDate, 0, 10, 35) },
    { id: 102, text: todos[1].text, completed_at_utc: isoAt(baseDate, 0, 13, 10) },
    { id: 103, text: todos[2].text, completed_at_utc: isoAt(baseDate, 0, 13, 20) },
    { id: 104, text: todos[3].text, completed_at_utc: isoAt(baseDate, 0, 13, 50) },
    { id: 105, text: todos[4].text, completed_at_utc: isoAt(baseDate, 0, 14, 8) }
  ];

  const dayMinus1Key = toLocalDateKey(addDays(baseDate, -1));
  const dayMinus2Key = toLocalDateKey(addDays(baseDate, -2));
  const dayMinus3Key = toLocalDateKey(addDays(baseDate, -3));
  const dayMinus4Key = toLocalDateKey(addDays(baseDate, -4));
  const dayMinus5Key = toLocalDateKey(addDays(baseDate, -5));
  const dayMinus6Key = toLocalDateKey(addDays(baseDate, -6));

  const journalEntries: Record<string, JournalEntry[]> = {
    [baseKey]: [
      {
        id: 201,
        text:
          'Morning: slept 7h36m. Energy steady. Focus today is easy aerobic work + protein-forward meals.',
        created_at: isoAt(baseDate, 0, 8, 10)
      },
      {
        id: 202,
        text:
          'Evening: cravings after 3pm; a 20-min walk helped. Hydration was better than yesterday.',
        created_at: isoAt(baseDate, 0, 20, 5)
      }
    ],
    [dayMinus1Key]: [
      {
        id: 208,
        text: 'Rest day paid off. Mood improved after the walk, and tomorrow’s run felt easier to say yes to.',
        created_at: isoAt(baseDate, -1, 20, 10)
      }
    ],
    [dayMinus2Key]: [
      {
        id: 203,
        text: 'Listened to the signals: HRV dipped a bit, kept the run easy, and did extra mobility instead of forcing intensity.',
        created_at: isoAt(baseDate, -2, 19, 45)
      }
    ],
    [dayMinus3Key]: [
      {
        id: 207,
        text: 'Tempo felt controlled—good sign. Keeping the week low-friction is making consistency easier.',
        created_at: isoAt(baseDate, -3, 19, 10)
      }
    ],
    [dayMinus4Key]: [
      {
        id: 204,
        text: 'Strength session felt solid. Consistency beat intensity today—sleep and hydration stayed on track.',
        created_at: isoAt(baseDate, -4, 18, 20)
      }
    ],
    [dayMinus5Key]: [
      {
        id: 206,
        text: 'Felt focused—keeping the day simple worked. Deep work first, training second, everything else trimmed.',
        created_at: isoAt(baseDate, -5, 19, 25)
      }
    ],
    [dayMinus6Key]: [
      {
        id: 205,
        text: 'Kept it aerobic. Calves felt a bit tight, so I swapped extra mobility in instead of pushing pace.',
        created_at: isoAt(baseDate, -6, 20, 5)
      }
    ]
  };

  const journalSummaries: Record<string, JournalDaySummary | null> = {
    [baseKey]: {
      groups: [
        {
          title: 'Big Wins',
          items: [
            'Completed track intervals session (6×800 + 4×200)',
            'Meal-prepped lunches + dinners for the week',
            'Reconciled accounts + set automatic savings transfer'
          ]
        },
        {
          title: 'Home Reset',
          items: [
            'Deep cleaned kitchen + cleared fridge',
            'Set up grab-and-go snack shelf (default healthy choices)',
            'Restocked staples to reduce weekday friction'
          ]
        },
        {
          title: 'Consistency',
          items: [
            'Weekly planning done (top 3 outcomes + time blocks)',
            'Walked after cravings instead of grazing',
            'Hydration improved vs yesterday'
          ]
        }
      ]
    },
    [dayMinus1Key]: {
      groups: [
        {
          title: 'Recovery Day',
          items: ['30–45 min walk for steps + stress relief', 'Shoulder/hip prehab work', 'Kept intensity low on purpose']
        },
        {
          title: 'Work/Admin',
          items: ['90 min deep work with a single deliverable', 'Sorted receipts into one folder (reimbursement-ready)']
        },
        {
          title: 'Home',
          items: ['Grocery run + easy staples', 'Prepped the kitchen for an easy week']
        }
      ]
    },
    [dayMinus2Key]: {
      groups: [
        {
          title: 'Smart Training',
          items: ['Kept run easy when recovery felt lower', 'Extra mobility instead of forcing intensity']
        },
        { title: 'Nutrition Choices', items: ['Packed lunch (skipped takeout)', 'Added vegetables at dinner'] },
        { title: 'Planning', items: ['Reviewed next-week calendar and flagged pinch points'] }
      ]
    },
    [dayMinus3Key]: {
      groups: [
        {
          title: 'Run Session',
          items: ['Tempo workout: 3×8′ @ threshold w/ 2′ jog', 'Cooldown + 8–10 min stretch']
        },
        {
          title: 'Work Progress',
          items: ['Drafted a 2-minute demo walkthrough outline', 'Wrote the next 3 highest-leverage tasks']
        },
        { title: 'Recovery', items: ['Walked after lunch', 'Lights out on time'] }
      ]
    },
    [dayMinus4Key]: {
      groups: [
        { title: 'Strength & Mobility', items: ['Strength session (form focus) completed', 'Mobility before bed instead of scrolling'] },
        { title: 'Nutrition Wins', items: ['Protein at each meal', 'Hydration goal hit (electrolytes on training day)'] },
        { title: 'Adulting', items: ['Calendar cleanup and moved lingering tasks into time blocks'] }
      ]
    },
    [dayMinus5Key]: {
      groups: [
        {
          title: 'Work',
          items: [
            'Closed the loop on two meaningful open items',
            'Blocked calendar for deep work (protected time)',
            'Inbox to near-zero'
          ]
        },
        { title: 'Training', items: ['Full-body strength (squat/hinge/pull) + 10-min core', '20-min easy walk'] },
        { title: 'Recovery', items: ['No caffeine after early afternoon', 'Earlier bedtime routine (screens down, stretch)'] }
      ]
    },
    [dayMinus6Key]: {
      groups: [
        { title: 'Training', items: ['60-min easy run + 6×20s strides', '15-min hip + calf mobility', 'Packed tomorrow’s gear + prepped hydration'] },
        { title: 'Home & Systems', items: ['Grocery list + simple meal plan (3 lunches, 2 dinners)', 'Laundry + reset workspace', 'Cleared fridge + set grab-and-go snack shelf'] },
        { title: 'People & Mindset', items: ['Called a friend/family member and made weekend plans', 'Wrote a 3-bullet weekly intention'] }
      ]
    }
  };

  const journalCompleted: Record<string, JournalCompletedItem[]> = {
    [baseKey]: completedToday,
    [dayMinus1Key]: [
      { id: 901, text: '30–45 min walk for steps + stress relief', completed_at_utc: isoAt(baseDate, -1, 14, 5) },
      { id: 902, text: 'Sorted receipts into one folder (reimbursement-ready)', completed_at_utc: isoAt(baseDate, -1, 16, 40) },
      { id: 903, text: 'Grocery run + kitchen reset', completed_at_utc: isoAt(baseDate, -1, 18, 20) }
    ],
    [dayMinus2Key]: [
      { id: 904, text: 'Easy run + extra mobility (recovery-first)', completed_at_utc: isoAt(baseDate, -2, 18, 10) },
      { id: 905, text: 'Packed lunch (skipped takeout)', completed_at_utc: isoAt(baseDate, -2, 12, 15) }
    ],
    [dayMinus3Key]: [
      { id: 906, text: 'Tempo workout: 3×8′ @ threshold', completed_at_utc: isoAt(baseDate, -3, 7, 35) },
      { id: 907, text: 'Walked after lunch', completed_at_utc: isoAt(baseDate, -3, 13, 40) },
      { id: 908, text: 'Drafted demo walkthrough outline', completed_at_utc: isoAt(baseDate, -3, 17, 25) }
    ],
    [dayMinus4Key]: [
      { id: 909, text: 'Strength session (form focus)', completed_at_utc: isoAt(baseDate, -4, 17, 50) },
      { id: 910, text: 'Hydration goal hit (electrolytes)', completed_at_utc: isoAt(baseDate, -4, 20, 0) }
    ],
    [dayMinus5Key]: [
      { id: 911, text: 'Full-body strength + core', completed_at_utc: isoAt(baseDate, -5, 18, 10) },
      { id: 912, text: 'Inbox to near-zero', completed_at_utc: isoAt(baseDate, -5, 15, 45) },
      { id: 913, text: 'No caffeine after early afternoon', completed_at_utc: isoAt(baseDate, -5, 14, 0) }
    ],
    [dayMinus6Key]: [
      { id: 914, text: '60-min easy run + strides', completed_at_utc: isoAt(baseDate, -6, 8, 20) },
      { id: 915, text: 'Grocery list + simple meal plan', completed_at_utc: isoAt(baseDate, -6, 16, 10) },
      { id: 916, text: 'Laundry + reset workspace', completed_at_utc: isoAt(baseDate, -6, 18, 35) }
    ]
  };

  const computedAt = isoAt(baseDate, 0, 6, 0);

  const nutritionGoals: NutritionGoal[] = [
    {
      slug: 'calories',
      display_name: 'Calories',
      unit: 'kcal',
      category: 'energy',
      group: 'macro',
      goal: 2350,
      default_goal: 2200,
      computed_at: computedAt,
      calorie_source: 'demo'
    },
    {
      slug: 'protein',
      display_name: 'Protein',
      unit: 'g',
      category: 'macro',
      group: 'macro',
      goal: 160,
      default_goal: 140,
      computed_at: computedAt,
      calorie_source: 'demo'
    },
    {
      slug: 'carbohydrates',
      display_name: 'Carbohydrates',
      unit: 'g',
      category: 'macro',
      group: 'macro',
      goal: 240,
      default_goal: 260,
      computed_at: computedAt,
      calorie_source: 'demo'
    },
    {
      slug: 'fat',
      display_name: 'Fat',
      unit: 'g',
      category: 'macro',
      group: 'macro',
      goal: 70,
      default_goal: 75,
      computed_at: computedAt,
      calorie_source: 'demo'
    },
    {
      slug: 'fiber',
      display_name: 'Fiber',
      unit: 'g',
      category: 'macro',
      group: 'macro',
      goal: 32,
      default_goal: 28,
      computed_at: computedAt,
      calorie_source: 'demo'
    },
    {
      slug: 'vitamin_c',
      display_name: 'Vitamin C',
      unit: 'mg',
      category: 'vitamin',
      group: 'vitamin',
      goal: 90,
      default_goal: 90
    },
    {
      slug: 'vitamin_d',
      display_name: 'Vitamin D',
      unit: 'mcg',
      category: 'vitamin',
      group: 'vitamin',
      goal: 20,
      default_goal: 20
    },
    {
      slug: 'magnesium',
      display_name: 'Magnesium',
      unit: 'mg',
      category: 'mineral',
      group: 'mineral',
      goal: 420,
      default_goal: 400
    },
    {
      slug: 'iron',
      display_name: 'Iron',
      unit: 'mg',
      category: 'mineral',
      group: 'mineral',
      goal: 18,
      default_goal: 18
    }
  ];

  const nutritionMenu: NutritionMenuResponse = {
    day: baseKey,
    entries: [
      { id: 401, ingredient_id: 9001, ingredient_name: 'Greek yogurt', quantity: 250, unit: 'g', source: 'manual' },
      { id: 402, ingredient_id: 9002, ingredient_name: 'Blueberries', quantity: 120, unit: 'g', source: 'manual' },
      { id: 403, ingredient_id: 9003, ingredient_name: 'Chicken burrito bowl', quantity: 1, unit: 'serving', source: 'manual' },
      { id: 404, ingredient_id: 9004, ingredient_name: 'Salmon + rice + greens', quantity: 1, unit: 'plate', source: 'manual' },
      { id: 405, ingredient_id: 9005, ingredient_name: 'Dark chocolate', quantity: 20, unit: 'g', source: 'manual' }
    ]
  };

  const nutritionSummary: NutritionSummary = {
    date: baseKey,
    nutrients: [
      { slug: 'calories', display_name: 'Calories', group: 'macro', unit: 'kcal', amount: 1820, goal: 2350, percent_of_goal: 77.4 },
      { slug: 'protein', display_name: 'Protein', group: 'macro', unit: 'g', amount: 142, goal: 160, percent_of_goal: 88.8 },
      { slug: 'carbohydrates', display_name: 'Carbohydrates', group: 'macro', unit: 'g', amount: 198, goal: 240, percent_of_goal: 82.5 },
      { slug: 'fat', display_name: 'Fat', group: 'macro', unit: 'g', amount: 56, goal: 70, percent_of_goal: 80.0 },
      { slug: 'fiber', display_name: 'Fiber', group: 'macro', unit: 'g', amount: 28, goal: 32, percent_of_goal: 87.5 },
      { slug: 'vitamin_c', display_name: 'Vitamin C', group: 'vitamin', unit: 'mg', amount: 104, goal: 90, percent_of_goal: 115.5 },
      { slug: 'vitamin_d', display_name: 'Vitamin D', group: 'vitamin', unit: 'mcg', amount: 12, goal: 20, percent_of_goal: 60.0 },
      { slug: 'magnesium', display_name: 'Magnesium', group: 'mineral', unit: 'mg', amount: 360, goal: 420, percent_of_goal: 85.7 },
      { slug: 'iron', display_name: 'Iron', group: 'mineral', unit: 'mg', amount: 14, goal: 18, percent_of_goal: 77.8 }
    ]
  };

  const nutritionHistory: NutritionHistory = {
    window_days: 14,
    nutrients: [
      { slug: 'calories', display_name: 'Calories', group: 'macro', unit: 'kcal', average_amount: 2105, goal: 2350, percent_of_goal: 89.6 },
      { slug: 'protein', display_name: 'Protein', group: 'macro', unit: 'g', average_amount: 151, goal: 160, percent_of_goal: 94.4 },
      { slug: 'carbohydrates', display_name: 'Carbohydrates', group: 'macro', unit: 'g', average_amount: 226, goal: 240, percent_of_goal: 94.2 },
      { slug: 'fat', display_name: 'Fat', group: 'macro', unit: 'g', average_amount: 68, goal: 70, percent_of_goal: 97.1 },
      { slug: 'fiber', display_name: 'Fiber', group: 'macro', unit: 'g', average_amount: 26, goal: 32, percent_of_goal: 81.3 }
    ]
  };

  const userProfile: UserProfileResponse = {
    profile: {
      date_of_birth: '1992-06-14',
      sex: 'male',
      height_cm: 178,
      current_weight_kg: 80.5,
      preferred_units: 'imperial',
      daily_energy_delta_kcal: -250
    },
    measurements: [
      { measured_at: isoAt(baseDate, -14, 8, 0), weight_kg: 81.4 },
      { measured_at: isoAt(baseDate, -10, 8, 0), weight_kg: 81.0 },
      { measured_at: isoAt(baseDate, -6, 8, 0), weight_kg: 80.7 },
      { measured_at: isoAt(baseDate, -2, 8, 0), weight_kg: 80.6 },
      { measured_at: isoAt(baseDate, 0, 8, 0), weight_kg: 80.5 }
    ],
    latest_energy: {
      metric_date: baseKey,
      active_kcal: 640,
      bmr_kcal: 1760,
      total_kcal: 2400,
      source: 'demo'
    },
    goals: nutritionGoals,
    scaling_rules: { rules: [], manual_rule_slug: null }
  };

  const garminStatus: GarminStatusResponse = {
    connected: true,
    garmin_email: 'demo.garmin@life-dashboard.demo',
    connected_at: isoAt(baseDate, -6, 9, 0),
    last_sync_at: isoAt(baseDate, 0, 14, 0),
    requires_reauth: false
  };

  const insight: InsightResponse = {
    metric_date: baseKey,
    readiness_score: 78,
    readiness_label: 'Primed',
    narrative:
      'Recovery is trending steady. HRV held its line while resting HR stayed low. Today is a good day for skill work or an easy aerobic session.',
    source_model: 'demo',
    last_updated: nowIso,
    refreshing: false,
    greeting: 'Good morning. Your baseline looks stable - keep the day simple and consistent.',
    hrv_value_ms: 52,
    hrv_note: 'Steady HRV - recovery looks reliable.',
    hrv_score: 0.78,
    rhr_value_bpm: 49,
    rhr_note: 'Resting HR is low; stress load looks manageable.',
    rhr_score: 0.82,
    sleep_value_hours: 7.6,
    sleep_note: 'Solid duration - keep bedtime consistent.',
    sleep_score: 0.8,
    training_load_value: 610,
    training_load_note: 'Load is moderate; an easy day fits well.',
    training_load_score: 0.7,
    morning_note: 'Fuel early, hydrate, and choose low-friction wins.'
  };

  const metricsOverview: MetricsOverview = {
    generated_at: nowIso,
    range_label: 'Last 14 days',
    training_volume_hours: 8.4,
    training_volume_window_days: 14,
    training_load_avg: 560,
    training_load_trend: buildTrends(baseDate, LOAD_VALUES),
    hrv_trend_ms: buildTrends(baseDate, HRV_VALUES),
    rhr_trend_bpm: buildTrends(baseDate, RHR_VALUES),
    sleep_trend_hours: buildTrends(baseDate, SLEEP_VALUES)
  };

  return {
    base_date: baseKey,
    todos,
    next_todo_id: 110,
    journal_entries: journalEntries,
    journal_completed: journalCompleted,
    journal_summaries: journalSummaries,
    next_journal_id: 209,
    nutrition_menu: nutritionMenu,
    nutrition_goals: nutritionGoals,
    nutrition_summary: nutritionSummary,
    nutrition_history: nutritionHistory,
    user_profile: userProfile,
    garmin_status: garminStatus,
    insight,
    metrics_overview: metricsOverview
  };
};

const getGuestState = () => {
  const todayKey = toLocalDateKey(new Date());
  const stored = loadState();
  if (!stored || stored.base_date !== todayKey) {
    const fresh = buildGuestState(new Date());
    saveState(fresh);
    return fresh;
  }
  return stored;
};

export const clearGuestState = () => {
  memoryState = null;
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Ignore storage failures.
  }
};

export const getGuestAuthMe = () => ({
  user: {
    id: 999999,
    email: 'guest@life-dashboard.demo',
    display_name: 'Guest',
    role: 'user',
    email_verified: true
  }
});

export const getGuestSceneTime = (): SceneTimeResponse => {
  const now = new Date();
  const hour = now.getHours();
  const minutes = now.getMinutes();
  return {
    iso: now.toISOString(),
    time_zone: resolveTimeZone(),
    hour_decimal: hour + minutes / 60,
    moment: getMoment(hour)
  };
};

export const getGuestTodos = (): TodoItem[] => getGuestState().todos;

export const createGuestTodo = (payload: {
  text: string;
  deadline_utc?: string | null;
  deadline_is_date_only?: boolean;
  time_zone?: string;
}): TodoItem => {
  const state = getGuestState();
  const nowIso = new Date().toISOString();
  const nextId = state.next_todo_id;
  state.next_todo_id += 1;
  const item: TodoItem = {
    id: nextId,
    text: payload.text,
    completed: false,
    deadline_utc: payload.deadline_utc ?? null,
    deadline_is_date_only: payload.deadline_is_date_only ?? false,
    is_overdue: payload.deadline_utc
      ? new Date(payload.deadline_utc).getTime() < Date.now()
      : false,
    created_at: nowIso,
    updated_at: nowIso
  };
  state.todos = [...state.todos, item];
  saveState(state);
  return item;
};

export const updateGuestTodo = (
  id: number,
  payload: {
    text?: string;
    deadline_utc?: string | null;
    deadline_is_date_only?: boolean;
    completed?: boolean;
    time_zone?: string;
  }
): TodoItem => {
  const state = getGuestState();
  const nowIso = new Date().toISOString();
  const nextTodos = state.todos.map((item) => {
    if (item.id !== id) return item;
    const completed = payload.completed ?? item.completed;
    const deadline = payload.deadline_utc ?? item.deadline_utc ?? null;
    const isOverdue = !completed && deadline ? new Date(deadline).getTime() < Date.now() : false;
    return {
      ...item,
      text: payload.text ?? item.text,
      completed,
      deadline_utc: deadline,
      deadline_is_date_only: payload.deadline_is_date_only ?? item.deadline_is_date_only,
      is_overdue: isOverdue,
      updated_at: nowIso
    };
  });
  const updated = nextTodos.find((item) => item.id === id);
  if (!updated) return state.todos[0];
  state.todos = nextTodos;
  saveState(state);
  return updated;
};

export const deleteGuestTodo = (id: number) => {
  const state = getGuestState();
  state.todos = state.todos.filter((item) => item.id !== id);
  saveState(state);
};

export const getGuestNutritionMenu = (day?: string): NutritionMenuResponse => {
  const state = getGuestState();
  if (!day) return state.nutrition_menu;
  return { ...state.nutrition_menu, day };
};

export const deleteGuestNutritionEntry = (id: number) => {
  const state = getGuestState();
  state.nutrition_menu = {
    ...state.nutrition_menu,
    entries: state.nutrition_menu.entries.filter((entry) => entry.id !== id)
  };
  saveState(state);
};

export const updateGuestNutritionEntry = (
  id: number,
  payload: { quantity: number; unit: string }
) => {
  const state = getGuestState();
  state.nutrition_menu = {
    ...state.nutrition_menu,
    entries: state.nutrition_menu.entries.map((entry) =>
      entry.id === id ? { ...entry, quantity: payload.quantity, unit: payload.unit } : entry
    )
  };
  saveState(state);
  return state.nutrition_menu.entries.find((entry) => entry.id === id);
};

export const getGuestNutritionGoals = (): NutritionGoal[] => getGuestState().nutrition_goals;

export const updateGuestNutritionGoal = (slug: string, goal: number): NutritionGoal => {
  const state = getGuestState();
  state.nutrition_goals = state.nutrition_goals.map((item) =>
    item.slug === slug ? { ...item, goal } : item
  );
  const updated = state.nutrition_goals.find((item) => item.slug === slug) ?? state.nutrition_goals[0];
  saveState(state);
  return updated;
};

export const getGuestNutritionDailySummary = (day?: string): NutritionSummary => {
  const state = getGuestState();
  if (!day) return state.nutrition_summary;
  return { ...state.nutrition_summary, date: day };
};

export const getGuestNutritionHistory = (days = 14): NutritionHistory => {
  const state = getGuestState();
  return { ...state.nutrition_history, window_days: days };
};

export const getGuestUserProfile = (): UserProfileResponse => getGuestState().user_profile;

export const updateGuestUserProfile = (payload: UserProfileData): UserProfileResponse => {
  const state = getGuestState();
  state.user_profile = {
    ...state.user_profile,
    profile: {
      ...state.user_profile.profile,
      ...payload
    }
  };
  saveState(state);
  return state.user_profile;
};

export const getGuestGarminStatus = (): GarminStatusResponse => getGuestState().garmin_status;

export const getGuestInsight = (): InsightResponse => getGuestState().insight;

export const getGuestMetricsOverview = (rangeDays = 14): MetricsOverview => {
  const state = getGuestState();
  const overview = state.metrics_overview;
  const slice = <T,>(values: T[]) => (values.length > rangeDays ? values.slice(-rangeDays) : values);
  if (rangeDays >= overview.hrv_trend_ms.length) return overview;
  return {
    ...overview,
    range_label: `Last ${rangeDays} days`,
    training_volume_window_days: rangeDays,
    training_load_trend: slice(overview.training_load_trend),
    hrv_trend_ms: slice(overview.hrv_trend_ms),
    rhr_trend_bpm: slice(overview.rhr_trend_bpm),
    sleep_trend_hours: slice(overview.sleep_trend_hours)
  };
};

export const getGuestReadinessSummary = (): ReadinessMetricsSummary => ({
  date: getGuestState().base_date,
  hrv: { value: 52, value_unit: 'ms', reference_value: 50, reference_label: '14-day avg', delta: 2, delta_unit: 'ms' },
  rhr: { value: 49, value_unit: 'bpm', reference_value: 50, reference_label: '14-day avg', delta: -1, delta_unit: 'bpm' },
  sleep: { value: 7.6, value_unit: 'hrs', reference_value: 7.4, reference_label: '14-day avg', delta: 0.2, delta_unit: 'hrs' },
  training_load: { value: 610, value_unit: 'pts', reference_value: 560, reference_label: '14-day avg', delta: 50, delta_unit: 'pts' }
});

export const getGuestRefreshStatus = (): RefreshStatusResponse => ({
  job_started: false,
  running: false,
  cooldown_seconds: 1800,
  message: 'Guest mode: refresh disabled.',
  last_error: null
});

export const getGuestJournalDay = (localDate: string, timeZone: string): JournalDayResponse => {
  const state = getGuestState();
  const entries = state.journal_entries[localDate] ?? [];
  const completed_items = state.journal_completed[localDate] ?? [];
  const summary = state.journal_summaries[localDate] ?? null;
  return {
    local_date: localDate,
    time_zone: timeZone,
    status: 'ok',
    entries,
    completed_items,
    summary
  };
};

export const getGuestJournalWeek = (weekStart: string, timeZone: string): JournalWeekResponse => {
  const state = getGuestState();
  const weekStartDate = new Date(`${weekStart}T00:00:00`);
  const days: JournalWeekDayStatus[] = [];
  for (let i = 0; i < 7; i += 1) {
    const day = addDays(weekStartDate, i);
    const key = toLocalDateKey(day);
    const entries = state.journal_entries[key] ?? [];
    const summary = state.journal_summaries[key];
    const completed = state.journal_completed[key] ?? [];
    days.push({
      local_date: key,
      has_entries: entries.length > 0,
      has_summary: Boolean(summary && summary.groups?.length),
      completed_count: completed.length
    });
  }
  const weekEndKey = toLocalDateKey(addDays(weekStartDate, 6));
  return {
    week_start: weekStart,
    week_end: weekEndKey,
    days
  };
};

export const createGuestJournalEntry = (text: string): JournalEntry => {
  const state = getGuestState();
  const todayKey = toLocalDateKey(new Date());
  const nowIso = new Date().toISOString();
  const entry: JournalEntry = {
    id: state.next_journal_id,
    text,
    created_at: nowIso
  };
  state.next_journal_id += 1;
  state.journal_entries = {
    ...state.journal_entries,
    [todayKey]: [...(state.journal_entries[todayKey] ?? []), entry]
  };
  saveState(state);
  return entry;
};

const upsertGuestNutritionMenuEntry = (payload: {
  ingredient_id: number;
  ingredient_name: string;
  quantity: number;
  unit: string;
}): { created: boolean } => {
  const state = getGuestState();
  const normalized = payload.ingredient_name.trim().toLowerCase();
  const existing = state.nutrition_menu.entries.find(
    (entry) => (entry.ingredient_name ?? '').trim().toLowerCase() === normalized
  );
  if (existing) return { created: false };

  const nextId =
    state.nutrition_menu.entries.reduce((max, entry) => Math.max(max, entry.id), 0) + 1;
  state.nutrition_menu = {
    ...state.nutrition_menu,
    entries: [
      ...state.nutrition_menu.entries,
      {
        id: nextId,
        ingredient_id: payload.ingredient_id,
        ingredient_name: payload.ingredient_name,
        quantity: payload.quantity,
        unit: payload.unit,
        source: 'assistant'
      }
    ]
  };
  saveState(state);
  return { created: true };
};

const findGuestTodo = (predicate: (todo: TodoItem) => boolean): TodoItem | undefined => {
  const state = getGuestState();
  return state.todos.find(predicate);
};

export const getGuestMonetChatResponse = (payload: {
  message: string;
  session_id?: string;
}): MonetChatResponse => {
  const trimmed = payload.message.trim();
  const message = trimmed.toLowerCase();
  const baseDate = startOfLocalDay(new Date());

  const nutrition_entries: MonetChatResponse['nutrition_entries'] = [];
  const todo_items: MonetChatResponse['todo_items'] = [];
  const tools_used: string[] = [];

  const wantsPlan = includesAny(message, ['plan my day', 'today plan', 'plan today']);
  const wantsReadiness = includesAny(message, ['readiness', 'energy', 'how am i doing', 'how are my metrics']);
  const wantsCravings = includesAny(message, ['craving', 'cravings', 'snack', 'sweet']);
  const wantsReimbursement = includesAny(message, ['reimbursement', 'expense', 'receipts']);
  const wantsDemo = includesAny(message, ['loom', 'walkthrough', 'demo']);
  const mentionsInsuranceCall =
    includesAny(message, ['insurance']) && includesAny(message, ['call', 'remind']);
  const mentionsPhysical =
    includesAny(message, ['annual physical', 'physical']) && includesAny(message, ['schedule', 'book']);

  const logFood = (spec: { ingredient_id: number; food_name: string; quantity: number; unit: string }) => {
    const { created } = upsertGuestNutritionMenuEntry({
      ingredient_id: spec.ingredient_id,
      ingredient_name: spec.food_name,
      quantity: spec.quantity,
      unit: spec.unit
    });
    nutrition_entries.push({
      ingredient_id: spec.ingredient_id,
      food_name: spec.food_name,
      quantity: spec.quantity,
      unit: spec.unit,
      status: 'logged',
      created
    });
    tools_used.push('demo:nutrition-log');
  };

  const ensureTodo = (options: {
    match: (todo: TodoItem) => boolean;
    create: () => TodoItem;
    update?: (todo: TodoItem) => TodoItem;
  }) => {
    const existing = findGuestTodo(options.match);
    if (!existing) {
      const created = options.create();
      todo_items.push(created);
      tools_used.push('demo:todo-create');
      return;
    }
    if (options.update) {
      const updated = options.update(existing);
      todo_items.push(updated);
      tools_used.push('demo:todo-update');
      return;
    }
    todo_items.push(existing);
  };

  // Meal logging packs.
  if (includesAny(message, ['yogurt', 'greek yogurt', 'blueberries', 'breakfast'])) {
    logFood({ ingredient_id: 9001, food_name: 'Greek yogurt', quantity: 250, unit: 'g' });
    logFood({ ingredient_id: 9002, food_name: 'Blueberries', quantity: 120, unit: 'g' });
  }
  if (includesAny(message, ['burrito bowl', 'lunch'])) {
    logFood({ ingredient_id: 9003, food_name: 'Chicken burrito bowl', quantity: 1, unit: 'serving' });
  }
  if (includesAny(message, ['salmon']) || (message.includes('rice') && message.includes('greens'))) {
    logFood({ ingredient_id: 9004, food_name: 'Salmon + rice + greens', quantity: 1, unit: 'plate' });
  }
  if (includesAny(message, ['dark chocolate', 'chocolate'])) {
    logFood({ ingredient_id: 9005, food_name: 'Dark chocolate', quantity: 20, unit: 'g' });
  }

  // Task capture packs.
  if (mentionsInsuranceCall) {
    ensureTodo({
      match: (todo) => todo.text.toLowerCase().includes('call insurance'),
      create: () =>
        createGuestTodo({
          text: 'Call insurance tomorrow morning: confirm labs coverage (lipid panel + A1C) and any pre-auth requirements.',
          deadline_utc: isoAt(baseDate, 1, 9, 30)
        })
    });
  }

  if (mentionsPhysical) {
    ensureTodo({
      match: (todo) => todo.text.toLowerCase().includes('annual physical'),
      create: () =>
        createGuestTodo({
          text: 'Health: schedule annual physical + labs (request lipid panel + A1C).',
          deadline_utc: isoAt(baseDate, 7, 10, 0)
        })
    });
  }

  if (wantsReimbursement) {
    ensureTodo({
      match: (todo) => todo.text.toLowerCase().includes('expense reimbursement') || todo.text.toLowerCase().includes('reimbursement'),
      create: () =>
        createGuestTodo({
          text: 'Submit expense reimbursement packet (Dec/Jan) + attach PDFs; update reimbursements tracker.',
          deadline_utc: isoAt(baseDate, 1, 17, 0)
        }),
      update: (todo) =>
        updateGuestTodo(todo.id, {
          text: 'Submit expense reimbursement packet (Dec/Jan) + attach PDFs; update reimbursements tracker.',
          deadline_utc: isoAt(baseDate, 1, 17, 0)
        })
    });
  }

  if (wantsDemo) {
    ensureTodo({
      match: (todo) => todo.text.toLowerCase().includes('loom') || todo.text.toLowerCase().includes('walkthrough'),
      create: () =>
        createGuestTodo({
          text: 'Record Loom: Dashboard → Insights → Nutrition → Journal → User (2–3 min walkthrough + what each screen solves).',
          deadline_utc: isoAt(baseDate, 1, 19, 0)
        }),
      update: (todo) =>
        updateGuestTodo(todo.id, {
          text: 'Record Loom: Dashboard → Insights → Nutrition → Journal → User (2–3 min walkthrough + what each screen solves).',
          deadline_utc: isoAt(baseDate, 1, 19, 0)
        })
    });
  }

  if (wantsPlan) {
    const deepWorkText = '90m deep work (single outcome) — pick one finish line and ship it.';
    const walkText = '20m walk after lunch (stress + cravings reset).';
    const dinnerText = 'Prep dinner components (protein + veg) so future-you wins.';

    ensureTodo({
      match: (todo) => todo.text.toLowerCase().includes('90m deep work'),
      create: () => createGuestTodo({ text: deepWorkText, deadline_utc: isoAt(baseDate, 0, 11, 30) })
    });
    ensureTodo({
      match: (todo) => todo.text.toLowerCase().includes('walk after lunch'),
      create: () => createGuestTodo({ text: walkText, deadline_utc: isoAt(baseDate, 0, 14, 30) })
    });
    ensureTodo({
      match: (todo) => todo.text.toLowerCase().includes('prep dinner components'),
      create: () => createGuestTodo({ text: dinnerText, deadline_utc: isoAt(baseDate, 0, 18, 0) })
    });
  }

  let reply = '';
  if (wantsReadiness) {
    reply =
      'You’re looking steady today: HRV holding, resting HR low, sleep solid. Keep training quality high but volume controlled—skill work or easy aerobic wins.';
  } else if (wantsPlan) {
    reply =
      'Here’s a low-friction day: 1) one deep-work block, 2) a short walk after lunch, 3) set up dinner so future-you wins.';
  } else if (wantsCravings) {
    reply =
      'Two-step reset: 12–20 min walk + water first. If you still want something sweet, portion it and enjoy it.';
  } else if (wantsReimbursement) {
    reply =
      'Added a clean, finish-line version so it’s easy to knock out in one sitting.';
  } else if (wantsDemo) {
    reply =
      'Added. Keep it to 2–3 minutes and narrate what problem each screen solves.';
  } else if (nutrition_entries.length > 0 && todo_items.length > 0) {
    reply =
      'Done. Logged your meal and added that reminder. If you tell me when, I’ll attach a due time.';
  } else if (nutrition_entries.length > 0) {
    reply = 'Logged with care. Want a quick protein/fiber check for the day?';
  } else if (todo_items.length > 0) {
    reply = 'Consider it done. I added that to your list.';
  } else {
    reply = 'Noted. What’s the next small step you want to make inevitable?';
  }

  return {
    session_id: payload.session_id ?? 'guest-demo-session',
    reply,
    nutrition_entries,
    todo_items,
    tools_used
  };
};

export const getGuestClaudeChatResponse = (payload: { message: string; session_id?: string }): ClaudeChatResponse => ({
  session_id: payload.session_id ?? 'guest-nutrition-session',
  reply:
    'Guest mode is local-only. Sign in to log foods and get personalized nutrient breakdowns.',
  logged_entries: []
});

export const getGuestClaudeTodoResponse = (payload: { message: string; session_id?: string }): ClaudeTodoResponse => ({
  session_id: payload.session_id ?? 'guest-todo-session',
  reply: 'Guest mode is local-only. Sign in to create and manage real tasks.',
  created_items: [],
  raw_payload: null
});
