import axios from 'axios';

const baseURL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

export const api = axios.create({
  baseURL,
  timeout: 180000,
  withCredentials: true
});

// Auth

export type AuthUser = {
  id: number;
  email: string;
  display_name: string | null;
  role: 'admin' | 'user';
  email_verified: boolean;
};

export type AuthMeResponse = {
  user: AuthUser;
};

export const fetchAuthMe = async (): Promise<AuthMeResponse> => {
  const { data } = await api.get('/api/auth/me');
  return data;
};

export const logout = async (): Promise<void> => {
  await api.post('/api/auth/logout');
};

// Garmin

export type GarminStatusResponse = {
  connected: boolean;
  garmin_email: string | null;
  connected_at: string | null;
  last_sync_at: string | null;
  requires_reauth: boolean;
};

export type GarminConnectPayload = {
  garmin_email: string;
  garmin_password: string;
};

export type GarminConnectResponse = {
  connected: boolean;
  garmin_email: string;
  connected_at: string;
  requires_reauth: boolean;
};

export const fetchGarminStatus = async (): Promise<GarminStatusResponse> => {
  const { data } = await api.get('/api/garmin/status');
  return data;
};

export const connectGarmin = async (payload: GarminConnectPayload): Promise<GarminConnectResponse> => {
  const { data } = await api.post('/api/garmin/connect', payload);
  return data;
};

export const reauthGarmin = async (): Promise<GarminStatusResponse> => {
  const { data } = await api.post('/api/garmin/reauth');
  return data;
};

export type InsightResponse = {
  metric_date: string;
  readiness_score: number | null;
  readiness_label: string | null;
  narrative: string;
  source_model: string;
  last_updated: string;
  refreshing?: boolean;
  greeting?: string | null;
  hrv_value_ms?: number | null;
  hrv_note?: string | null;
  hrv_score?: number | null;
  rhr_value_bpm?: number | null;
  rhr_note?: string | null;
  rhr_score?: number | null;
  sleep_value_hours?: number | null;
  sleep_note?: string | null;
  sleep_score?: number | null;
  training_load_value?: number | null;
  training_load_note?: string | null;
  training_load_score?: number | null;
  morning_note?: string | null;
};

export type MetricDelta = {
  value: number | null;
  value_unit: string;
  reference_value: number | null;
  reference_label: string;
  delta: number | null;
  delta_unit: string;
};

export type ReadinessMetricsSummary = {
  date: string;
  hrv: MetricDelta;
  rhr: MetricDelta;
  sleep: MetricDelta;
  training_load: MetricDelta;
};

export type MetricsOverview = {
  generated_at: string;
  range_label: string;
  training_volume_hours: number;
  training_volume_window_days: number;
  training_load_avg: number | null;
  training_load_trend: { timestamp: string; value: number | null }[];
  hrv_trend_ms: { timestamp: string; value: number | null }[];
  rhr_trend_bpm: { timestamp: string; value: number | null }[];
  sleep_trend_hours: { timestamp: string; value: number | null }[];
};

export type SceneTimeResponse = {
  iso: string;
  time_zone: string;
  hour_decimal: number;
  moment: 'morning' | 'noon' | 'twilight' | 'night';
};

export type RefreshStatusResponse = {
  job_started: boolean;
  running: boolean;
  last_started_at?: string | null;
  last_completed_at?: string | null;
  next_allowed_at?: string | null;
  cooldown_seconds: number;
  message?: string | null;
  last_error?: string | null;
};

export const fetchInsight = async (): Promise<InsightResponse> => {
  const { data } = await api.get('/api/insights/daily');
  return data;
};

export const fetchMetricsOverview = async (rangeDays = 7): Promise<MetricsOverview> => {
  const { data } = await api.get('/api/metrics/overview', { params: { range_days: rangeDays } });
  return data;
};

