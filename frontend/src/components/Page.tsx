import { Link, useLocation } from 'react-router-dom';
import { Badge, EmptyState, ErrorState, Spinner } from './ui';
import { useActiveDataset } from '../lib/useDataset';
import { formatApiError, type Dataset } from '../lib/api';
import { BlurText } from './bits/BlurText';
import { AnimatedContent } from './bits/AnimatedContent';

const COPY: Record<string, { kicker: string; title: string; desc: string }> = {
  '/overview': { kicker: 'Your retail pulse', title: 'See what is happening.', desc: 'A friendly view of revenue, products, markets and the signals worth your attention.' },
  '/sales': { kicker: 'Sales explorer', title: 'Understand the sales curve.', desc: 'Move from the big picture to daily rhythm, geography and the moments that shaped revenue.' },
  '/products': { kicker: 'Product intelligence', title: 'Find what is selling.', desc: 'Compare products, search the catalogue and open any item to inspect its momentum.' },
  '/regions': { kicker: 'Geographic intelligence', title: 'See where demand comes from.', desc: 'Compare markets, spot concentration and drill into a country before forecasting it.' },
  '/customers': { kicker: 'Customer intelligence', title: 'Understand your customers.', desc: 'RFM segments turn transaction history into clear groups you can explore.' },
  '/forecast': { kicker: 'Forecast studio', title: 'Look ahead with confidence.', desc: 'Compare models, choose a horizon and see the expected path with uncertainty made visible.' },
  '/anomalies': { kicker: 'Anomaly observatory', title: 'Notice what looks unusual.', desc: 'Review robust statistical flags without pretending an anomaly automatically explains its cause.' },
};

export function PageGate({ children }: { children: (id: string, dataset: Dataset) => React.ReactNode }) {
  const { dataset, isPending, isError, error, refetch } = useActiveDataset();
  if (isPending) return <Spinner label="Preparing your workspace…" />;
  if (isError) return <ErrorState message={formatApiError(error)} onRetry={() => refetch()} />;
  if (!dataset) return <EmptyState title="No dataset yet" hint="Upload a retail CSV in Data Lab first — the analytics pages only show processed data." />;
  return <AnimatedContent className="page-enter">{children(dataset.id, dataset)}</AnimatedContent>;
}

export function DatasetStrip({ filename, span, capabilities }: { filename: string; span: string; capabilities?: Record<string, boolean> }) {
  const { pathname } = useLocation();
  const copy = COPY[pathname] ?? COPY['/overview'];
  return (
    <div className="page-intro">
      <div className="page-intro__top">
        <div>
          <p className="eyebrow">{copy.kicker}</p>
          <h1><BlurText text={copy.title} /></h1>
          <p className="page-intro__desc">{copy.desc}</p>
        </div>
        <div className="dataset-pill">
          <span className="dataset-pill__dot" />
          <Link to="/data-lab" title={`${filename} · ${span}`}>{filename}</Link>
          <span>{span}</span>
        </div>
      </div>
      {capabilities && <div className="capability-row">{Object.entries(capabilities).map(([k, v]) => <Badge key={k} tone={v ? 'moss' : 'brass'}>{k}</Badge>)}</div>}
    </div>
  );
}

export function QualityNote({ accepted, quarantined, cancellations }: { accepted: number; quarantined: number; cancellations: number }) {
  return <p className="quality-note">✓ {accepted.toLocaleString()} accepted · {quarantined.toLocaleString()} quarantined · {cancellations.toLocaleString()} cancellations — the ledger stays reconciled.</p>;
}

export function PageHero({ kicker, title, desc, children }: { kicker: string; title: string; desc: string; children?: React.ReactNode }) {
  return <div className="page-intro"><div className="page-intro__top"><div><p className="eyebrow">{kicker}</p><h1><BlurText text={title} /></h1><p className="page-intro__desc">{desc}</p></div>{children}</div></div>;
}
