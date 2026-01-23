import axios from 'axios';
import { isGuestMode } from '../demo/guest/guestMode';
import {
  clearGuestState,
  createGuestJournalEntry,
  createGuestTodo,
  deleteGuestNutritionEntry,
  deleteGuestTodo,
  getGuestAuthMe,
  getGuestClaudeChatResponse,
  getGuestClaudeTodoResponse,
  getGuestGarminStatus,
  getGuestInsight,
  getGuestJournalDay,
  getGuestJournalWeek,
  getGuestMetricsOverview,
  getGuestMonetChatResponse,
  getGuestNutritionDailySummary,
  getGuestNutritionGoals,
  getGuestNutritionHistory,
  getGuestNutritionMenu,
  getGuestReadinessSummary,
  getGuestRefreshStatus,
  getGuestSceneTime,
  getGuestTodos,
  getGuestUserProfile,
  updateGuestNutritionEntry,
  updateGuestNutritionGoal,
  updateGuestTodo,
  updateGuestUserProfile
} from '../demo/guest/guestStore';

const resolveApiBaseUrl = () => {
  const envBase = import.meta.env.VITE_API_BASE_URL;
  if (envBase) {
    return envBase;
  }
  if (typeof window === 'undefined') {
    return 'http://localhost:8000';
  }
  const { hostname, origin } = window.location;
  if (hostname === 'localhost' || hostname === '127.0.0.1') {
    return 'http://localhost:8000';
  }
  return origin;
};

const baseURL = resolveApiBaseUrl();

export const getApiBaseUrl = () => baseURL;

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
  if (isGuestMode()) {
    return getGuestAuthMe();
  }
  const { data } = await api.get('/api/auth/me');
  return data;
};

export const logout = async (): Promise<void> => {
  if (isGuestMode()) {
    clearGuestState();
    return;
  }
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
  if (isGuestMode()) {
    return getGuestGarminStatus();
  }
  const { data } = await api.get('/api/garmin/status');
  return data;
};

export const connectGarmin = async (payload: GarminConnectPayload): Promise<GarminConnectResponse> => {
  if (isGuestMode()) {
    const status = getGuestGarminStatus();
    return {
      connected: status.connected,
      garmin_email: status.garmin_email ?? 'demo.garmin@life-dashboard.demo',
      connected_at: status.connected_at ?? new Date().toISOString(),
      requires_reauth: status.requires_reauth
    };
  }
  const { data } = await api.post('/api/garmin/connect', payload);
  return data;
};

export const reauthGarmin = async (): Promise<GarminStatusResponse> => {
  if (isGuestMode()) {
    return getGuestGarminStatus();
  }
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
  if (isGuestMode()) {
    return getGuestInsight();
  }
  const { data } = await api.get('/api/insights/daily');
  return data;
};

export const fetchMetricsOverview = async (rangeDays = 7): Promise<MetricsOverview> => {
  if (isGuestMode()) {
    return getGuestMetricsOverview(rangeDays);
  }
  const { data } = await api.get('/api/metrics/overview', { params: { range_days: rangeDays } });
  return data;
};

export const fetchReadinessSummary = async (): Promise<ReadinessMetricsSummary> => {
  if (isGuestMode()) {
    return getGuestReadinessSummary();
  }
  const { data } = await api.get('/api/metrics/readiness-summary');
  return data;
};

export const fetchSceneTime = async (): Promise<SceneTimeResponse> => {
  if (isGuestMode()) {
    return getGuestSceneTime();
  }
  const { data } = await api.get('/api/time');
  return data;
};

export const triggerVisitRefresh = async (): Promise<RefreshStatusResponse> => {
  if (isGuestMode()) {
    return getGuestRefreshStatus();
  }
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
  if (isGuestMode()) {
    return getGuestNutritionMenu(day);
  }
  const { data } = await api.get('/api/nutrition/intake/menu', { params: { day } });
  return data;
};

