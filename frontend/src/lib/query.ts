import { QueryClient } from '@tanstack/react-query';

/** One client for the app. Immutable dataset marts are cached aggressively; job state opts into polling. */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      gcTime: 10 * 60_000,
      retry: 1,
      retryDelay: (attempt) => Math.min(750 * 2 ** attempt, 4000),
      refetchOnWindowFocus: false,
    },
    mutations: { retry: 0 },
  },
});
