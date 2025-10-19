import cors from 'cors';
import express, { type Request as ExpressRequest } from 'express';
import { createHmac, randomUUID, timingSafeEqual } from 'node:crypto';

import { asyncHandler, handleError } from '../../shared/http';
import { logger } from '../../shared/logger';
import { healthHandler, requestLogger } from '../../shared/middleware';
import { writeRawPayload } from '../../shared/gcs';
import { supabaseServiceRole } from '../../shared/supabase';
import { requireEnv } from '../../shared/env';
import { processProviderPayload } from '../../jobs/src/ingest';
import { getProviderHandler, upsertRawEvent } from '../../../lib/providers/manager';
import { findUserByExternalId } from '../../../lib/providers/lookup';
import { isSubscriptionActive } from '../../../lib/billing';
import { getStripeClient } from '../../../lib/stripe';
import type Stripe from 'stripe';

const app = express();
const port = process.env.PORT ?? '8080';

app.use(cors());
app.use(requestLogger());

const jsonParser = express.json({
  verify: (req: any, _res, buf) => {
    req.rawBody = buf.toString();
  }
});

const rawParser = express.raw({
  type: '*/*',
  verify: (req: any, _res, buf) => {
    req.rawBody = buf;
  }
});

app.use((req, res, next) => {
  if (req.path === '/stripe') {
    return rawParser(req, res, next);
  }
  return jsonParser(req, res, next);
});

const garminHandler = getProviderHandler('garmin');
const withingsHandler = getProviderHandler('withings');

function toFetchRequest(req: ExpressRequest): Request {
  const headers = new Headers();
  for (const [key, value] of Object.entries(req.headers)) {
    if (Array.isArray(value)) {
      value.forEach((v) => headers.append(key, v));
    } else if (value !== undefined) {
      headers.set(key, value);
    }
  }
  const raw = (req as any).rawBody;
  const body = typeof raw === 'string' || raw instanceof Buffer ? raw : JSON.stringify(req.body);
  return new Request(`https://webhooks.internal${req.originalUrl}`, {
    method: req.method,
    headers,
    body: typeof body === 'string' ? body : body.toString()
  });
}

function verifyHmacSignature(body: Buffer | string, secret: string, signature?: string | string[]) {
  if (!secret) return false;
  if (!signature) return false;

  const provided = Array.isArray(signature) ? signature[0] : signature;
  if (!provided) return false;

  const normalizedBody = Buffer.isBuffer(body) ? body : Buffer.from(body);

  const expectedHex = createHmac('sha256', secret).update(normalizedBody).digest('hex');
  const expectedBase64 = createHmac('sha256', secret).update(normalizedBody).digest('base64');

  try {
    const providedBufferHex = Buffer.from(provided, 'hex');
    const expectedBufferHex = Buffer.from(expectedHex, 'hex');
    if (providedBufferHex.length === expectedBufferHex.length && timingSafeEqual(providedBufferHex, expectedBufferHex)) {
      return true;
    }
  } catch {
    // ignore hex parse errors
  }

  try {
    const providedBuffer = Buffer.from(provided, 'base64');
    const expectedBuffer = Buffer.from(expectedBase64, 'base64');
    if (providedBuffer.length === expectedBuffer.length && timingSafeEqual(providedBuffer, expectedBuffer)) {
      return true;
    }
  } catch {
    // ignore base64 parse errors
  }

  return false;
}

app.get('/health', healthHandler('webhooks'));

app.post(
  '/garmin',
  asyncHandler(async (req, res) => {
    const secret = process.env.GARMIN_WEBHOOK_SECRET;
    if (secret) {
      const rawBody = (req as any).rawBody ?? JSON.stringify(req.body);
      const signature = req.headers['x-garmin-signature'] ?? req.headers['x-garmin-signature-256'];
      if (!verifyHmacSignature(rawBody, secret, signature)) {
        logger.warn({ event: 'garmin.signature_failed' }, 'garmin webhook signature verification failed');
        res.status(401).json({ error: 'Invalid signature' });
        return;
      }
    }

    const externalUserId =
      req.headers['x-garmin-user-id']?.toString() ??
      (req.body?.data?.userId ?? req.body?.data?.userIdHash);

    if (!externalUserId) {
      res.status(400).json({ error: 'Missing Garmin user id' });
      return;
    }

    const userId = await findUserByExternalId('garmin', externalUserId);
    if (!userId) {
      res.status(202).json({ status: 'ignored', reason: 'user not linked yet' });
      return;
    }

    const rawObject = await writeRawPayload('garmin/raw', randomUUID(), (req as any).rawBody ?? JSON.stringify(req.body));
    const payload = await garminHandler.parseWebhook(toFetchRequest(req));
    logger.info({ userId, rawObject }, 'stored garmin raw payload');

    await upsertRawEvent(payload, userId);
    await processProviderPayload(userId, payload);

    // TODO: enqueue recompute job via Pub/Sub when event merits recalculation.
    res.json({ status: 'ok' });
  })
);

