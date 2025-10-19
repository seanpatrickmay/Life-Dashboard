'use client';

export interface ToastOptions {
  title: string;
  description?: string;
  variant?: 'default' | 'destructive';
}

export function toast(_options: ToastOptions) {
  // TODO: integrate a real toast system (e.g., sonner or @radix-ui/react-toast).
  if (process.env.NODE_ENV !== 'production') {
    console.log('[toast]', _options);
  }
}
