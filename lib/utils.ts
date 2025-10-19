import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function assertEnv(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(`Missing required environment variable: ${name}`);
  }
  return value;
}

export function isServiceRole(headers: Headers): boolean {
  return headers.get('x-service-role-key') === process.env.SUPABASE_SERVICE_ROLE_KEY;
}

export const ONE_DAY = 60 * 60 * 24;
