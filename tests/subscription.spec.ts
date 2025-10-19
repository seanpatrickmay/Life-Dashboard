import { describe, expect, it, vi, beforeEach } from 'vitest';

import type Stripe from 'stripe';

import { isSubscriptionActive } from '@/lib/billing';

vi.mock('cors', () => ({
  default: () => (_req: unknown, _res: unknown, next: () => void) => next()
}));

vi.mock('express', () => {
  const handlers: Record<string, any> = {};
  const app = {
    use: vi.fn(),
    get: vi.fn((path: string, handler: any) => {
      handlers[path] = handler;
      return app;
    }),
    post: vi.fn((path: string, ...fns: any[]) => {
      handlers[path] = fns;
      return app;
    }),
    listen: vi.fn()
  };

  const express = () => app;
  express.json = () => (_req: unknown, _res: unknown, next: () => void) => next();
  express.raw = () => (_req: unknown, _res: unknown, next: () => void) => next();

  return { default: express };
});

vi.mock('pino', () => ({
  default: () => ({
    info: vi.fn(),
    error: vi.fn(),
    debug: vi.fn(),
    child: vi.fn(() => ({
      info: vi.fn(),
      error: vi.fn(),
      debug: vi.fn()
    }))
  })
}));

vi.mock('@/services/shared/gcs', () => ({
  writeRawPayload: vi.fn().mockResolvedValue('mock://gcs-object')
}));

const USER_ID = '00000000-0000-0000-0000-000000000001';

const subscriptions: any[] = [];
const featureFlags: any[] = [];

vi.mock('@/services/shared/supabase', () => ({
  supabaseServiceRole: {
    from: (table: string) => {
      return {
        upsert: (payload: any) => {
          if (table === 'subscriptions') {
            subscriptions.push(payload);
          }
          if (table === 'feature_flags') {
            featureFlags.push(payload);
          }
          return { error: null };
        }
      };
    }
  }
}));

describe('Stripe subscription webhooks', () => {
  beforeEach(() => {
    subscriptions.length = 0;
    featureFlags.length = 0;
  });

  it('creates subscription and enables premium features on update', async () => {
    const { handleStripeEvent } = await import('@/services/webhooks/src/index');

    const event = {
      type: 'customer.subscription.updated',
      data: {
        object: {
          id: 'sub_123',
          metadata: { userId: USER_ID },
          status: 'active',
          current_period_end: Math.floor(Date.now() / 1000) + 3600
        }
      }
    } as Stripe.Event;

    await handleStripeEvent(event);

    const latestSubscription = subscriptions.at(-1);
    expect(latestSubscription).toMatchObject({ user_id: USER_ID, stripe_subscription_id: 'sub_123' });
    expect(isSubscriptionActive(latestSubscription)).toBe(true);
    expect(featureFlags.at(-1)).toMatchObject({ enabled: true });
  });

  it('keeps features until period end after cancel, then disables', async () => {
    const { handleStripeEvent } = await import('@/services/webhooks/src/index');

    const futureCancelEvent = {
      type: 'customer.subscription.deleted',
      data: {
        object: {
          id: 'sub_123',
          metadata: { userId: USER_ID },
          status: 'canceled',
          current_period_end: Math.floor(Date.now() / 1000) + 86400
        }
      }
    } as Stripe.Event;

    await handleStripeEvent(futureCancelEvent);
    expect(featureFlags.at(-1)).toMatchObject({ enabled: true });
    expect(isSubscriptionActive(subscriptions.at(-1))).toBe(true);

    const pastCancelEvent = {
      type: 'customer.subscription.deleted',
      data: {
        object: {
          id: 'sub_123',
          metadata: { userId: USER_ID },
          status: 'canceled',
          current_period_end: Math.floor(Date.now() / 1000) - 86400
        }
      }
    } as Stripe.Event;

    await handleStripeEvent(pastCancelEvent);
    expect(featureFlags.at(-1)).toMatchObject({ enabled: false });
    expect(isSubscriptionActive(subscriptions.at(-1))).toBe(false);
  });
});
