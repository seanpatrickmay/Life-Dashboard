import { getSupabaseServiceRoleClient } from '@/lib/supabase';

export async function findUserByExternalId(provider: string, externalId: string) {
  const client = getSupabaseServiceRoleClient();
  const { data, error } = await client
    .from('connections')
    .select('user_id')
    .eq('provider', provider)
    .eq('external_user_id', externalId)
    .maybeSingle();

  if (error) throw error;
  return data?.user_id ?? null;
}
