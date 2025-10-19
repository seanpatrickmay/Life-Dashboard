// TODO: Expose this redirect via Cloud Run HTTP server.
import crypto from 'node:crypto';

import { garminAuthUrl } from '@/lib/providers/garmin';

export function handleGarminAuthRedirect(request: Request) {
  const redirectUri =
    new URL(request.url).searchParams.get('redirect_uri') ??
    `${process.env.NEXT_PUBLIC_APP_URL ?? 'http://localhost:3000'}/integrations/garmin/callback`;
  const state = crypto.randomUUID();
  const url = garminAuthUrl(redirectUri, state);
  return Response.redirect(url);
}
