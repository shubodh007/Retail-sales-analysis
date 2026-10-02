import { QueryClient } from '@tanstack/react-query';

/** One client for the app. No per-page clients. */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});
