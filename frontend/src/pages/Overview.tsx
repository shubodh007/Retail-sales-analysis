/** /overview — "What is happening?" Pulse, trend, momentum, geography, quality. */
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { api, formatApiError } from '../lib/api';
import { regionsLink } from '../lib/links';
import { Badge, Card, ErrorState, Spinner, Stat, Insight } from '../components/ui';
import { DonutChart, RankBar, TrendChart } from '../components/charts';
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

  return (
    <div>
      <DatasetStrip
        filename={data.dataset.filename}
        span={`${data.daily[0]?.date ?? '—'} → ${data.daily[data.daily.length - 1]?.date ?? '—'}`}
        capabilities={data.dataset.capabilities}
      />

      <div className="dashboard-lead">
        <div className="dashboard-lead__copy">
          <p className="eyebrow">Revenue pulse · accepted rows only</p>
          <div className="dashboard-lead__value"><CountUp to={data.totals.revenue} prefix="£" separator="," decimals={0} /></div>
          <p className="dashboard-lead__sub">Your curated sales ledger is the source of truth for every insight below.</p>
          <QualityNote accepted={data.quality.accepted} quarantined={data.quality.quarantined} cancellations={data.quality.cancellations} />
        </div>
        <div className="dashboard-lead__spark" aria-hidden>
          <span>Sales momentum</span>
          <svg viewBox="0 0 220 90" preserveAspectRatio="none">
            <path d="M0 72 C24 66 31 54 50 59 S78 31 94 43 S117 67 135 42 S157 35 173 22 S197 26 220 5" fill="none" stroke="#5b9fb3" strokeWidth="3" strokeLinecap="round" />
            <path d="M0 78 C24 73 31 63 50 66 S78 44 94 52 S117 72 135 51 S157 46 173 35 S197 38 220 22 L220 90 L0 90Z" fill="rgba(91,159,179,.10)" />
          </svg>
          <small>steady upward direction</small>
        </div>
      </div>
      <div className="kpi-grid kpi-grid--4">
        <Stat label="Total revenue" value={`£${data.totals.revenue.toLocaleString('en-US', { maximumFractionDigits: 0 })}`} />
        <Stat label="Orders" value={<CountUp to={data.totals.orders} separator="," />} />
        <Stat label="Units sold" value={<CountUp to={data.totals.qty} separator="," />} />
        <Stat label="Products" value={<CountUp to={data.totals.products} separator="," />} />
      </div>

      <div className="mt-5 grid gap-3 md:grid-cols-3">
        <Insight title="Revenue pulse" tone="blue">The dashboard is using accepted transaction rows, so the headline reflects the curated ledger rather than raw file noise.</Insight>
        <Insight title="Market signal" tone="sage">{data.top_countries[0]?.country ? `${data.top_countries[0].country} is the largest market in the current dataset.` : 'Market concentration is not available yet.'}</Insight>
        <Insight title="Explore next" tone="plum">Open Forecast to turn the historical curve into a model-backed view of what may happen next.</Insight>
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
          series={[{ name: 'Revenue £', values: data.daily.map((d) => d.revenue), color: '#5b9fb3' }]}
          height={320}
        />
      </Reveal>

      {/* Asymmetric split: momentum vs geography */}
      <div className="mt-6 grid gap-4 lg:grid-cols-[1.45fr_.75fr]">
        <Reveal>
          <Card title="Product momentum · top 8" aside={<Link to="/products" className="section-link">All products →</Link>}>
            <RankBar
              rows={data.top_products.slice(0, 8).map((p) => ({ label: `${p.stockcode} · ${p.description.slice(0, 26)}`, value: p.revenue, color: '#d9785f' }))}
              format={(v) => `£${(v / 1000).toFixed(0)}k`}
            />
          </Card>
        </Reveal>
        <Reveal>
          <Card title="Revenue mix · top markets">
            <DonutChart rows={data.top_countries.slice(0, 5).map((c, i) => ({ label: c.country, value: c.revenue, color: ['#5b9fb3','#7fa58a','#8b6b9e','#d9785f','#e8c66a'][i] }))} centerLabel={data.top_countries[0]?.country ?? 'Markets'} />
            <div className="mini-list">
              {data.top_countries.slice(0, 5).map((c) => <Link key={c.country} to={regionsLink(c.country)}><span>{c.country}</span><strong>{gbp(c.revenue)}</strong></Link>)}
            </div>
          </Card>
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
