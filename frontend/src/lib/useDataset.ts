/** Active dataset = most recently uploaded. Data Lab owns switching. */
import { useQuery } from '@tanstack/react-query';
import { api } from './api';

export function useActiveDataset() {
  const q = useQuery({ queryKey: ['datasets'], queryFn: api.datasets });
  return { ...q, dataset: q.data?.[0] ?? null };
}
