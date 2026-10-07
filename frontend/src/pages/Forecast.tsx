/** /forecast — Forecast Lab. Target/context/horizon/model → job → evidence. */
import { Suspense, lazy, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useMutation, useQuery } from '@tanstack/react-query';
import { api, formatApiError, type FcGroup } from '../lib/api';
import { Badge, Button, Card, ErrorState, Spinner, Stat, Insight } from '../components/ui';
import { BandChart } from '../components/charts';
import CountUp from '../components/bits/CountUp';
import { ShinyText } from '../components/bits/ShinyText';
import { Reveal } from '../components/Reveal';
import { DatasetStrip, PageGate } from '../components/Page';

const HorizonSection = lazy(() => import('./HorizonSection'));

const HORIZONS = [7, 30, 90];
const MODEL_OPTS = [
  { v: '', label: 'Auto · fast evidence' },
  { v: 'arima', label: 'ARIMA' },
  { v: 'prophet', label: 'Prophet' },
  { v: 'rf', label: 'Random Forest' },
  { v: 'xgb', label: 'XGBoost' },
];

export function Forecast() {
  return (
    <PageGate>
      {(id, dataset) => (
        <Lab
          id={id}
          filename={dataset.filename}
          span={`${dataset.date_from?.slice(0, 10) ?? '—'} → ${dataset.date_to?.slice(0, 10) ?? '—'}`}
        />
      )}
    </PageGate>
  );
}

