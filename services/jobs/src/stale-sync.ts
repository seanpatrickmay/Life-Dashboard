// TODO: Trigger via Cloud Scheduler -> Pub/Sub when deployed to Cloud Run.
import { supabaseServiceRole } from '../../shared/supabase';
import { logger } from '../../shared/logger';

export async function sendStaleSyncAlerts() {
  const supabase = supabaseServiceRole;
  const threshold = new Date(Date.now() - 48 * 60 * 60 * 1000).toISOString();
  const { data, error } = await supabase
    .from('connections')
    .select('user_id, provider, latest_sync_at')
    .or(`latest_sync_at.is.null,latest_sync_at.lt.${threshold}`)
    .eq('status', 'connected');

  if (error) throw error;
  if (!data?.length) return;

  for (const connection of data) {
    logger.warn({ connection }, 'Stale provider connection detected');
    // TODO: Integrate transactional email or notification pipeline.
  }
}
