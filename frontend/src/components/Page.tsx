/** Shared page furniture: dataset context strip + states. */
import { Link } from 'react-router-dom';
import { Badge, EmptyState, ErrorState, Spinner } from './ui';
import { useActiveDataset } from '../lib/useDataset';
import { formatApiError, type Dataset } from '../lib/api';

export function PageGate({ children }: { children: (id: string, dataset: Dataset) => React.ReactNode }) {
  const { dataset, isPending, isError, error, refetch } = useActiveDataset();
  if (isPending) return <Spinner label="Loading datasets…" />;
  if (isError) return <ErrorState message={formatApiError(error)} onRetry={() => refetch()} />;
  if (!dataset)
    return (
      <EmptyState
        title="No dataset yet"
        hint="Upload a retail CSV in the Data Lab first — these pages show real processed data only."
      />
    );
  return <>{children(dataset.id, dataset)}</>;
}

export function DatasetStrip({
  filename,
  span,
  capabilities,
}: {
  filename: string;
  span: string;
  capabilities?: Record<string, boolean>;
}) {
  return (
    <div className="mb-4 flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-ink/15 pb-3">
      <span className="font-mono text-xs tracking-wider text-fog uppercase">Dataset</span>
      <Link to="/data-lab" className="font-mono text-sm underline decoration-safety underline-offset-4">
        {filename}
      </Link>
      <span className="tnum font-mono text-xs text-fog">{span}</span>
      {capabilities &&
        Object.entries(capabilities).map(([k, v]) => (
          <Badge key={k} tone={v ? 'moss' : 'brass'}>
            {k}
          </Badge>
        ))}
    </div>
  );
}

export function QualityNote({ accepted, quarantined, cancellations }: { accepted: number; quarantined: number; cancellations: number }) {
  return (
    <p className="mt-2 font-mono text-[11px] tracking-wider text-fog uppercase">
      Accepted {accepted.toLocaleString()} · Quarantined {quarantined.toLocaleString()} · Cancellations{' '}
      {cancellations.toLocaleString()} — nothing silently dropped (see Data Lab profile)
    </p>
  );
}
