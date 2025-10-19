import { cache } from 'react';
import type { SupabaseClient } from '@supabase/supabase-js';

import { getSupabaseServerClient, getSupabaseBrowserClient } from '@/lib/supabase';

export const getSession = cache(async () => {
  const supabase = getSupabaseServerClient();
  const {
    data: { session }
  } = await supabase.auth.getSession();
  return session;
});

export const getCurrentUser = cache(async () => {
  const session = await getSession();
  return session?.user ?? null;
});

export async function getBrowserSession() {
  const supabase = getSupabaseBrowserClient();
  const { data } = await supabase.auth.getSession();
  return data.session;
}

export class UnauthorizedError extends Error {
  constructor(message = 'Unauthorized') {
    super(message);
    this.name = 'UnauthorizedError';
  }
}

export async function requireAuthedUser() {
  const session = await getSession();
  if (!session?.user) {
    throw new UnauthorizedError();
  }
  return session.user;
}

export async function withRLS<T>(callback: (client: SupabaseClient) => Promise<T>) {
  const supabase = getSupabaseServerClient();
  return callback(supabase);
}
