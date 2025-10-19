// TODO: Expose this redirect via Cloud Run HTTP server.
import crypto from 'node:crypto';

import { withingsAuthUrl } from '@/lib/providers/withings';

export function handleWithingsAuthRedirect(request: Request) {
  const redirectUri =
    new URL(request.url).searchParams.get('redirect_uri') ??
    `${process.env.NEXT_PUBLIC_APP_URL ?? 'http://localhost:3000'}/integrations/withings/callback`;
  const state = crypto.randomUUID();
  const url = withingsAuthUrl(redirectUri, state);
  return Response.redirect(url);
}
