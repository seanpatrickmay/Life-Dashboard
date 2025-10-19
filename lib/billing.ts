export const PREMIUM_SUBSCRIPTION_STATUSES = new Set(['trialing', 'active', 'past_due']);

export interface SubscriptionStatusLike {
  status: string | null;
  current_period_end?: string | null;
}

export function isSubscriptionActive(subscription: SubscriptionStatusLike | null | undefined, now = new Date()) {
  if (!subscription?.status) {
    return false;
  }

  if (PREMIUM_SUBSCRIPTION_STATUSES.has(subscription.status)) {
    return true;
  }

  if (subscription.status === 'canceled' && subscription.current_period_end) {
    const end = new Date(subscription.current_period_end);
    return end.getTime() > now.getTime();
  }

  return false;
}
