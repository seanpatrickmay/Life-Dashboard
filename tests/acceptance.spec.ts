import { afterEach, describe, expect, it, vi } from 'vitest';

import { createNutritionEntryAction } from '@/app/nutrition/actions';
import { generateInsights } from '@/lib/llm/client';
import { createCheckoutSession } from '@/lib/stripe';

vi.mock('next/cache', () => ({ revalidatePath: vi.fn() }));

const mockInsert = vi.fn().mockResolvedValue({ error: null });
const mockUpdate = vi.fn().mockResolvedValue({ error: null });
const mockDelete = vi.fn().mockResolvedValue({ error: null });
const mockUpsert = vi.fn().mockResolvedValue({ error: null });

vi.mock('@/lib/auth', async () => {
  const actual = await vi.importActual<typeof import('@/lib/auth')>('@/lib/auth');
  return {
    ...actual,
    requireAuthedUser: vi.fn().mockResolvedValue({ id: 'user-1' }),
    withRLS: async (cb: any) => {
      const chain: any = {
        eq: () => chain,
        gte: () => chain,
        lt: () => chain,
        order: () => chain,
        select: () => chain,
        maybeSingle: async () => ({ data: null }),
        insert: (...args: any[]) => {
          mockInsert(...args);
          return chain;
        },
        update: (...args: any[]) => {
          mockUpdate(...args);
          return chain;
        },
        delete: (...args: any[]) => {
          mockDelete(...args);
          return chain;
        },
        upsert: (...args: any[]) => {
          mockUpsert(...args);
          return chain;
        }
      };

      await cb({
        from: () => chain
      });
    }
  };
});

vi.mock('@/lib/supabase', () => ({
  getSupabaseServerClient: () => ({
    from: () => ({ insert: mockInsert, upsert: mockUpsert, eq: () => ({ insert: mockInsert }) })
  })
}));

describe('Acceptance flows (stubbed)', () => {
  afterEach(() => {
    mockInsert.mockClear();
    mockUpdate.mockClear();
    mockDelete.mockClear();
    mockUpsert.mockClear();
  });

  it('allows adding a nutrition entry via server action', async () => {
    await createNutritionEntryAction({
      timestamp: new Date('2024-01-01T12:00:00Z'),
      foodName: 'Test Meal',
      calories: 420,
      protein_g: 30,
      carbs_g: 50,
      fat_g: 10
    });

    expect(mockInsert).toHaveBeenCalledWith(
      expect.objectContaining({
        food_name: 'Test Meal',
        calories: 420
      })
    );
  });

  it('generates insights through the LLM proxy', async () => {
    const fetchSpy = vi.spyOn(global, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({ data: [{ topic: 'daily', cached: false, summary: 'All good' }] })
    } as Response);

    const data = await generateInsights({
      userId: 'user-1',
      from: '2024-01-01',
      to: '2024-01-07',
      topics: ['daily']
    });

    expect(fetchSpy).toHaveBeenCalledWith(
      '/api/llm/insights',
      expect.objectContaining({ method: 'POST' })
    );
    expect(data[0]?.summary).toBe('All good');

    fetchSpy.mockRestore();
  });

  it('creates a Stripe checkout session via API helper', async () => {
    const fetchSpy = vi.spyOn(global, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({ url: 'https://checkout.stripe.com/test' })
    } as Response);

    const url = await createCheckoutSession({
      plan: 'monthly',
      successUrl: 'https://app/success',
      cancelUrl: 'https://app/cancel'
    });
    expect(url).toContain('stripe.com');

    fetchSpy.mockRestore();
  });
});
