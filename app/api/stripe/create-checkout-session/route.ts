import { NextResponse } from 'next/server';
import { z } from 'zod';

import { UnauthorizedError, requireAuthedUser } from '@/lib/auth';
import { getStripeClient, getPriceId, getProProductId } from '@/lib/stripe';
import { getSupabaseServiceRoleClient } from '@/lib/supabase';

const bodySchema = z
  .object({
    plan: z.enum(['monthly', 'yearly']).optional(),
    priceId: z.string().optional(),
    successUrl: z.string().url(),
    cancelUrl: z.string().url()
  })
  .refine((value) => value.priceId || value.plan, {
    message: 'plan or priceId is required'
  });

export async function POST(request: Request) {
  try {
    const user = await requireAuthedUser();
    const body = await request.json();
    const parsed = bodySchema.parse(body);

    const stripe = getStripeClient();
    const supabase = getSupabaseServiceRoleClient();

    const priceId = parsed.priceId ?? getPriceId(parsed.plan ?? 'monthly');
    const productId = getProProductId();

    let customerId = await getStripeCustomerId(user.id, supabase);
    if (!customerId) {
      const customer = await stripe.customers.create({
        email: user.email,
        metadata: { userId: user.id }
      });
      customerId = customer.id;
      const { error } = await supabase
        .from('stripe_customers')
        .insert({ user_id: user.id, stripe_customer_id: customerId });
      if (error) throw error;
    }

    const session = await stripe.checkout.sessions.create({
      mode: 'subscription',
      customer: customerId,
      success_url: parsed.successUrl,
      cancel_url: parsed.cancelUrl,
      allow_promotion_codes: true,
      line_items: [{ price: priceId, quantity: 1 }],
      subscription_data: {
        metadata: {
          userId: user.id,
          productId
        }
      },
      metadata: {
        userId: user.id,
        productId
      }
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

async function getStripeCustomerId(userId: string, supabase = getSupabaseServiceRoleClient()) {
  const { data, error } = await supabase
    .from('stripe_customers')
    .select('stripe_customer_id')
    .eq('user_id', userId)
    .maybeSingle();

  if (error) throw error;
  return data?.stripe_customer_id ?? null;
}
