/** /regions — Geographic Intelligence. Country contribution, rank, drill-down. */
import { Link, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api, formatApiError } from '../lib/api';
import { forecastLink, salesLink } from '../lib/links';
import { Badge, Card, ErrorState, Spinner } from '../components/ui';
import { RankBar, TrendChart } from '../components/charts';
import { Reveal } from '../components/Reveal';
import { DatasetStrip, PageGate } from '../components/Page';

export function Regions() {
  return (
    <PageGate>
      {(id, dataset) => (
        <RegionsBody
          id={id}
          filename={dataset.filename}
          span={`${dataset.date_from?.slice(0, 10) ?? '—'} → ${dataset.date_to?.slice(0, 10) ?? '—'}`}
        />
      )}
    </PageGate>
  );
}

function RegionsBody({ id, filename, span }: { id: string; filename: string; span: string }) {
  const [params, setParams] = useSearchParams();
  const selected = params.get('country') ?? '';
  const geo = useQuery({ queryKey: ['geo', id], queryFn: () => api.geography(id) });
  const trend = useQuery({
    queryKey: ['region-trend', id, selected],
    queryFn: () => api.trend(id, 'daily', selected || undefined),
    enabled: !!selected,
  });

  if (geo.isPending) return <Spinner label="Ranking countries…" />;
  if (geo.isError) {
    const status = (geo.error as { status?: number })?.status;
    if (status === 409)
      return (
        <div>
          <DatasetStrip filename={filename} span={span} />
          <Card title="Geographic Intelligence">
            <p className="text-sm text-ink/70">
              This dataset has no geography column — nothing to rank, and nothing invented.
              Upload a file with a country/region/store column to enable this experience.
            </p>
          </Card>
        </div>
      );
    return <ErrorState message={formatApiError(geo.error)} onRetry={() => geo.refetch()} />;
  }

  const total = geo.data.countries.reduce((s, c) => s + c.revenue, 0) || 1;
  const top3 = geo.data.countries.slice(0, 3).reduce((s, c) => s + c.revenue, 0) / total;
  const detail = selected ? geo.data.countries.find((c) => c.country === selected) : null;

  return (
    <div>
      <DatasetStrip filename={filename} span={span} />
      <p className="mb-4 max-w-3xl text-sm text-ink/70">
        Country is the geographic dimension — no invented regions, no coordinates, no decorative globe.
        Top-3 concentration: <strong className="tnum font-mono">{(top3 * 100).toFixed(1)}%</strong> of revenue.
      </p>

      <div className="grid gap-6 lg:grid-cols-5">
        {/* Rank */}
        <Reveal className="lg:col-span-3">
          <h2 className="font-mono text-[11px] tracking-[0.25em] text-fog uppercase">
            Contribution · {geo.data.countries.length} countries
          </h2>
          <RankBar
            rows={geo.data.countries.slice(0, 20).map((c) => ({
              label: c.country,
              value: c.revenue,
              color: c.country === selected ? '#e76f2f' : '#17191c',
            }))}
            format={(v) => `£${(v / 1000).toFixed(0)}k`}
          />
          {geo.data.countries.length > 20 && (
            <p className="mt-1 font-mono text-[11px] tracking-wider text-fog uppercase">
              Top 20 of {geo.data.countries.length} — remainder in the rank table
            </p>
          )}
        </Reveal>

        {/* Detail drill-down */}
        <div className="lg:col-span-2">
          {!selected && (
            <Card title="Country drill-down">
              <p className="text-sm text-ink/70">Select a country in the table below to inspect its trend and continue into Sales or Forecast.</p>
            </Card>
          )}
          {selected && detail && (
            <Reveal>
              <Card
                title={detail.country}
                aside={<Badge tone="safety">{((detail.revenue / total) * 100).toFixed(1)}% of revenue</Badge>}
              >
                <div className="grid grid-cols-3 gap-2 font-mono text-xs">
                  <div><p className="text-fog uppercase">Revenue</p><p className="tnum text-sm">£{detail.revenue.toLocaleString('en-US', { maximumFractionDigits: 0 })}</p></div>
                  <div><p className="text-fog uppercase">Qty</p><p className="tnum text-sm">{detail.qty.toLocaleString()}</p></div>
                  <div><p className="text-fog uppercase">Orders</p><p className="tnum text-sm">{detail.orders.toLocaleString()}</p></div>
                </div>
                {trend.data && (
                  <div className="mt-3">
                    <TrendChart
                      dates={trend.data.points.map((p) => p.date)}
                      series={[{ name: 'Revenue £', values: trend.data.points.map((p) => p.revenue), color: '#e76f2f' }]}
                      height={200}
                    />
                  </div>
                )}
                <div className="mt-3 flex gap-3 font-mono text-[11px] tracking-wider uppercase">
                  <Link to={salesLink(selected)} className="text-ember">Sales drill-down →</Link>
                  <Link to={forecastLink('country', selected)} className="text-ember">Forecast this →</Link>
                  <button onClick={() => setParams({})} className="text-fog hover:text-ink">Clear</button>
                </div>
              </Card>
            </Reveal>
          )}
          {/* Compact rank table doubles as selector */}
          <h2 className="mt-4 font-mono text-[11px] tracking-[0.25em] text-fog uppercase">Rank</h2>
          <table className="mt-1 w-full text-sm">
            <tbody className="tnum font-mono text-xs">
              {geo.data.countries.map((c, i) => (
                <tr key={c.country} className={`border-t border-ink/10 ${c.country === selected ? 'bg-bone' : ''}`}>
                  <td className="py-1 pr-2 text-fog">{String(i + 1).padStart(2, '0')}</td>
                  <td className="py-1 pr-2">
                    <button onClick={() => setParams({ country: c.country })} className="hover:text-ember hover:underline">
                      {c.country}
                    </button>
                  </td>
                  <td className="py-1 text-right">£{c.revenue.toLocaleString('en-US', { maximumFractionDigits: 0 })}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