export const fetchReadinessSummary = async (): Promise<ReadinessMetricsSummary> => {
  const { data } = await api.get('/api/metrics/readiness-summary');
  return data;
};

export const fetchSceneTime = async (): Promise<SceneTimeResponse> => {
  const { data } = await api.get('/api/time');
  return data;
};

export const triggerVisitRefresh = async (): Promise<RefreshStatusResponse> => {
  const { data } = await api.post('/api/system/refresh-today');
  return data;
};

// Nutrition

export type NutritionNutrient = {
  slug: string;
  display_name: string;
  category: string;
  group: string;
  unit: string;
  default_goal: number;
};

export type IngredientStatus = 'confirmed' | 'unconfirmed';

export type NutritionIngredient = {
  id: number;
  owner_user_id: number;
  name: string;
  default_unit: string;
  status: IngredientStatus;
  source?: string | null;
  nutrients: Record<string, number | null>;
};

export type RecipeComponent = {
  ingredient_id?: number | null;
  child_recipe_id?: number | null;
  ingredient_name?: string | null;
  child_recipe_name?: string | null;
  quantity: number;
  unit: string;
  position?: number | null;
};

export type NutritionRecipe = {
  id: number;
  owner_user_id: number;
  name: string;
  default_unit: string;
  servings: number;
  status: IngredientStatus;
  components: RecipeComponent[];
  derived_nutrients: Record<string, number | null>;
};

export type RecipeSuggestion = {
  recipe: {
    name: string;
    default_unit: string;
    servings: number;
    status?: IngredientStatus;
    components?: RecipeComponent[];
  };
  ingredients: Array<{
    name: string;
    quantity: number;
    unit: string;
  }>;
};

export type NutritionGoal = {
  slug: string;
  display_name: string;
  unit: string;
  category: string;
  group: string;
  goal: number;
  default_goal: number;
  computed_at?: string | null;
  computed_from_date?: string | null;
  calorie_source?: string | null;
};

export type NutritionSummary = {
  date: string;
  nutrients: Array<{
    slug: string;
    display_name: string;
    group: string;
    unit: string;
    amount: number | null;
    goal: number | null;
    percent_of_goal: number | null;
  }>;
};

export type NutritionHistory = {
  window_days: number;
  nutrients: Array<{
    slug: string;
    display_name: string;
    group: string;
    unit: string;
    average_amount: number | null;
    goal: number | null;
    percent_of_goal: number | null;
  }>;
};

export type ClaudeChatResponse = {
  session_id: string;
  reply: string;
  logged_entries: Array<{
    ingredient_id?: number;
    recipe_id?: number;
    food_name: string;
    quantity: number;
    unit: string;
    status: string;
    created?: boolean;
  }>;
};

export const fetchNutritionNutrients = async (): Promise<NutritionNutrient[]> => {
  const { data } = await api.get('/api/nutrition/nutrients');
  return data;
};

export type NutritionMenuResponse = {
  day: string;
  entries: Array<{
    id: number;
    ingredient_id: number;
    ingredient_name?: string | null;
    quantity: number;
    unit: string;
    source: string;
  }>;
};

export const fetchNutritionMenu = async (day?: string): Promise<NutritionMenuResponse> => {
  const { data } = await api.get('/api/nutrition/intake/menu', { params: { day } });
  return data;
};

export const updateNutritionIntake = async (
  intakeId: number,
  payload: { quantity: number; unit: string }
) => {
  const { data } = await api.patch(`/api/nutrition/intake/${intakeId}`, payload);
  return data;
};

export const deleteNutritionIntake = async (intakeId: number) => {
  await api.delete(`/api/nutrition/intake/${intakeId}`);
};

export const fetchNutritionIngredients = async (): Promise<NutritionIngredient[]> => {
  const { data } = await api.get('/api/nutrition/ingredients');
  return data;
};

