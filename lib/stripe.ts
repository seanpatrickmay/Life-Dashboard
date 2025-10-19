import Stripe from 'stripe';

import { PREMIUM_SUBSCRIPTION_STATUSES } from '@/lib/billing';
import { assertEnv } from '@/lib/utils';

const STRIPE_PRO_PRODUCT_ID = assertEnv('STRIPE_PRO_PRODUCT_ID');
const STRIPE_PRICE_MONTH = assertEnv('STRIPE_PRICE_PRO_MONTH_ID');
const STRIPE_PRICE_YEAR = assertEnv('STRIPE_PRICE_PRO_YEAR_ID');

let stripeSingleton: Stripe | null = null;

export function getStripeClient() {
  if (!stripeSingleton) {
    stripeSingleton = new Stripe(assertEnv('STRIPE_SECRET_KEY'), {
      apiVersion: '2023-10-16',
      appInfo: {
        name: 'Life Dashboard',
        version: '0.1.0'
      }
    });
  }

  return stripeSingleton;
}

export function getMeteredUsageKey(userId: string, featureCode: string) {
  return `${userId}:${featureCode}`;
}

export function getProProductId() {
  return STRIPE_PRO_PRODUCT_ID;
}

export function getPriceId(plan: 'monthly' | 'yearly' = 'monthly') {
  return plan === 'yearly' ? STRIPE_PRICE_YEAR : STRIPE_PRICE_MONTH;
}

export async function createCheckoutSession({
  plan = 'monthly',
  successUrl,
  cancelUrl
}: {
  plan?: 'monthly' | 'yearly';
  successUrl: string;
  cancelUrl: string;
}) {
  const response = await fetch('/api/stripe/create-checkout-session', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ plan, successUrl, cancelUrl })
  });

  if (!response.ok) {
    throw new Error('Unable to create checkout session');
  }

  const data = (await response.json()) as { url: string };
  return data.url;
}

export async function createPortalSession() {
  const response = await fetch('/api/stripe/create-portal-session', {
    method: 'POST'
  });

  if (!response.ok) {
    throw new Error('Unable to start billing portal');
  }

  const data = (await response.json()) as { url: string };
  return data.url;
}
