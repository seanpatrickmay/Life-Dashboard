import { createLogger } from '@/lib/observability/logger';

export const logger = createLogger({ service: process.env.SERVICE_NAME ?? 'life-dashboard' });
