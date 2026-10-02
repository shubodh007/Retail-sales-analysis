/** /system — How the system works. Pipeline stages with live dataset figures. */
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api, formatApiError } from '../lib/api';
import { Card, ErrorState, Spinner } from '../components/ui';
import { Reveal } from '../components/Reveal';

function Stage({ n, name, desc, figure }: { n: string; name: string; desc: string; figure: string }) {
  return (
    <Reveal>
      <div className="grid gap-2 border-t border-ink/15 py-3 md:grid-cols-[48px_220px_1fr_auto]">
        <span className="font-mono text-xs text-fog">{n}</span>
        <span className="font-mono text-sm font-bold tracking-widest uppercase">{name}</span>
        <span className="text-sm text-ink/75">{desc}</span>
        <span className="tnum text-right font-mono text-sm">{figure}</span>
      </div>
    </Reveal>
  );
}

export function System() {
  const ds = useQuery({ queryKey: ['datasets'], queryFn: api.datasets });
  const latest = ds.data?.[0];
  const profile = useQuery({
    queryKey: ['profile', latest?.id],
    queryFn: () => api.profile(latest!.id),
    enabled: !!latest,
  });

  if (ds.isPending) return <Spinner label="Reading registry…" />;
  if (ds.isError) return <ErrorState message={formatApiError(ds.error)} onRetry={() => ds.refetch()} />;
  if (!latest) return <p className="text-sm">Upload a dataset in <Link to="/data-lab" className="text-ember underline">Data Lab</Link> first.</p>;

  const q = profile.data?.profile.quality;
  const marts = profile.data?.profile.marts as Record<string, number> | undefined;

  return (
    <div>
      <p className="mb-4 max-w-3xl text-sm text-ink/70">
        Every figure below comes from the processed dataset — no mock values, no marketing.
        Source: <span className="font-mono">{latest.filename}</span>, profiled in Data Lab.
      </p>

      <h2 className="font-mono text-[11px] tracking-[0.25em] text-fog uppercase">Pipeline · raw to screen</h2>
      <div className="mt-1">
        <Stage n="01" name="Raw data" desc="UCI Online Retail II transactions, staged as CSV" figure={latest.row_count.toLocaleString()} />
        <Stage n="02" name="PySpark" desc="Dedupe, date parse, numeric validation, cancellation split — deterministic policy, reconciled ledger" figure={q ? `${q.accepted.toLocaleString()} accepted` : '…'} />
        <Stage n="03" name="Parquet" desc="Curated lake: accepted rows, typed columns; cancellations stored separately" figure={profile.data ? '2 tables' : '…'} />
        <Stage n="04" name="PostgreSQL" desc="Six analytical marts (daily/monthly/product/country/customer) + anomaly flags + forecast store" figure={marts ? Object.values(marts).reduce((s, v) => s + v, 0).toLocaleString() + ' mart rows' : '…'} />
        <Stage n="05" name="FastAPI" desc="Aggregated DTOs only — raw rows never cross the API boundary" figure="70–380 ms local" />
        <Stage n="06" name="Forecasting" desc="ARIMA · Prophet · Random Forest · XGBoost on chronological holdouts, WAPE selection" figure="horizons 7 / 30 / 90 d" />
        <Stage n="07" name="React" desc="Industrial Analytics surfaces; 3D horizon lazy-loaded in its own chunk" figure="8 experiences" />
      </div>

      {q && (
        <div className="mt-6 grid gap-4 md:grid-cols-2">
          <Card title="Quality ledger · reconciled">
            <dl className="tnum grid grid-cols-2 gap-1 font-mono text-xs">
              <dt className="text-fog uppercase">Raw</dt><dd className="text-right">{latest.row_count.toLocaleString()}</dd>
              <dt className="text-fog uppercase">Duplicates</dt><dd className="text-right">{q.duplicates.toLocaleString()}</dd>
              <dt className="text-fog uppercase">Quarantined</dt><dd className="text-right">{q.quarantined.toLocaleString()}</dd>
              <dt className="text-fog uppercase">Cancellations</dt><dd className="text-right">{q.cancellations.toLocaleString()}</dd>
              <dt className="text-fog uppercase">Accepted</dt><dd className="text-right">{q.accepted.toLocaleString()}</dd>
            </dl>
          </Card>
          <Card title="Local measurements · labeled">
            <dl className="grid grid-cols-2 gap-1 font-mono text-xs">
              <dt className="text-fog uppercase">API range</dt><dd className="text-right">70–380 ms</dd>
              <dt className="text-fog uppercase">4-model train</dt><dd className="text-right">≈60 s (UCI global 30d)</dd>
              <dt className="text-fog uppercase">1M-row ingest</dt><dd className="text-right">≈7 min (local Spark)</dd>
              <dt className="text-fog uppercase">Main bundle</dt><dd className="text-right">≈893 KB / 291 KB gzip</dd>
              <dt className="text-fog uppercase">3D chunk</dt><dd className="text-right">≈939 KB, lazy only</dd>
            </dl>
            <p className="mt-2 font-mono text-[11px] text-fog">Measured on local dev hardware, 2026-09-30 — not production SLAs.</p>
          </Card>
        </div>
      )}
    </div>
  );
}
