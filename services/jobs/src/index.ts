import cors from 'cors';
import express from 'express';

import { asyncHandler, handleError } from '../../shared/http';
import { logger } from '../../shared/logger';
import { healthHandler, requestLogger } from '../../shared/middleware';
import { recomputeRequestSchema, backfillRequestSchema } from '../../shared/schemas';
import { recomputeNightly } from './recompute-nightly';
import { supabaseServiceRole } from '../../shared/supabase';

const app = express();
const port = process.env.PORT ?? '8080';

app.use(cors());
app.use(express.json());
app.use(requestLogger());

app.get('/health', healthHandler('jobs'));

app.post(
  '/recompute',
  asyncHandler(async (req, res) => {
    const { date } = recomputeRequestSchema.parse({
      date: Array.isArray(req.query.date) ? req.query.date[0] : req.query.date
    });
    logger.info({ date }, 'recompute request received');

    if (date) {
      await recomputeSingleDay(date as string);
    } else {
      await recomputeNightly();
    }

    res.json({ status: 'queued' });
  })
);

app.post(
  '/backfill',
  asyncHandler(async (req, res) => {
    const parsed = backfillRequestSchema.parse({
      provider: Array.isArray(req.query.provider) ? req.query.provider[0] : req.query.provider,
      days: Array.isArray(req.query.days) ? req.query.days[0] : req.query.days,
      userId: req.body?.userId ?? (Array.isArray(req.query.userId) ? req.query.userId[0] : req.query.userId)
    });
    const { provider, days, userId } = parsed;
    logger.info({ provider, days, userId }, 'backfill request received');

    // TODO: Implement provider-specific historical fetch from Garmin/Withings APIs.
    // For now we mark the job as accepted.
    res.json({ status: 'accepted', provider, days, userId });
  })
);

async function recomputeSingleDay(date: string) {
  const supabase = supabaseServiceRole;
  const { data, error } = await supabase
    .from('daily_metrics')
    .select('*')
    .eq('metric_date', date);
  if (error) throw error;
  if (!data) return;

  // TODO: refine recompute to target single-day readiness + aggregates per user.
  await recomputeNightly();
}

app.use((err: unknown, _req: express.Request, res: express.Response, _next: express.NextFunction) => {
  logger.error({ err }, 'Unhandled error in jobs service');
  handleError(err, res);
});

export function start() {
  app.listen(port, () => {
    logger.info({ port }, 'jobs service listening');
  });
}

if (require.main === module) {
  start();
}