export const updateNutritionIntake = async (
  intakeId: number,
  payload: { quantity: number; unit: string }
) => {
  if (isGuestMode()) {
    return updateGuestNutritionEntry(intakeId, payload);
  }
  const { data } = await api.patch(`/api/nutrition/intake/${intakeId}`, payload);
  return data;
};

export const deleteNutritionIntake = async (intakeId: number) => {
  if (isGuestMode()) {
    deleteGuestNutritionEntry(intakeId);
    return;
  }
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
  if (isGuestMode()) {
    return getGuestNutritionGoals();
  }
  const { data } = await api.get('/api/nutrition/goals');
  return data;
};

export const updateNutritionGoal = async (slug: string, goal: number) => {
  if (isGuestMode()) {
    return updateGuestNutritionGoal(slug, goal);
  }
  const { data } = await api.put(`/api/nutrition/goals/${slug}`, { goal });
  return data as NutritionGoal;
};

export const logManualIntake = async (payload: { ingredient_id?: number; recipe_id?: number; quantity: number; unit: string; day?: string }) => {
  const { data } = await api.post('/api/nutrition/intake/manual', payload);
  return data as { id?: number } & typeof payload;
};

export const fetchNutritionDailySummary = async (day?: string): Promise<NutritionSummary> => {
  if (isGuestMode()) {
    return getGuestNutritionDailySummary(day);
  }
  const { data } = await api.get('/api/nutrition/intake/daily', { params: { day } });
  return data;
};

export const fetchNutritionHistory = async (days = 14): Promise<NutritionHistory> => {
  if (isGuestMode()) {
    return getGuestNutritionHistory(days);
  }
  const { data } = await api.get('/api/nutrition/intake/history', { params: { days } });
  return data;
};

export const sendClaudeMessage = async (message: string, session_id?: string): Promise<ClaudeChatResponse> => {
  if (isGuestMode()) {
    return getGuestClaudeChatResponse({ message, session_id });
  }
  const { data } = await api.post('/api/nutrition/claude/message', { message, session_id });
  return data;
};

// Todos

export type TodoItem = {
  id: number;
  text: string;
  completed: boolean;
  deadline_utc: string | null;
  deadline_is_date_only: boolean;
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
  if (isGuestMode()) {
    return getGuestTodos();
  }
  const { data } = await api.get('/api/todos', { params: { time_zone } });
  return data;
};

export const createTodo = async (payload: {
  text: string;
  deadline_utc?: string | null;
  deadline_is_date_only?: boolean;
  time_zone?: string;
}) => {
  if (isGuestMode()) {
    return createGuestTodo(payload);
  }
  const { data } = await api.post('/api/todos', payload);
  return data as TodoItem;
};

export const updateTodo = async (
  id: number,
  payload: {
    text?: string;
    deadline_utc?: string | null;
    deadline_is_date_only?: boolean;
    completed?: boolean;
    time_zone?: string;
  }
) => {
  if (isGuestMode()) {
    return updateGuestTodo(id, payload);
  }
  const { data } = await api.patch(`/api/todos/${id}`, payload);
  return data as TodoItem;
};

export const deleteTodo = async (id: number) => {
  if (isGuestMode()) {
    deleteGuestTodo(id);
    return;
  }
  await api.delete(`/api/todos/${id}`);
};

export const sendClaudeTodoMessage = async (
  message: string,
  session_id?: string
): Promise<ClaudeTodoResponse> => {
  if (isGuestMode()) {
    return getGuestClaudeTodoResponse({ message, session_id });
  }
  const { data } = await api.post('/api/todos/claude/message', { message, session_id });
  return data;
};

// Calendar

export type CalendarStatus = {
  connected: boolean;
  account_email: string | null;
  connected_at: string | null;
  last_sync_at: string | null;
  requires_reauth: boolean;
};

