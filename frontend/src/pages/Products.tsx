/** /products — "Which products drive the business?" Contribution, momentum, extremes. */
import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { api, formatApiError } from '../lib/api';
import { forecastLink } from '../lib/links';
import { Badge, Button, Card, ErrorState, Spinner } from '../components/ui';
import { RankBar, TrendChart } from '../components/charts';
import { Reveal } from '../components/Reveal';
import { DatasetStrip, PageGate } from '../components/Page';

export function Products() {
  return (
    <PageGate>
      {(id, dataset) => (
        <ProductsBody
          id={id}
          filename={dataset.filename}
          span={`${dataset.date_from?.slice(0, 10) ?? '—'} → ${dataset.date_to?.slice(0, 10) ?? '—'}`}
        />
      )}
    </PageGate>
  );
}

type SortKey = 'revenue' | 'qty' | 'orders';

function ProductsBody({ id, filename, span }: { id: string; filename: string; span: string }) {
  const [params] = useSearchParams();
  const [sort, setSort] = useState<SortKey>('revenue');
  const [search, setSearch] = useState(params.get('search') ?? '');
  const [query, setQuery] = useState(params.get('search') ?? '');
  const [page, setPage] = useState(0);
  const [focus, setFocus] = useState<string | null>(null);
  const limit = 25;

  const caps = useQuery({ queryKey: ['caps', id], queryFn: () => api.profile(id) });
  const list = useQuery({
    queryKey: ['products', id, sort, query, page],
    queryFn: () => api.products(id, { sort, limit, offset: page * limit, search: query || undefined }),
    placeholderData: keepPreviousData,
  });
  const top = useQuery({ queryKey: ['top10', id], queryFn: () => api.products(id, { sort: 'revenue', limit: 10 }) });
  const trend = useQuery({
    queryKey: ['ptrend', id, focus],
    queryFn: () => api.productTrend(id, focus!),
    enabled: !!focus,
  });

  const pages = list.data ? Math.max(1, Math.ceil(list.data.total / limit)) : 1;

  return (
    <div>
      <DatasetStrip filename={filename} span={span} />

      {caps.data && !caps.data.schema_map.category && (
        <div className="mb-4">
          <Badge tone="brass">Category analysis unavailable — this dataset has no category column (no data invented)</Badge>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-5">
        {/* Contribution */}
        <Reveal className="lg:col-span-2">
          <Card title="Top 10 by revenue">
            {top.isPending && <Spinner label="Ranking…" />}
            {top.isError && <ErrorState message={formatApiError(top.error)} onRetry={() => top.refetch()} />}
            {top.data && (
              <RankBar
                rows={top.data.items.map((p) => ({
                  label: `${p.stockcode} · ${p.description.slice(0, 22)}`,
                  value: p.revenue,
                  color: '#17191c',
                }))}
                format={(v) => `£${(v / 1000).toFixed(0)}k`}
              />
            )}
          </Card>
        </Reveal>

        {/* Explorer table */}
        <Reveal className="lg:col-span-3">
          <Card
            title={`Explorer · ${list.data?.total.toLocaleString() ?? '…'} products`}
            aside={
              <div className="flex gap-2">
                {(['revenue', 'qty', 'orders'] as const).map((s) => (
                  <button
                    key={s}
                    onClick={() => { setSort(s); setPage(0); }}
                    aria-pressed={sort === s}
                    className={`px-2 py-0.5 font-mono text-[11px] tracking-wider uppercase ${sort === s ? 'bg-ink text-paper' : 'text-fog hover:text-ink'}`}
                  >
                    {s}
                  </button>
                ))}
              </div>
            }
          >
            <form
              className="mb-3 flex gap-2"
              onSubmit={(e) => { e.preventDefault(); setQuery(search); setPage(0); }}
            >
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search code or name…"
                aria-label="Search products"
                className="w-full border border-ink/25 bg-paper px-3 py-1.5 font-mono text-xs"
              />
              <Button type="submit">Go</Button>
            </form>
            {list.isPending && <Spinner label="Loading products…" />}
            {list.isError && <ErrorState message={formatApiError(list.error)} onRetry={() => list.refetch()} />}
            {list.data && (
              <>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left font-mono text-[11px] text-fog uppercase">
                      <th className="py-1 pr-2">Code</th>
                      <th className="py-1 pr-2">Name</th>
                      <th className="py-1 pr-2 text-right">Qty</th>
                      <th className="py-1 pr-2 text-right">Revenue</th>
                      <th className="py-1 text-right">Orders</th>
                    </tr>
                  </thead>
                  <tbody className="tnum font-mono text-xs">
                    {list.data.items.map((p) => (
                      <tr
                        key={p.stockcode}
                        onClick={() => setFocus(p.stockcode)}
                        className={`cursor-pointer border-t border-ink/10 hover:bg-bone/70 ${focus === p.stockcode ? 'bg-bone' : ''}`}
                      >
                        <td className="py-1.5 pr-2">
                          {p.stockcode}{' '}
                          <Link
                            to={forecastLink('product', p.stockcode)}
                            onClick={(e) => e.stopPropagation()}
                            className="text-ember hover:underline"
                            aria-label={`Forecast ${p.stockcode}`}
                          >
                            ➤
                          </Link>
                        </td>
                        <td className="max-w-48 truncate py-1.5 pr-2 font-sans text-[13px]">{p.description}</td>
                        <td className="py-1.5 pr-2 text-right">{p.qty.toLocaleString()}</td>
                        <td className="py-1.5 pr-2 text-right">£{p.revenue.toLocaleString('en-US', { maximumFractionDigits: 0 })}</td>
                        <td className="py-1.5 text-right">{p.orders.toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <div className="mt-3 flex items-center justify-between font-mono text-xs text-fog">
                  <span>PAGE {page + 1} / {pages}</span>
                  <div className="flex gap-2">
                    <Button disabled={page === 0} onClick={() => setPage((p) => p - 1)}>Prev</Button>
                    <Button disabled={page + 1 >= pages} onClick={() => setPage((p) => p + 1)}>Next</Button>
                  </div>
                </div>
              </>
            )}
          </Card>
        </Reveal>
      </div>

      {/* Focused momentum */}
      <div className="mt-6">
        {!focus && (
          <Card title="Product momentum">
            <p className="text-sm text-ink/70">Select a row to inspect its daily revenue curve.</p>
          </Card>
        )}
        {focus && trend.isPending && <Card title={`Momentum · ${focus}`}><Spinner label="Loading curve…" /></Card>}
        {focus && trend.isError && <ErrorState message={formatApiError(trend.error)} />}
        {focus && trend.data && (
          <Reveal>
            <Card title={`Momentum · ${trend.data.stockcode}`} aside={<Button onClick={() => setFocus(null)}>Clear</Button>}>
              <TrendChart
                dates={trend.data.points.map((p) => p.date)}
                series={[{ name: 'Revenue £', values: trend.data.points.map((p) => p.revenue), color: '#e76f2f' }]}
                height={260}
              />
            </Card>
          </Reveal>
        )}
      </div>
    </div>
  );
}
