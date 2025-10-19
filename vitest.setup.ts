import '@testing-library/jest-dom';
import { vi } from 'vitest';

vi.mock('react', async () => {
  const actual = await vi.importActual<typeof import('react')>('react');
  return {
    ...actual,
    cache: actual.cache ?? ((fn: unknown) => fn)
  };
});

process.env.NEXT_PUBLIC_SUPABASE_URL ??= 'https://example.supabase.co';
process.env.SUPABASE_ANON_KEY ??= 'anon-key';
process.env.SUPABASE_SERVICE_ROLE_KEY ??= 'service-role-key';
process.env.STRIPE_SECRET_KEY ??= 'sk_test_123';
process.env.STRIPE_WEBHOOK_SECRET ??= 'whsec_test';
process.env.STRIPE_PRO_PRODUCT_ID ??= 'prod_test';
process.env.STRIPE_PRICE_PRO_MONTH_ID ??= 'price_monthly_test';
process.env.STRIPE_PRICE_PRO_YEAR_ID ??= 'price_yearly_test';
process.env.NEXT_PUBLIC_FREE_INSIGHTS_LIMIT ??= '5';
process.env.LLM_SERVICE_URL ??= 'https://llm.local';
process.env.JOBS_SERVICE_URL ??= 'https://jobs.local';
