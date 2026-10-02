/** Data Lab: upload CSV -> async Spark ingestion (poll) -> dataset registry. */
import { useEffect, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, formatApiError, type DatasetProfile } from '../lib/api';
import { Badge, Button, Card, EmptyState, ErrorState, Spinner, Stat } from '../components/ui';
import { NullBar } from '../components/NullBar';

function UploadCard({ onDone }: { onDone: (id: string) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const doneRef = useRef<string | null>(null);
  const qc = useQueryClient();
  const mutation = useMutation({
    mutationFn: (f: File) => api.upload(f),
    onSuccess: (d) => {
      setJobId(d.id);
      setFile(null);
    },
  });
  const job = useQuery({
    queryKey: ['dataset-status', jobId],
    queryFn: () => api.datasetStatus(jobId!),
    enabled: !!jobId,
    refetchInterval: (q) => {
      const s = q.state.data?.status;
      return s === 'queued' || s === 'processing' ? 3000 : false;
    },
  });
  useEffect(() => {
    if (job.data?.status === 'ready' && doneRef.current !== job.data.id) {
      doneRef.current = job.data.id;
      qc.invalidateQueries({ queryKey: ['datasets'] });
      onDone(job.data.id);
    }
  }, [job.data, qc, onDone]);

  const busy = mutation.isPending || job.data?.status === 'queued' || job.data?.status === 'processing';
  const failed = job.data?.status === 'failed';

  return (
    <Card title="01 / Ingest CSV">
      <div className="flex flex-wrap items-center gap-3">
        <label className="cursor-pointer border border-dashed border-steel px-4 py-2 font-mono text-xs tracking-wider uppercase hover:border-safety focus-within:border-safety">
          <input
            type="file"
            accept=".csv"
            className="sr-only"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
          {file ? file.name : 'Choose .csv file'}
        </label>
        <Button disabled={!file || busy} onClick={() => file && mutation.mutate(file)}>
          {busy ? 'Profiling…' : 'Upload + Profile'}
        </Button>
        {file && <span className="font-mono text-xs text-fog">{(file.size / 1024).toFixed(0)} KB</span>}
      </div>
      {busy && <Spinner label={job.data ? `Spark is profiling your file… (${job.data.status})` : 'Spark is profiling your file…'} />}
      {mutation.isError && <div className="mt-3"><ErrorState message={formatApiError(mutation.error)} /></div>}
      {failed && <div className="mt-3"><ErrorState message={job.data?.error ?? 'processing failed'} /></div>}
      <p className="mt-3 text-xs text-ink/60">
        Schema is auto-detected against the dataset contract. Files failing validation are rejected with reasons —
        never silently coerced. Large files process in the background; you can keep browsing.
      </p>
    </Card>
  );
}

function DatasetList({ selected, onSelect }: { selected: string | null; onSelect: (id: string) => void }) {
  const { data, isPending, isError, error, refetch } = useQuery({ queryKey: ['datasets'], queryFn: api.datasets });
  if (isPending) return <Card title="02 / Registry"><Spinner label="Loading registry…" /></Card>;
  if (isError)
    return (
      <Card title="02 / Registry">
        <ErrorState message={formatApiError(error)} onRetry={() => refetch()} />
      </Card>
    );
  if (!data.length)
    return (
      <Card title="02 / Registry">
        <EmptyState title="No datasets yet" hint="Upload a retail CSV to begin. A deterministic synthetic sample ships in datasets/samples/." />
      </Card>
    );
  return (
    <Card title="02 / Registry">
      <ul className="divide-y divide-ink/10">
        {data.map((d) => (
          <li key={d.id}>
            <button
              onClick={() => onSelect(d.id)}
              className={`flex w-full items-center justify-between gap-3 px-2 py-2 text-left hover:bg-bone/60 ${selected === d.id ? 'bg-bone' : ''}`}
            >
              <span className="truncate font-mono text-sm">{d.filename}</span>
              <span className="flex shrink-0 items-center gap-2">
                <span className="tnum font-mono text-xs text-fog">{d.row_count.toLocaleString()} rows</span>
                <Badge tone={d.status === 'ready' ? 'moss' : 'brass'}>{d.status}</Badge>
              </span>
            </button>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function ProfileView({ id }: { id: string }) {
  const statusQ = useQuery({
    queryKey: ['dataset-status', id],
    queryFn: () => api.datasetStatus(id),
    refetchInterval: (q) => {
      const s = q.state.data?.status;
      return s === 'queued' || s === 'processing' ? 3000 : false;
    },
  });
  const ready = statusQ.data?.status === 'ready';
  const failed = statusQ.data?.status === 'failed';
  const { data, isPending, isError, error, refetch } = useQuery({
    queryKey: ['profile', id],
    queryFn: () => api.profile(id),
    enabled: ready,
  });
  if (statusQ.isPending)
    return (
      <Card title="03 / Profile">
        <Spinner label="Reading status…" />
      </Card>
    );
  if (statusQ.isError)
    return (
      <Card title="03 / Profile">
        <ErrorState message={formatApiError(statusQ.error)} />
      </Card>
    );
  if (failed)
    return (
      <Card title="03 / Profile">
        <ErrorState message={statusQ.data?.error ?? 'dataset processing failed'} />
      </Card>
    );
  if (!ready)
    return (
      <Card title="03 / Profile">
        <Spinner label={`Spark is profiling this dataset… (${statusQ.data?.status})`} />
      </Card>
    );
  if (isPending)
    return (
      <Card title="03 / Profile">
        <Spinner label="Reading profile…" />
      </Card>
    );
  if (isError)
    return (
      <Card title="03 / Profile">
        <ErrorState message={formatApiError(error)} onRetry={() => refetch()} />
      </Card>
    );
  const p: DatasetProfile = data;
  const prof = p.profile;
  return (
    <Card
      title="03 / Profile"
      aside={<Badge tone="moss">{p.row_count.toLocaleString()} rows</Badge>}
    >
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Stat label="Rows in" value={prof.row_count.toLocaleString()} />
        <Stat label="Rows curated" value={prof.curated_count.toLocaleString()} />
        <Stat label="Date span" value={`${prof.date_from?.slice(0, 10) ?? '—'} → ${prof.date_to?.slice(0, 10) ?? '—'}`} />
        <Stat label="Duplicates" value={prof.duplicate_rows.toLocaleString()} />
        <Stat label="Bad dates" value={`${prof.unparseable_dates.toLocaleString()} (${(prof.unparseable_date_pct * 100).toFixed(1)}%)`} />
        <Stat label="Products" value={(prof.cardinality.product_id ?? '—').toLocaleString()} />
        <Stat label="Regions" value={prof.cardinality.region ?? '—'} />
        <Stat label="Customers" value={(prof.cardinality.customer_id ?? '—').toLocaleString()} />
      </div>

      <h3 className="mt-6 mb-2 font-mono text-[11px] tracking-[0.2em] text-fog uppercase">Null share by column</h3>
      <NullBar data={prof.null_pct} />

      <h3 className="mt-6 mb-2 font-mono text-[11px] tracking-[0.2em] text-fog uppercase">Detected schema map</h3>
      <table className="w-full text-sm">
        <tbody>
          {Object.entries(p.schema_map).map(([role, col]) => (
            <tr key={role} className="border-t border-ink/10">
              <td className="py-1 pr-4 font-mono text-xs text-fog">{role}</td>
              <td className="py-1 font-mono text-xs">{col}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {Object.keys(prof.numeric_summary).length > 0 && (
        <>
          <h3 className="mt-6 mb-2 font-mono text-[11px] tracking-[0.2em] text-fog uppercase">Numeric summary</h3>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left font-mono text-[11px] text-fog uppercase">
                <th className="py-1 pr-4">Field</th>
                <th className="py-1 pr-4">Min</th>
                <th className="py-1 pr-4">Max</th>
                <th className="py-1 pr-4">Mean</th>
              </tr>
            </thead>
            <tbody className="tnum font-mono text-xs">
              {Object.entries(prof.numeric_summary).map(([k, v]) => (
                <tr key={k} className="border-t border-ink/10">
                  <td className="py-1 pr-4">{k}</td>
                  <td className="py-1 pr-4">{v.min ?? '—'}</td>
                  <td className="py-1 pr-4">{v.max ?? '—'}</td>
                  <td className="py-1 pr-4">{typeof v.mean === 'number' ? v.mean.toFixed(2) : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </Card>
  );
}

export function DataLab() {
  const [selected, setSelected] = useState<string | null>(null);
  return (
    <div className="grid gap-4 lg:grid-cols-[380px_1fr]">
      <div className="grid content-start gap-4">
        <UploadCard onDone={setSelected} />
        <DatasetList selected={selected} onSelect={setSelected} />
      </div>
      <div>
        {selected ? (
          <ProfileView key={selected} id={selected} />
        ) : (
          <Card title="03 / Profile">
            <EmptyState title="No dataset selected" hint="Pick a dataset from the registry to inspect its profile." />
          </Card>
        )}
      </div>
    </div>
  );
}