export const createNutritionIngredient = async (payload: Partial<NutritionIngredient>) => {
  const { data } = await api.post('/api/nutrition/ingredients', payload);
  return data as NutritionIngredient;
};

export const updateNutritionIngredient = async (id: number, payload: Partial<NutritionIngredient>) => {
  const { data } = await api.patch(`/api/nutrition/ingredients/${id}`, payload);
  return data as NutritionIngredient;
};

export const fetchNutritionRecipes = async (): Promise<NutritionRecipe[]> => {
  const { data } = await api.get('/api/nutrition/recipes');
  return data;
};

export const fetchNutritionRecipe = async (id: number): Promise<NutritionRecipe> => {
  const { data } = await api.get(`/api/nutrition/recipes/${id}`);
  return data;
};

export const createNutritionRecipe = async (payload: Partial<NutritionRecipe>) => {
  const { data } = await api.post('/api/nutrition/recipes', payload);
  return data as NutritionRecipe;
};

export const updateNutritionRecipe = async (id: number, payload: Partial<NutritionRecipe>) => {
  const { data } = await api.patch(`/api/nutrition/recipes/${id}`, payload);
  return data as NutritionRecipe;
};

export const suggestNutritionRecipe = async (description: string): Promise<RecipeSuggestion> => {
  const { data } = await api.post('/api/nutrition/recipes/suggest', null, { params: { description } });
  return data as RecipeSuggestion;
};

export const fetchNutritionGoals = async (): Promise<NutritionGoal[]> => {
  const { data } = await api.get('/api/nutrition/goals');
  return data;
};

export const updateNutritionGoal = async (slug: string, goal: number) => {
  const { data } = await api.put(`/api/nutrition/goals/${slug}`, { goal });
  return data as NutritionGoal;
};

export const logManualIntake = async (payload: { ingredient_id?: number; recipe_id?: number; quantity: number; unit: string; day?: string }) => {
  const { data } = await api.post('/api/nutrition/intake/manual', payload);
  return data as { id?: number } & typeof payload;
};

export const fetchNutritionDailySummary = async (day?: string): Promise<NutritionSummary> => {
  const { data } = await api.get('/api/nutrition/intake/daily', { params: { day } });
  return data;
};

export const fetchNutritionHistory = async (days = 14): Promise<NutritionHistory> => {
  const { data } = await api.get('/api/nutrition/intake/history', { params: { days } });
  return data;
};

export const sendClaudeMessage = async (message: string, session_id?: string): Promise<ClaudeChatResponse> => {
  const { data } = await api.post('/api/nutrition/claude/message', { message, session_id });
  return data;
};

// Todos

export type TodoItem = {
  id: number;
  text: string;
  completed: boolean;
  deadline_utc: string | null;
  is_overdue: boolean;
  created_at: string;
  updated_at: string;
};

export type ClaudeTodoResponse = {
  session_id: string;
  reply: string;
  created_items: TodoItem[];
  raw_payload?: Record<string, unknown> | null;
};

export const fetchTodos = async (time_zone?: string): Promise<TodoItem[]> => {
  const { data } = await api.get('/api/todos', { params: { time_zone } });
  return data;
};

export const createTodo = async (payload: { text: string; deadline_utc?: string | null }) => {
  const { data } = await api.post('/api/todos', payload);
  return data as TodoItem;
};

export const updateTodo = async (
  id: number,
  payload: { text?: string; deadline_utc?: string | null; completed?: boolean; time_zone?: string }
) => {
  const { data } = await api.patch(`/api/todos/${id}`, payload);
  return data as TodoItem;
};

export const deleteTodo = async (id: number) => {
  await api.delete(`/api/todos/${id}`);
};

export const sendClaudeTodoMessage = async (
  message: string,
  session_id?: string
): Promise<ClaudeTodoResponse> => {
  const { data } = await api.post('/api/todos/claude/message', { message, session_id });
  return data;
};

// Journal

export type JournalEntry = {
  id: number;
  text: string;
  created_at: string;
};

