/** /overview — "What is happening?" Pulse, trend, momentum, geography, quality. */
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { api, formatApiError } from '../lib/api';
import { regionsLink } from '../lib/links';
import { Badge, ErrorState, Spinner, Stat } from '../components/ui';
import { RankBar, TrendChart } from '../components/charts';
import CountUp from '../components/bits/CountUp';
import { Reveal } from '../components/Reveal';
import { DatasetStrip, PageGate, QualityNote } from '../components/Page';

const gbp = (v: number) =>
  `£${v.toLocaleString('en-US', { maximumFractionDigits: 0 })}`;

export function Overview() {
  return (
    <PageGate>
      {(id) => (
        <OverviewBody id={id} />
      )}
    </PageGate>
  );
}

function OverviewBody({ id }: { id: string }) {
  const { data, isPending, isError, error, refetch } = useQuery({
    queryKey: ['overview', id],
    queryFn: () => api.overview(id),
  });
  if (isPending) return <Spinner label="Aggregating marts…" />;
  if (isError) return <ErrorState message={formatApiError(error)} onRetry={() => refetch()} />;

  const ukShare = data.top_countries.length
    ? (data.top_countries[0].revenue / data.totals.revenue) * 100
    : 0;

  return (
    <div>
      <DatasetStrip
        filename={data.dataset.filename}
        span={`${data.daily[0]?.date ?? '—'} → ${data.daily[data.daily.length - 1]?.date ?? '—'}`}
        capabilities={data.dataset.capabilities}
      />

      {/* Pulse lead — editorial, not a card grid */}
      <div className="border-b-2 border-ink pb-5">
        <p className="font-mono text-[11px] tracking-[0.25em] text-fog uppercase">Revenue pulse · accepted rows only</p>
        <p className="num-sans mt-1 text-5xl font-bold tracking-tight md:text-6xl">
          <CountUp to={data.totals.revenue} prefix="£" separator="," decimals={0} />
        </p>
        <div className="mt-4 grid grid-cols-2 gap-4 md:grid-cols-4">
          <Stat label="Units" value={<CountUp to={data.totals.qty} separator="," />} />
          <Stat label="Orders" value={<CountUp to={data.totals.orders} separator="," />} />
          <Stat label="Products" value={<CountUp to={data.totals.products} separator="," />} />
          <Stat label="UK share" value={`${ukShare.toFixed(1)}%`} mono={false} />
        </div>
        <QualityNote
          accepted={data.quality.accepted}
          quarantined={data.quality.quarantined}
          cancellations={data.quality.cancellations}
        />
      </div>

      <Reveal className="mt-6">
        <div className="flex items-baseline justify-between">
          <h2 className="font-mono text-[11px] tracking-[0.25em] text-fog uppercase">Daily revenue · 2 years</h2>
          <Link to="/sales" className="font-mono text-[11px] tracking-wider text-ember uppercase">
            Open sales analysis →
          </Link>
        </div>
        <TrendChart
          dates={data.daily.map((d) => d.date)}
          series={[{ name: 'Revenue £', values: data.daily.map((d) => d.revenue), color: '#17191c' }]}
          height={320}
        />
      </Reveal>

      {/* Asymmetric split: momentum vs geography */}
      <div className="mt-6 grid gap-6 lg:grid-cols-5">
        <Reveal className="lg:col-span-3">
          <div className="flex items-baseline justify-between">
            <h2 className="font-mono text-[11px] tracking-[0.25em] text-fog uppercase">Product momentum · top 8</h2>
            <Link to="/products" className="font-mono text-[11px] tracking-wider text-ember uppercase">
              All products →
            </Link>
          </div>
          <RankBar
            rows={data.top_products.slice(0, 8).map((p) => ({
              label: `${p.stockcode} · ${p.description.slice(0, 26)}`,
              value: p.revenue,
              color: '#e76f2f',
            }))}
            format={(v) => `£${(v / 1000).toFixed(0)}k`}
          />
        </Reveal>
        <Reveal className="lg:col-span-2">
          <h2 className="font-mono text-[11px] tracking-[0.25em] text-fog uppercase">Geographic signal · top 8</h2>
          <table className="mt-2 w-full">
            <tbody>
              {data.top_countries.map((c) => (
                <tr key={c.country} className="border-t border-ink/10">
                  <td className="py-1.5 pr-2 text-sm">
                    <Link to={regionsLink(c.country)} className="hover:text-ember hover:underline">{c.country}</Link>
                  </td>
                  <td className="w-24 py-1.5">
                    <span
                      className="block h-2 bg-moss"
                      style={{ width: `${Math.max(2, (c.revenue / data.top_countries[0].revenue) * 100)}%` }}
                    />
                  </td>
                  <td className="tnum py-1.5 text-right font-mono text-xs">{gbp(c.revenue)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-2 text-xs text-ink/60">
            Single-country dominance ({data.top_countries[0]?.country}) — wholesale skew, see dataset notes.
          </p>
        </Reveal>
      </div>

      {data.top_products[0]?.stockcode === 'M' && (
        <div className="mt-4">
          <Badge tone="brass">Manual adjustments (code “M”) top the product list — bookkeeping lines, not merchandise</Badge>
        </div>
      )}
    </div>
  );
}