app.post(
  '/withings',
  asyncHandler(async (req, res) => {
    const secret = process.env.WITHINGS_WEBHOOK_SECRET;
    if (secret) {
      const rawBody = (req as any).rawBody ?? JSON.stringify(req.body);
      const signature = req.headers['x-withings-signature'] ?? req.headers['x-signature'];
      if (!verifyHmacSignature(rawBody, secret, signature)) {
        logger.warn({ event: 'withings.signature_failed' }, 'withings webhook signature verification failed');
        res.status(401).json({ error: 'Invalid signature' });
        return;
      }
    }

    const externalUserId =
      req.headers['x-withings-user-id']?.toString() ??
      req.body?.userid ??
      req.body?.notification?.userid;

    if (!externalUserId) {
      res.status(400).json({ error: 'Missing Withings user id' });
      return;
    }

    const userId = await findUserByExternalId('withings', externalUserId.toString());
    if (!userId) {
      res.status(202).json({ status: 'ignored', reason: 'user not linked yet' });
      return;
    }

    const rawObject = await writeRawPayload('withings/raw', randomUUID(), (req as any).rawBody ?? JSON.stringify(req.body));
    const payload = await withingsHandler.parseWebhook(toFetchRequest(req));
    logger.info({ userId, rawObject }, 'stored withings raw payload');

    await upsertRawEvent(payload, userId);
    await processProviderPayload(userId, payload);

    // TODO: enqueue recompute job via Pub/Sub when event merits recalculation.
    res.json({ status: 'ok' });
  })
);

app.post(
  '/stripe',
  asyncHandler(async (req, res) => {
    const stripe = getStripeClient();
    const endpointSecret = requireEnv('STRIPE_WEBHOOK_SECRET');
    const signature = req.headers['stripe-signature'];

    if (!signature) {
      res.status(400).json({ error: 'Missing Stripe signature' });
      return;
    }

    const rawBody = (req as any).rawBody as Buffer;

    let event: Stripe.Event;
    try {
      event = stripe.webhooks.constructEvent(rawBody, signature, endpointSecret);
    } catch (error) {
      logger.error({ error }, 'stripe signature verification failed');
      res.status(400).json({ error: 'Signature verification failed' });
      return;
    }

    await writeRawPayload('stripe/raw', event.id, rawBody.toString());
    await handleStripeEvent(event);

    res.json({ received: true });
  })
);

export async function handleStripeEvent(event: Stripe.Event) {
  switch (event.type) {
    case 'customer.subscription.created':
    case 'customer.subscription.updated':
    case 'customer.subscription.deleted': {
      const subscription = event.data.object as Stripe.Subscription;
      const userId = subscription.metadata?.userId;
      if (!userId) return;

      const currentPeriodEnd = subscription.current_period_end
        ? new Date(subscription.current_period_end * 1000).toISOString()
        : null;
      const isActive = isSubscriptionActive({
        status: subscription.status,
        current_period_end: currentPeriodEnd
      });

      const payload = {
        user_id: userId,
        stripe_subscription_id: subscription.id,
        status: subscription.status,
        current_period_end: currentPeriodEnd,
        updated_at: new Date().toISOString()
      };

      const { error } = await supabaseServiceRole.from('subscriptions').upsert(payload, {
        onConflict: 'user_id'
      });
      if (error) throw error;

      const { error: ffError } = await supabaseServiceRole.from('feature_flags').upsert(
        {
          user_id: userId,
          key: 'billing-pro',
          enabled: isActive,
          updated_at: new Date().toISOString()
        },
        {
          onConflict: 'user_id,key'
        }
      );
      if (ffError) throw ffError;
      break;
    }
    case 'invoice.paid':
    case 'invoice.payment_failed':
      // TODO: handle invoice events for notifications or retries.
      break;
    default:
      logger.debug({ eventType: event.type }, 'Unhandled Stripe webhook event');
  }
}

app.use((err: unknown, _req: express.Request, res: express.Response, _next: express.NextFunction) => {
  logger.error({ err }, 'Unhandled error in webhooks service');
  handleError(err, res);
});

export function start() {
  app.listen(port, () => {
    logger.info({ port }, 'webhooks service listening');
  });
}

if (require.main === module) {
  start();
}
