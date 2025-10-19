import { NextResponse } from 'next/server';

import { UnauthorizedError, requireAuthedUser } from '@/lib/auth';
import { getStripeClient } from '@/lib/stripe';
import { getSupabaseServiceRoleClient } from '@/lib/supabase';

export async function POST() {
  try {
    const user = await requireAuthedUser();
    const supabase = getSupabaseServiceRoleClient();
    const stripe = getStripeClient();

    const { data, error } = await supabase
      .from('stripe_customers')
      .select('stripe_customer_id')
      .eq('user_id', user.id)
      .maybeSingle();

    if (error) throw error;
    if (!data?.stripe_customer_id) {
      return NextResponse.json({ error: 'Customer not found' }, { status: 404 });
    }

    const session = await stripe.billingPortal.sessions.create({
      customer: data.stripe_customer_id,
      return_url: `${process.env.NEXT_PUBLIC_APP_URL ?? 'http://localhost:3000'}/settings`
    });

    return NextResponse.json({ url: session.url });
  } catch (error) {
    if (error instanceof UnauthorizedError) {
      return NextResponse.json({ error: error.message }, { status: 401 });
    }
    console.error(error);
    return NextResponse.json({ error: (error as Error).message }, { status: 400 });
  }
}
