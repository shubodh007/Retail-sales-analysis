import { Link, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from './lib/api';
import { Badge } from './components/ui';
import { DataLab } from './pages/DataLab';
import { Anomalies } from './pages/Anomalies';
import { Customers } from './pages/Customers';
import { Forecast } from './pages/Forecast';
import { Overview } from './pages/Overview';
import { Products } from './pages/Products';
import { Regions } from './pages/Regions';
import { Sales } from './pages/Sales';
import { System } from './pages/System';
import { useActiveDataset } from './lib/useDataset';

const NAV = [
  { to: '/overview', label: 'Overview' },
  { to: '/sales', label: 'Sales' },
  { to: '/products', label: 'Products' },
  { to: '/regions', label: 'Geographic Intelligence' },
  { to: '/customers', label: 'Customers' },
  { to: '/forecast', label: 'Forecast' },
  { to: '/anomalies', label: 'Anomalies' },
  { to: '/system', label: 'System' },
  { to: '/data-lab', label: 'Data Lab' },
];

/** Compact live-dataset indicator: real metadata, never a banner. */
function DatasetBadge() {
  const { dataset } = useActiveDataset();
  if (!dataset) return null;
  return (
    <Link
      to="/data-lab"
      title={`${dataset.filename} · ${dataset.row_count.toLocaleString()} rows`}
      className="hidden max-w-56 truncate font-mono text-[11px] tracking-wider text-fog uppercase hover:text-ember lg:inline"
    >
      {dataset.filename} · {(dataset.row_count / 1_000_000).toFixed(2)}M
    </Link>
  );
}

function Shell() {  const loc = useLocation();
  const health = useQuery({ queryKey: ['health'], queryFn: api.health, retry: false });
  return (
    <div className="min-h-screen">
      <header className="border-b-2 border-ink bg-paper">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-3">
            <span className="inline-block h-4 w-4 bg-safety" aria-hidden />
            <div>
              <p className="font-mono text-sm font-bold tracking-[0.25em] uppercase">Retail Intelligence</p>
              <p className="font-mono text-[11px] tracking-wider text-fog uppercase">Industrial Analytics</p>
            </div>
          </div>
          <nav className="flex items-center gap-4" aria-label="Primary">            {NAV.map((n) => (
              <Link
                key={n.to}
                to={n.to}
                aria-current={loc.pathname.startsWith(n.to) ? 'page' : undefined}
                className={`font-mono text-xs tracking-widest uppercase ${loc.pathname.startsWith(n.to) ? 'text-ember' : 'text-ink hover:text-ember'}`}
              >
                {n.label}
              </Link>
            ))}
            {health.data ? (
              <Badge tone={health.data.db ? 'moss' : 'brass'}>API {health.data.db ? 'live' : 'no-db'}</Badge>
            ) : (
              <Badge tone="steel">API …</Badge>
            )}
            <DatasetBadge />
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6">
        <Routes>
          <Route path="/" element={<Navigate to="/overview" replace />} />
          <Route path="/overview" element={<Overview />} />
          <Route path="/sales" element={<Sales />} />
          <Route path="/products" element={<Products />} />
          <Route path="/regions" element={<Regions />} />
          <Route path="/customers" element={<Customers />} />
          <Route path="/forecast" element={<Forecast />} />
          <Route path="/anomalies" element={<Anomalies />} />
          <Route path="/system" element={<System />} />
          <Route path="/data-lab" element={<DataLab />} />
          <Route path="*" element={<Navigate to="/overview" replace />} />
        </Routes>
        <footer className="mt-10 border-t border-ink/15 pt-3 font-mono text-[11px] tracking-wider text-fog uppercase">
          Retail Intelligence · all figures from processed marts — no mock data.
        </footer>
      </main>
    </div>
  );
}

export default function App() {
  return <Shell />;
}