function Lab({ id, filename, span }: { id: string; filename: string; span: string }) {
  const [params] = useSearchParams();
  const [contextType, setContextType] = useState(params.get('context') ?? 'global');
  const [contextId, setContextId] = useState(params.get('context_id') ?? '');
  const [horizon, setHorizon] = useState(30);
  const [model, setModel] = useState('');
  const [groupId, setGroupId] = useState<string | null>(null);

  const caps = useQuery({ queryKey: ['fc-caps', id, horizon], queryFn: () => api.fcCapabilities(id, horizon) });
  const geo = useQuery({ queryKey: ['geo-list', id], queryFn: () => api.geography(id), enabled: contextType === 'country' });

  const create = useMutation({
    mutationFn: () =>
      api.fcCreate({
        dataset_id: id, target: 'revenue', context_type: contextType,
        context_id: contextType === 'global' ? null : contextId || null,
        horizon, models: model ? [model] : null,
      }),
    onSuccess: (g) => setGroupId(g.id),
  });

  const group = useQuery({
    queryKey: ['fc-group', groupId ?? params.get('group')],
    queryFn: () => api.fcGroup(groupId ?? params.get('group')!),
    enabled: !!(groupId ?? params.get('group')),
    refetchInterval: (q) => {
      const s = (q.state.data as FcGroup | undefined)?.status;
      return s === 'pending' || s === 'running' ? 4000 : false;
    },
  });
  const g = group.data;
  const shown = model ? g?.runs.find((r) => r.model === model) : g?.runs.find((r) => r.model === g?.best_model);

  return (
    <div>
      <DatasetStrip filename={filename} span={span} />

      <div className="mb-5 grid gap-3 md:grid-cols-3">
        <Insight title="Actuals" tone="blue">What already happened in the selected context.</Insight>
        <Insight title="Forecast" tone="plum">What the selected model expects next, with uncertainty shown on the chart.</Insight>
        <Insight title="Model choice" tone="sage">Auto mode compares models on chronological holdouts instead of guessing which algorithm wins.</Insight>
      </div>

      {/* Control rail */}
      <div className="grid gap-3 border-b-2 border-ink pb-4 md:grid-cols-[140px_1fr_1fr_1fr_auto]">
        <label className="block">
          <span className="font-mono text-[11px] tracking-[0.2em] text-fog uppercase">Target</span>
          <select disabled value="revenue" className="mt-1 w-full border border-ink/25 bg-bone px-2 py-1.5 font-mono text-xs uppercase" aria-label="Target">
            <option value="revenue">Revenue</option>
          </select>
        </label>
        <label className="block">
          <span className="font-mono text-[11px] tracking-[0.2em] text-fog uppercase">Context</span>
          <div className="mt-1 flex gap-2">
            <select value={contextType} onChange={(e) => { setContextType(e.target.value); setContextId(''); }} className="border border-ink/25 bg-paper px-2 py-1.5 font-mono text-xs uppercase" aria-label="Context">
              <option value="global">Global</option>
              <option value="product">Product</option>
              <option value="country">Country</option>
            </select>
            {contextType === 'country' && (
              <input value={contextId} onChange={(e) => setContextId(e.target.value)} list="fc-countries" placeholder="Country…" aria-label="Country" className="w-full border border-ink/25 bg-paper px-2 py-1.5 font-mono text-xs" />
            )}
            {contextType === 'product' && (
              <input value={contextId} onChange={(e) => setContextId(e.target.value)} placeholder="StockCode…" aria-label="Product code" className="w-full border border-ink/25 bg-paper px-2 py-1.5 font-mono text-xs" />
            )}
            <datalist id="fc-countries">{geo.data?.countries.map((c) => <option key={c.country} value={c.country} />)}</datalist>
          </div>
        </label>
        <div>
          <span className="font-mono text-[11px] tracking-[0.2em] text-fog uppercase">Horizon</span>
          <div className="mt-1 flex border border-ink/25" role="group" aria-label="Horizon">
            {HORIZONS.map((h) => (
              <button key={h} onClick={() => setHorizon(h)} aria-pressed={horizon === h}
                className={`px-3 py-1.5 font-mono text-xs ${horizon === h ? 'bg-ink text-paper' : 'hover:bg-bone'}`}>{h}d</button>
            ))}
          </div>
        </div>
        <label className="block">
          <span className="font-mono text-[11px] tracking-[0.2em] text-fog uppercase">Model</span>
          <select value={model} onChange={(e) => setModel(e.target.value)} className="mt-1 w-full border border-ink/25 bg-paper px-2 py-1.5 font-mono text-xs uppercase" aria-label="Model">
            {MODEL_OPTS.map((m) => <option key={m.v} value={m.v}>{m.label}</option>)}
          </select>
        </label>
        <div className="flex items-end">
          <Button
            disabled={create.isPending || (contextType !== 'global' && !contextId)}
            onClick={() => create.mutate()}
          >
            {create.isPending ? 'Queuing…' : 'Train forecast'}
          </Button>
        </div>
      </div>
      {caps.data?.history && (
        <p className="mt-2 font-mono text-[11px] tracking-wider text-fog uppercase">
          History {caps.data.history.from} → {caps.data.history.to} · {caps.data.global_points} daily points · selection by lowest validation WAPE
        </p>
      )}
      {create.isError && <div className="mt-3"><ErrorState message={formatApiError(create.error)} /></div>}

      {/* Job + evidence */}
      {!g && (
        <Card title="No forecast yet">
          <p className="text-sm text-ink/70">
            Configure the rail above and train. Auto mode uses fast tree models on chronological holdouts; explicit model selection can still run ARIMA or Prophet. 
            the lowest validation WAPE is reported as best — never hardcoded.
          </p>
        </Card>
      )}
      {g && (g.status === 'pending' || g.status === 'running') && (
        <Spinner label={`Training ${g.horizon}-day ${g.context_type} forecast… (polling job ${g.id.slice(0, 8)})`} />
      )}
      {g?.status === 'failed' && <ErrorState message={g.error ?? 'training failed'} />}
      {g?.status === 'done' && shown && (
        <div className="mt-4">
          <div className="flex flex-wrap items-end gap-x-8 gap-y-2 border-b border-ink/15 pb-4">
            <div>
              <p className="font-mono text-[11px] tracking-[0.25em] text-fog uppercase">
                {shown.model} · next {g.horizon} days · total
              </p>
              <p className="tnum font-mono text-4xl font-bold">
                <CountUp to={shown.forecast.reduce((s, p) => s + p.predicted, 0)} prefix="£" separator="," decimals={0} />
              </p>
            </div>
            <Stat label="Validation WAPE" value={`${shown.metrics.wape?.toFixed(1)}%`} />
            <Stat label="Validation MAE" value={`£${(shown.metrics.mae ?? 0).toLocaleString('en-US', { maximumFractionDigits: 0 })}`} />
            <Stat label="Train time" value={`${shown.duration_s.toFixed(1)}s`} />
            <Badge tone="moss"><ShinyText>Selected model: {g.best_model ?? 'unavailable'}</ShinyText> — lowest validation WAPE</Badge>
          </div>
          {shown.metrics.wape != null && shown.metrics.wape > 60 && (
            <p className="mt-2 border border-brass/60 bg-brass/10 p-3 font-mono text-xs tracking-wider uppercase">
              High validation error — sparse or intermittent demand in this context; treat the forecast as directional, not precise.
            </p>
          )}

          <Reveal className="mt-4">
            <BandChart
              history={shown.history.map((h) => ({ date: h.date, v: h.actual }))}
              validation={shown.validation}
              forecast={shown.forecast.map((f) => ({ date: f.date, v: f.predicted, lo: f.lower, hi: f.upper }))}
            />
            <p className="mt-1 font-mono text-[11px] tracking-wider text-fog uppercase">
              Blue = history · plum = forecast · band = {shown.interval_type === 'analytic' ? 'analytic interval' : 'empirical residual band (p10–p90 of out-of-sample errors)'} · dashed = validation fit
            </p>
          </Reveal>

          <Reveal className="mt-6">
            <CompareTable groupId={g.id} />
          </Reveal>

          <Reveal className="mt-6">
            <Card title="Run metadata">
              <dl className="grid grid-cols-2 gap-x-6 gap-y-1 font-mono text-xs md:grid-cols-4">
                <div><dt className="text-fog uppercase">Train</dt><dd>{shown.train_from} → {shown.train_to}</dd></div>
                <div><dt className="text-fog uppercase">Validate</dt><dd>{shown.val_from} → {shown.val_to}</dd></div>
                <div><dt className="text-fog uppercase">MAPE</dt><dd>{shown.metrics.mape != null ? `${shown.metrics.mape.toFixed(1)}%` : `n/a (${shown.mape_status})`}</dd></div>
                <div><dt className="text-fog uppercase">sMAPE</dt><dd>{shown.metrics.smape?.toFixed(1)}%</dd></div>
                <div className="col-span-2 md:col-span-4"><dt className="text-fog uppercase">Config</dt><dd className="break-all">{JSON.stringify(shown.config)}</dd></div>
              </dl>
            </Card>
          </Reveal>

          <Suspense fallback={<Spinner label="Loading 3D horizon…" />}>
            <HorizonSection group={g} shownModel={shown.model} />
          </Suspense>
        </div>
      )}
    </div>
  );
}

