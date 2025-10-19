export type ProviderName = 'garmin' | 'withings';

export type ProviderStatus = 'connected' | 'paused' | 'revoked' | 'disconnected' | 'error';

export interface ProviderConnection {
  provider: ProviderName;
  status: ProviderStatus;
  latestSyncAt?: string;
  scopes?: string[];
}

export interface ProviderWebhookPayload {
  provider: ProviderName;
  event: string;
  receivedAt: string;
  data: unknown;
}

export interface NormalizedDailyMetric {
  date: string;
  energyBurnedKcal?: number;
  steps?: number;
  sleepMinutesTotal?: number;
  sleepEfficiency?: number;
  restingHr?: number;
  hrvRmssd?: number;
  stressScore?: number;
  trainingLoad?: number;
  weightKg?: number;
  bodyFatPct?: number;
}

export interface NormalizedActivity {
  sourceId?: string;
  name?: string;
  sportType?: string;
  startTime: string;
  durationSeconds?: number;
  distanceMeters?: number;
  avgHr?: number;
  maxHr?: number;
  trimp?: number;
  tssEst?: number;
  calories?: number;
  raw?: unknown;
}

export interface BackfillOptions {
  userId: string;
  accessToken: string;
  refreshToken?: string;
  days: number;
}

export interface BackfillResult {
  importedDays: number;
  rawEventsStored: number;
  metricsUpserted: number;
  activitiesUpserted: number;
}
