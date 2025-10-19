import { createServerComponentClient } from '@supabase/auth-helpers-nextjs';
import { createClient, type SupabaseClient } from '@supabase/supabase-js';
import { cookies } from 'next/headers';

import { assertEnv } from '@/lib/utils';

const SUPABASE_URL = assertEnv('NEXT_PUBLIC_SUPABASE_URL');
const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? assertEnv('SUPABASE_ANON_KEY');

export function getSupabaseServerClient(): SupabaseClient {
  return createServerComponentClient(
    { cookies },
    {
      supabaseUrl: SUPABASE_URL,
      supabaseKey: SUPABASE_ANON_KEY
    }
  );
}

export function getSupabaseServiceRoleClient() {
  return createClient(SUPABASE_URL, assertEnv('SUPABASE_SERVICE_ROLE_KEY'), {
    auth: {
      autoRefreshToken: false,
      persistSession: false
    }
  });
}

let browserClient: SupabaseClient | null = null;

export function getSupabaseBrowserClient(): SupabaseClient {
  if (typeof window === 'undefined') {
    throw new Error('getSupabaseBrowserClient must be called in the browser');
  }
  if (!browserClient) {
    browserClient = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
      auth: {
        persistSession: true
      }
    });
  }
  return browserClient;
}
