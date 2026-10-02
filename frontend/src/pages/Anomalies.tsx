/** /anomalies — Anomaly Observatory. Flags with baselines, never causes. */
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api, formatApiError } from '../lib/api';
import { forecastLink } from '../lib/links';
import { Badge, Card, ErrorState, Spinner, Stat } from '../components/ui';
import { Reveal } from '../components/Reveal';
import { DatasetStrip, PageGate } from '../components/Page';

const DIMS = [
  { v: 'global', label: 'Global' },
  { v: 'country', label: 'Country' },
  { v: 'product', label: 'Product' },
];

export function Anomalies() {
  return (
    <PageGate>
      {(id, dataset) => (
        <AnomaliesBody
          id={id}
          filename={dataset.filename}
          span={`${dataset.date_from?.slice(0, 10) ?? '—'} → ${dataset.date_to?.slice(0, 10) ?? '—'}`}
        />
      )}
    </PageGate>
  );
}

function AnomaliesBody({ id, filename, span }: { id: string; filename: string; span: string }) {
  const [dim, setDim] = useState('global');
  const [key, setKey] = useState('');
  const [page, setPage] = useState(0);
  const limit = 25;

  const summary = useQuery({ queryKey: ['anom-sum', id], queryFn: () => api.anomaliesSummary(id) });
  const flags = useQuery({
    queryKey: ['anom', id, dim, key, page],
    queryFn: () => api.anomalies(id, dim, key || undefined, limit, page * limit),
  });

  return (
    <div>
      <DatasetStrip filename={filename} span={span} />
      <p className="mb-4 max-w-3xl text-sm text-ink/70">
        Trailing median + MAD robust z-scores (|z| ≥ 3.5, 28-day trailing window, past data only).
        Flags mark movement <em>associated with</em> unusual days — the method explains nothing about causes.
      </p>

      {summary.data && (
        <div className="grid grid-cols-3 gap-4 border-b-2 border-ink pb-4">
          {(['global', 'country', 'product'] as const).map((d) => (
            <Stat key={d} label={`${d} flags`} value={summary.data.by_dimension[d] ?? 0} />
          ))}
        </div>
      )}

      {/* Dimension rail */}
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <div className="flex border border-ink/25" role="group" aria-label="Dimension">
          {DIMS.map((d) => (
            <button key={d.v} onClick={() => { setDim(d.v); setKey(''); setPage(0); }} aria-pressed={dim === d.v}
              className={`px-4 py-1.5 font-mono text-xs tracking-widest uppercase ${dim === d.v ? 'bg-ink text-paper' : 'hover:bg-bone'}`}>
              {d.label}
            </button>
          ))}
        </div>
        {dim !== 'global' && (
          <input value={key} onChange={(e) => { setKey(e.target.value); setPage(0); }}
            placeholder={dim === 'country' ? 'Filter country… (empty = all)' : 'Filter stock code… (empty = all)'}
            aria-label="Dimension key filter"
            className="border border-ink/25 bg-paper px-3 py-1.5 font-mono text-xs" />
        )}
      </div>

      <div className="mt-4">
        {flags.isPending && <Spinner label="Reading flags…" />}
        {flags.isError && <ErrorState message={formatApiError(flags.error)} onRetry={() => flags.refetch()} />}
        {flags.data && flags.data.items.length === 0 && (
          <Card title="No flags">
            <p className="text-sm text-ink/70">No {dim} anomalies recorded for this dataset — a clean bill, not missing data.</p>
          </Card>
        )}
        {flags.data && flags.data.items.length > 0 && (
          <Reveal>
            <Card
              title={`${dim} flags · ${flags.data.total.toLocaleString()}`}
              aside={<Badge tone="steel">{flags.data.method}</Badge>}
            >
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left font-mono text-[11px] text-fog uppercase">
                    <th className="py-1 pr-2">Date</th>
                    {dim !== 'global' && <th className="py-1 pr-2">Context</th>}
                    <th className="py-1 pr-2 text-right">Observed</th>
                    <th className="py-1 pr-2 text-right">Expected</th>
                    <th className="py-1 pr-2 text-right">z</th>
                    <th className="py-1 text-right">Forecast</th>
                  </tr>
                </thead>
                <tbody className="tnum font-mono text-xs">
                  {flags.data.items.map((f, i) => (
                    <tr key={`${f.date}-${i}`} className="border-t border-ink/10">
                      <td className="py-1.5 pr-2">{f.date}</td>
                      {dim !== 'global' && <td className="py-1.5 pr-2">{f.key}</td>}
                      <td className={`py-1.5 pr-2 text-right ${f.deviation < 0 ? 'text-ember' : ''}`}>
                        £{f.observed.toLocaleString('en-US', { maximumFractionDigits: 0 })}
                      </td>
                      <td className="py-1.5 pr-2 text-right">£{f.expected.toLocaleString('en-US', { maximumFractionDigits: 0 })}</td>
                      <td className="py-1.5 pr-2 text-right">{f.deviation > 0 ? '+' : ''}{f.deviation.toFixed(1)}</td>
                      <td className="py-1.5 text-right">
                        <Link
                          to={dim === 'product' ? forecastLink('product', f.key) : dim === 'country' ? forecastLink('country', f.key) : forecastLink('global')}
                          className="text-ember hover:underline"
                        >
                          Model it →
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="mt-3 flex items-center justify-between font-mono text-xs text-fog">
                <span>{flags.data.total.toLocaleString()} TOTAL · PAGE {page + 1} / {Math.max(1, Math.ceil(flags.data.total / limit))}</span>
                <div className="flex gap-2">
                  <button disabled={page === 0} onClick={() => setPage((p) => p - 1)} className="border border-ink/25 px-2 py-0.5 uppercase disabled:opacity-40">Prev</button>
                  <button disabled={(page + 1) * limit >= flags.data.total} onClick={() => setPage((p) => p + 1)} className="border border-ink/25 px-2 py-0.5 uppercase disabled:opacity-40">Next</button>
                </div>
              </div>
              <p className="mt-1 font-mono text-[11px] tracking-wider text-fog">{flags.data.language}</p>
            </Card>
          </Reveal>
        )}
      </div>
    </div>
  );
}