export type CalendarSummary = {
  google_id: string;
  summary: string;
  selected: boolean;
  primary: boolean;
  is_life_dashboard: boolean;
  color_id?: string | null;
  time_zone?: string | null;
};

export type CalendarListResponse = {
  calendars: CalendarSummary[];
};

export type CalendarEvent = {
  id: number;
  calendar_google_id: string;
  calendar_summary: string;
  calendar_primary: boolean;
  calendar_is_life_dashboard: boolean;
  google_event_id: string;
  recurring_event_id?: string | null;
  ical_uid?: string | null;
  summary?: string | null;
  description?: string | null;
  location?: string | null;
  start_time: string | null;
  end_time: string | null;
  is_all_day: boolean;
  status?: string | null;
  visibility?: string | null;
  transparency?: string | null;
  hangout_link?: string | null;
  conference_link?: string | null;
  organizer?: Record<string, unknown> | null;
  attendees?: Array<Record<string, unknown>> | null;
};

export type CalendarEventsResponse = {
  events: CalendarEvent[];
};

export const fetchCalendarStatus = async (): Promise<CalendarStatus> => {
  if (isGuestMode()) {
    return {
      connected: false,
      account_email: null,
      connected_at: null,
      last_sync_at: null,
      requires_reauth: false
    };
  }
  const { data } = await api.get('/api/calendar/status');
  return data;
};

export const fetchCalendars = async (): Promise<CalendarListResponse> => {
  if (isGuestMode()) {
    return { calendars: [] };
  }
  const { data } = await api.get('/api/calendar/calendars');
  return data;
};

export const updateCalendarSelection = async (google_ids: string[]): Promise<CalendarListResponse> => {
  if (isGuestMode()) {
    return { calendars: [] };
  }
  const { data } = await api.post('/api/calendar/calendars/selection', { google_ids });
  return data;
};

export const syncCalendar = async (): Promise<void> => {
  if (isGuestMode()) {
    return;
  }
  await api.post('/api/calendar/sync');
};

export const fetchCalendarEvents = async (start: string, end: string): Promise<CalendarEventsResponse> => {
  if (isGuestMode()) {
    return { events: [] };
  }
  const { data } = await api.get('/api/calendar/events', { params: { start, end } });
  return data;
};

export const updateCalendarEvent = async (
  id: number,
  payload: { summary?: string; start_time?: string; end_time?: string; scope?: string; is_all_day?: boolean }
): Promise<CalendarEvent> => {
  if (isGuestMode()) {
    throw new Error('Calendar editing is unavailable in guest mode.');
  }
  const { data } = await api.patch(`/api/calendar/events/${id}`, payload);
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
  if (isGuestMode()) {
    return createGuestJournalEntry(payload.text);
  }
  const { data } = await api.post('/api/journal/entries', payload);
  return data as JournalEntry;
};

export const fetchJournalDay = async (
  localDate: string,
  timeZone: string
): Promise<JournalDayResponse> => {
  if (isGuestMode()) {
    return getGuestJournalDay(localDate, timeZone);
  }
  const { data } = await api.get(`/api/journal/day/${localDate}`, { params: { time_zone: timeZone } });
  return data;
};

export const fetchJournalWeek = async (
  weekStart: string,
  timeZone: string
): Promise<JournalWeekResponse> => {
  if (isGuestMode()) {
    return getGuestJournalWeek(weekStart, timeZone);
  }
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
  if (isGuestMode()) {
    return getGuestMonetChatResponse(payload);
  }
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
  if (isGuestMode()) {
    return getGuestUserProfile();
  }
  const { data } = await api.get('/api/user/profile');
  return data;
};

export const updateUserProfile = async (payload: UserProfileData): Promise<UserProfileResponse> => {
  if (isGuestMode()) {
    return updateGuestUserProfile(payload);
  }
  const { data } = await api.put('/api/user/profile', payload);
  return data;
};
