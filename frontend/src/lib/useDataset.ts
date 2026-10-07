/** Active dataset = newest successfully processed dataset. */
import { useQuery } from '@tanstack/react-query';
import { api } from './api';

export function useActiveDataset() {
  const q = useQuery({
    queryKey: ['datasets'],
    queryFn: api.datasets,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });
  const ready = q.data?.filter((dataset) => dataset.status === 'ready') ?? [];
  return { ...q, dataset: ready[0] ?? null };
}