function CompareTable({ groupId }: { groupId: string }) {
  const { data, isPending, isError } = useQuery({ queryKey: ['fc-compare', groupId], queryFn: () => api.fcCompare(groupId) });
  if (isPending) return <Spinner label="Scoring models…" />;
  if (isError || !data) return <ErrorState message="Comparison unavailable" />;
  return (
    <Card
      title="Model comparison · validation"
      aside={<Badge tone="steel">criterion: {data.selection.criterion}</Badge>}
    >
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left font-mono text-[11px] text-fog uppercase">
            <th className="py-1 pr-3">Model</th>
            <th className="py-1 pr-3 text-right">MAE</th>
            <th className="py-1 pr-3 text-right">RMSE</th>
            <th className="py-1 pr-3 text-right">WAPE</th>
            <th className="py-1 pr-3 text-right">sMAPE</th>
            <th className="py-1 pr-3 text-right">MAPE</th>
            <th className="py-1 text-right">Train</th>
          </tr>
        </thead>
        <tbody className="tnum font-mono text-xs">
          {data.models.map((m) => {
            const best = data.selection.best_model === m.model;
            return (
              <tr key={m.model} className={`border-t border-ink/10 ${best ? 'bg-brass/10' : ''}`}>
                <td className="py-1.5 pr-3">{m.model}{best && <span className="ml-2 text-ember">◀ lowest WAPE</span>}</td>
                <td className="py-1.5 pr-3 text-right">{m.metrics.mae?.toLocaleString('en-US', { maximumFractionDigits: 0 })}</td>
                <td className="py-1.5 pr-3 text-right">{m.metrics.rmse?.toLocaleString('en-US', { maximumFractionDigits: 0 })}</td>
                <td className="py-1.5 pr-3 text-right">{m.metrics.wape?.toFixed(1)}%</td>
                <td className="py-1.5 pr-3 text-right">{m.metrics.smape?.toFixed(1)}%</td>
                <td className="py-1.5 pr-3 text-right">{m.metrics.mape != null ? `${m.metrics.mape.toFixed(1)}%` : 'n/a'}</td>
                <td className="py-1.5 text-right">{m.duration_s.toFixed(1)}s</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </Card>
  );
}
