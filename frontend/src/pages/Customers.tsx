/** /customers — Customer Intelligence. RFM segments, value, methodology. */
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api, formatApiError } from '../lib/api';
import { forecastLink } from '../lib/links';
import { Link } from 'react-router-dom';
import { Badge, Card, ErrorState, Spinner } from '../components/ui';
import { DonutChart, RankBar } from '../components/charts';
import { Reveal } from '../components/Reveal';
import { DatasetStrip, PageGate } from '../components/Page';

export function Customers() {
  return (
    <PageGate>
      {(id, dataset) => (
        <CustomersBody
          id={id}
          filename={dataset.filename}
          span={`${dataset.date_from?.slice(0, 10) ?? '—'} → ${dataset.date_to?.slice(0, 10) ?? '—'}`}
        />
      )}
    </PageGate>
  );
}

function CustomersBody({ id, filename, span }: { id: string; filename: string; span: string }) {
  const [segment, setSegment] = useState<string>('');
  const rfm = useQuery({ queryKey: ['rfm', id], queryFn: () => api.rfm(id) });

  if (rfm.isPending) return <Spinner label="Scoring customers…" />;
  if (rfm.isError) {
    const status = (rfm.error as { status?: number })?.status;
    if (status === 409)
      return (
        <div>
          <DatasetStrip filename={filename} span={span} />
          <Card title="Customer Intelligence">
            <p className="text-sm text-ink/70">
              This dataset has no customer column — no segments computed, no personas invented.
            </p>
          </Card>
        </div>
      );
    return <ErrorState message={formatApiError(rfm.error)} onRetry={() => rfm.refetch()} />;
  }

  const shown = segment ? rfm.data.customers.filter((c) => c.segment === segment) : rfm.data.customers;

  return (
    <div>
      <DatasetStrip filename={filename} span={span} />
      <p className="mb-4 max-w-3xl text-sm text-ink/70">
        {rfm.data.customers_total.toLocaleString()} customers scored by recency, frequency and monetary value.
        Segments are deterministic rules — no clustering, no invented attributes.
      </p>

      <div className="grid gap-6 lg:grid-cols-5">
        {/* Segment distribution by revenue */}
        <Reveal className="lg:col-span-2">
          <h2 className="font-mono text-[11px] tracking-[0.25em] text-fog uppercase">Revenue by segment</h2>
          <DonutChart rows={rfm.data.segments.slice(0, 6).map((s, i) => ({ label: s.segment, value: s.revenue, color: ['#7fa58a','#5b9fb3','#8b6b9e','#d9785f','#e8c66a','#d99a9a'][i] }))} centerLabel="Customers" height={190} />
          <RankBar
            rows={rfm.data.segments.map((s) => ({
              label: `${s.segment} (${s.customers.toLocaleString()})`,
              value: s.revenue,
              color: s.segment === 'Champions' ? '#d9785f' : s.segment === 'Hibernating' ? '#5b9fb3' : '#5b9fb3',
            }))}
            format={(v) => `£${(v / 1000).toFixed(0)}k`}
          />
          <div className="mt-2 flex flex-wrap gap-2">
            <button onClick={() => setSegment('')} aria-pressed={!segment}
              className={`border px-2 py-1 font-mono text-[11px] uppercase ${!segment ? 'bg-ink text-paper' : 'border-ink/25'}`}>All</button>
            {rfm.data.segments.map((s) => (
              <button key={s.segment} onClick={() => setSegment(s.segment)} aria-pressed={segment === s.segment}
                className={`border px-2 py-1 font-mono text-[11px] uppercase ${segment === s.segment ? 'bg-ink text-paper' : 'border-ink/25 hover:bg-bone'}`}>
                {s.segment}
              </button>
            ))}
          </div>
        </Reveal>

        {/* Customer list */}
        <Reveal className="lg:col-span-3">
          <Card
            title={segment ? `${segment} · top customers` : 'Top customers · all segments'}
            aside={<Badge tone="steel">{shown.length} shown of {rfm.data.customers_total.toLocaleString()}</Badge>}
          >
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left font-mono text-[11px] text-fog uppercase">
                  <th className="py-1 pr-2">Customer</th>
                  <th className="py-1 pr-2">Segment</th>
                  <th className="py-1 pr-2 text-right">R/F/M</th>
                  <th className="py-1 pr-2 text-right">Orders</th>
                  <th className="py-1 text-right">Revenue</th>
                </tr>
              </thead>
              <tbody className="tnum font-mono text-xs">
                {shown.slice(0, 25).map((c) => (
                  <tr key={c.customer_id} className="border-t border-ink/10">
                    <td className="py-1.5 pr-2">{c.customer_id} <span className="text-fog">· {c.country}</span></td>
                    <td className="py-1.5 pr-2">{c.segment}</td>
                    <td className="py-1.5 pr-2 text-right">{c.r}/{c.f}/{c.m}</td>
                    <td className="py-1.5 pr-2 text-right">{c.orders}</td>
                    <td className="py-1.5 text-right">£{c.revenue.toLocaleString('en-US', { maximumFractionDigits: 0 })}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-2 font-mono text-[11px] tracking-wider text-fog uppercase">
              R = recency score · F = frequency · M = monetary · {rfm.data.customers[0]?.customer_id} leads at £
              {rfm.data.customers[0]?.revenue.toLocaleString('en-US', { maximumFractionDigits: 0 })}
            </p>
          </Card>
        </Reveal>
      </div>

      <Reveal className="mt-6">
        <Card title="Methodology · RFM">
          <dl className="grid gap-x-6 gap-y-1 font-mono text-xs md:grid-cols-2">
            {Object.entries(rfm.data.methodology).map(([k, v]) => (
              <div key={k}><dt className="text-fog uppercase">{k}</dt><dd className="mb-2">{v}</dd></div>
            ))}
          </dl>
          <Link to={forecastLink('global')} className="font-mono text-[11px] tracking-wider text-ember uppercase">
            Forecast global revenue →
          </Link>
        </Card>
      </Reveal>
    </div>
  );
}
