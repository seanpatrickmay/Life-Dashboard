import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const USER_ID = '00000000-0000-0000-0000-000000000001';

let subscriptionData: any = { status: 'active', current_period_end: null };
let insightsCountValue = 0;

const subscriptionsChain = {
  select: () => subscriptionsChain,
  eq: () => subscriptionsChain,
  order: () => subscriptionsChain,
  limit: () => subscriptionsChain,
  maybeSingle: async () => ({ data: subscriptionData, error: null })
};

const insightsChain: any = {
  select: () => insightsChain,
  eq: () => insightsChain,
  gte: () => Promise.resolve({ count: insightsCountValue, error: null })
};

vi.mock('@/lib/supabase', () => ({
  getSupabaseServerClient: () => ({
    from: (table: string) => {
      if (table === 'subscriptions') return subscriptionsChain;
      if (table === 'insights') return insightsChain;
      throw new Error(`Unexpected table ${table}`);
    }
  })
}));

vi.mock('@/lib/auth', () => ({
  requireAuthedUser: vi.fn().mockResolvedValue({ id: USER_ID, email: 'test@example.com' })
}));

describe('LLM insights gating', () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    subscriptionData = { status: 'active', current_period_end: null };
    insightsCountValue = 0;
    fetchSpy = vi.spyOn(global, 'fetch').mockResolvedValue({
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      text: async () => JSON.stringify({ data: [] })
    } as Response);
  });

  afterEach(() => {
    fetchSpy.mockRestore();
  });

  it('allows premium subscribers to request insights', async () => {
    const mod = await import('@/app/api/llm/insights/route');

    const request = new Request('http://localhost/api/llm/insights', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: USER_ID, from: '2024-01-01', to: '2024-01-07', topics: ['daily'] })
    });

    const response = await mod.POST(request);
    expect(response.status).toBe(200);
    expect(fetchSpy).toHaveBeenCalled();
  });

  it('allows cancelled subscribers until period end', async () => {
    subscriptionData = {
      status: 'canceled',
      current_period_end: new Date(Date.now() + 86400 * 1000).toISOString()
    };

    const mod = await import('@/app/api/llm/insights/route');
    const request = new Request('http://localhost/api/llm/insights', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: USER_ID, from: '2024-01-01', to: '2024-01-07', topics: ['daily'] })
    });

    const response = await mod.POST(request);
    expect(response.status).toBe(200);
    expect(fetchSpy).toHaveBeenCalled();
  });

  it('blocks free users over monthly insight quota', async () => {
    subscriptionData = null;
    insightsCountValue = 5;

    const mod = await import('@/app/api/llm/insights/route');
    const request = new Request('http://localhost/api/llm/insights', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: USER_ID, from: '2024-01-01', to: '2024-01-07', topics: ['daily'] })
    });

    const response = await mod.POST(request);
    expect(response.status).toBe(402);
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});
