// TODO: Validate state parameter and exchange for internal user ID before persisting tokens.
import { getSupabaseServiceRoleClient } from '@/lib/supabase';
import { exchangeGarminCode } from '@/lib/providers/garmin';

export async function handleGarminCallback(request: Request) {
  const url = new URL(request.url);
  const code = url.searchParams.get('code');
  const state = url.searchParams.get('state');
  const redirectUri = `${process.env.NEXT_PUBLIC_APP_URL ?? 'http://localhost:3000'}/api/oauth/garmin/callback`;

  if (!code || !state) {
    return new Response(JSON.stringify({ error: 'Missing authorization context' }), {
      status: 400,
      headers: { 'content-type': 'application/json' }
    });
  }

  try {
    const tokens = await exchangeGarminCode(code, redirectUri);
    const supabase = getSupabaseServiceRoleClient();
    const { error } = await supabase.from('connections').upsert(
      {
        user_id: state,
        provider: 'garmin',
        status: 'connected',
        external_user_id: state,
        access_token_encrypted: Buffer.from(tokens.accessToken, 'utf8'),
        refresh_token_encrypted: Buffer.from(tokens.refreshToken, 'utf8'),
        scopes: tokens.scope?.split(' ') ?? [],
        updated_at: new Date().toISOString()
      },
      {
        onConflict: 'user_id,provider'
      }
    );
    if (error) throw error;
  } catch (error) {
    console.error('Garmin callback error', error);
    return new Response(JSON.stringify({ error: (error as Error).message }), {
      status: 400,
      headers: { 'content-type': 'application/json' }
    });
  }

  return new Response(JSON.stringify({ status: 'linked' }), {
    status: 200,
    headers: { 'content-type': 'application/json' }
  });
}
