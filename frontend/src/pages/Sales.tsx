/** /sales — "How are sales behaving?" Workbench: grain, geography, rhythm. */
import { useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api, formatApiError } from '../lib/api';
import { forecastLink } from '../lib/links';
import { Button, Card, ErrorState, Spinner } from '../components/ui';
import { RankBar, TrendChart } from '../components/charts';
import { Reveal } from '../components/Reveal';
import { DatasetStrip, PageGate } from '../components/Page';

const DOW = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

export function Sales() {
  return (
    <PageGate>
      {(id, dataset) => (
        <SalesBody
          id={id}
          filename={dataset.filename}
          span={`${dataset.date_from?.slice(0, 10) ?? '—'} → ${dataset.date_to?.slice(0, 10) ?? '—'}`}
        />
      )}
    </PageGate>
  );
}

function SalesBody({ id, filename, span }: { id: string; filename: string; span: string }) {
  const [params] = useSearchParams();
  const [grain, setGrain] = useState<'daily' | 'monthly'>('daily');
  const [country, setCountry] = useState<string>(params.get('country') ?? '');

  const trend = useQuery({
    queryKey: ['trend', id, grain, country],
    queryFn: () => api.trend(id, grain, country || undefined),
  });
  const geo = useQuery({ queryKey: ['geo-list', id], queryFn: () => api.geography(id) });

  const rhythm = useMemo(() => {
    if (grain !== 'daily' || !trend.data) return null;
    const sums = new Array(7).fill(0);
    const counts = new Array(7).fill(0);
    for (const p of trend.data.points) {
      const d = new Date(`${p.date}T00:00:00Z`).getUTCDay(); // 0=Sun..6=Sat
      const i = (d + 6) % 7; // Mon-first
      sums[i] += p.revenue;
      counts[i] += 1;
    }
    return sums.map((s, i) => ({ label: DOW[i], value: counts[i] ? s / counts[i] : 0 }));
  }, [trend.data, grain]);

  const best = useMemo(() => {
    if (!trend.data?.points.length) return null;
    return trend.data.points.reduce((a, b) => (b.revenue > a.revenue ? b : a));
  }, [trend.data]);

  return (
    <div>
      <DatasetStrip filename={filename} span={span} />

      {/* Controls */}
      <div className="flex flex-wrap items-center gap-3 border-b border-ink/15 pb-4">
        <div className="flex border border-ink/25" role="group" aria-label="Grain">
          {(['daily', 'monthly'] as const).map((g) => (
            <button
              key={g}
              onClick={() => setGrain(g)}
              aria-pressed={grain === g}
              className={`px-4 py-1.5 font-mono text-xs tracking-widest uppercase ${grain === g ? 'bg-ink text-paper' : 'text-ink hover:bg-bone'}`}
            >
              {g}
            </button>
          ))}
        </div>
        <select
          aria-label="Country filter"
          value={country}
          onChange={(e) => setCountry(e.target.value)}
          className="border border-ink/25 bg-paper px-3 py-1.5 font-mono text-xs tracking-wider uppercase"
        >
          <option value="">All countries</option>
          {geo.data?.countries.map((c) => (
            <option key={c.country} value={c.country}>
              {c.country}
            </option>
          ))}
        </select>
        {country && <Button onClick={() => setCountry('')}>Clear</Button>}
        {geo.isError && (
          <span className="font-mono text-[11px] tracking-wider text-ember uppercase">(countries unavailable)</span>
        )}
        <Link to={forecastLink('country', country || undefined)} className="font-mono text-[11px] tracking-wider text-ember uppercase">
          Forecast {country || 'global'} →
        </Link>
        {best && (
          <span className="tnum ml-auto font-mono text-xs text-fog">
            PEAK {best.date} · £{best.revenue.toLocaleString('en-US', { maximumFractionDigits: 0 })}
          </span>
        )}
      </div>

      <div className="mt-4">
        {trend.isPending && <Spinner label={`Loading ${grain} trend…`} />}
        {trend.isError && <ErrorState message={formatApiError(trend.error)} onRetry={() => trend.refetch()} />}
        {trend.data && (
          <Reveal>
            <TrendChart
              dates={trend.data.points.map((p) => p.date)}
              series={[
                { name: 'Revenue £', values: trend.data.points.map((p) => p.revenue), color: '#d9785f' },
                { name: 'Orders', values: trend.data.points.map((p) => p.orders), color: '#5b9fb3', yAxis: 1, kind: 'bar' },
              ]}
              height={340}
            />
          </Reveal>
        )}
      </div>

      {rhythm && (
        <div className="mt-6 grid gap-6 lg:grid-cols-2">
          <Reveal>
            <Card title="Weekday rhythm · avg revenue">
              <RankBar rows={rhythm.map((r) => ({ ...r, color: '#7fa58a' }))} format={(v) => `£${(v / 1000).toFixed(0)}k`} height={rhythm.length * 34} />
            </Card>
          </Reveal>
          <Reveal>
            <Card title="Reading the curve">
              <ul className="list-disc space-y-2 pl-5 text-sm text-ink/80">
                <li>December peaks repeat yearly — gift-ware seasonality, not growth.</li>
                <li>Wholesale orders create single-day spikes; check quantity before celebrating revenue.</li>
                <li>Cancellations are already excluded — see Data Lab quality ledger.</li>
                <li>Filter by country to separate domestic scale from export noise.</li>
              </ul>
            </Card>
          </Reveal>
        </div>
      )}
    </div>
  );
}