export type JournalCompletedItem = {
  id: number;
  text: string;
  completed_at_utc: string | null;
};

export type JournalDaySummaryGroup = {
  title: string;
  items: string[];
};

export type JournalDaySummary = {
  groups: JournalDaySummaryGroup[];
};

export type JournalDayResponse = {
  local_date: string;
  time_zone: string;
  status: string;
  entries: JournalEntry[];
  completed_items: JournalCompletedItem[];
  summary?: JournalDaySummary | null;
};

export type JournalWeekDayStatus = {
  local_date: string;
  has_entries: boolean;
  has_summary: boolean;
  completed_count: number;
};

export type JournalWeekResponse = {
  week_start: string;
  week_end: string;
  days: JournalWeekDayStatus[];
};

export const createJournalEntry = async (payload: { text: string; time_zone: string }) => {
  const { data } = await api.post('/api/journal/entries', payload);
  return data as JournalEntry;
};

export const fetchJournalDay = async (
  localDate: string,
  timeZone: string
): Promise<JournalDayResponse> => {
  const { data } = await api.get(`/api/journal/day/${localDate}`, { params: { time_zone: timeZone } });
  return data;
};

export const fetchJournalWeek = async (
  weekStart: string,
  timeZone: string
): Promise<JournalWeekResponse> => {
  const { data } = await api.get('/api/journal/week', { params: { week_start: weekStart, time_zone: timeZone } });
  return data;
};

export type MonetChatResponse = {
  session_id: string;
  reply: string;
  nutrition_entries: Array<{
    ingredient_id?: number;
    recipe_id?: number;
    food_name: string;
    quantity: number;
    unit: string;
    status: string;
    created?: boolean;
  }>;
  todo_items: TodoItem[];
  tools_used: string[];
};

export const sendMonetMessage = async (payload: {
  message: string;
  session_id?: string;
  window_days?: number;
  time_zone?: string;
}): Promise<MonetChatResponse> => {
  const { data } = await api.post('/api/assistant/monet-message', payload);
  return data;
};

export type ScalingRule = {
  slug: string;
  label: string;
  description?: string | null;
  type: 'catalog' | 'manual';
  owner_user_id?: number | null;
  active: boolean;
  multipliers: Record<string, number>;
};

export type ScalingRuleList = {
  rules: ScalingRule[];
  manual_rule_slug?: string | null;
};

export const fetchScalingRules = async (): Promise<ScalingRuleList> => {
  const { data } = await api.get('/api/user/scaling-rules');
  return data;
};

export const enableScalingRule = async (slug: string) => {
  await api.post(`/api/user/scaling-rules/${slug}`);
};

export const disableScalingRule = async (slug: string) => {
  await api.delete(`/api/user/scaling-rules/${slug}`);
};

export type UserProfileData = {
  date_of_birth?: string | null;
  sex?: string | null;
  height_cm?: number | null;
  current_weight_kg?: number | null;
  preferred_units?: 'metric' | 'imperial';
  daily_energy_delta_kcal?: number;
};

export type MeasurementEntry = {
  measured_at: string;
  weight_kg: number;
};

export type DailyEnergySummary = {
  metric_date: string;
  active_kcal?: number | null;
  bmr_kcal?: number | null;
  total_kcal?: number | null;
  source?: string | null;
};

export type UserProfileResponse = {
  profile: UserProfileData;
  measurements: MeasurementEntry[];
  latest_energy?: DailyEnergySummary | null;
  goals: NutritionGoal[];
  scaling_rules: ScalingRuleList;
};

export const fetchUserProfile = async (): Promise<UserProfileResponse> => {
  const { data } = await api.get('/api/user/profile');
  return data;
};

export const updateUserProfile = async (payload: UserProfileData): Promise<UserProfileResponse> => {
  const { data } = await api.put('/api/user/profile', payload);
  return data;
};
