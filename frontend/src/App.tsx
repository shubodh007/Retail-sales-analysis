import { lazy, Suspense, useMemo } from 'react';
import { Link, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { LazyMotion, MotionConfig } from 'motion/react';
import { api } from './lib/api';
import { useActiveDataset } from './lib/useDataset';
import { PillNav } from './components/bits/PillNav';
import { AnimatedContent } from './components/bits/AnimatedContent';
import { Spinner } from './components/ui';

const Overview = lazy(() => import('./pages/Overview').then((m) => ({ default: m.Overview })));
const Sales = lazy(() => import('./pages/Sales').then((m) => ({ default: m.Sales })));
const Products = lazy(() => import('./pages/Products').then((m) => ({ default: m.Products })));
const Regions = lazy(() => import('./pages/Regions').then((m) => ({ default: m.Regions })));
const Customers = lazy(() => import('./pages/Customers').then((m) => ({ default: m.Customers })));
const Forecast = lazy(() => import('./pages/Forecast').then((m) => ({ default: m.Forecast })));
const Anomalies = lazy(() => import('./pages/Anomalies').then((m) => ({ default: m.Anomalies })));
const DataLab = lazy(() => import('./pages/DataLab').then((m) => ({ default: m.DataLab })));
const System = lazy(() => import('./pages/System').then((m) => ({ default: m.System })));

const NAV = [
  { to: '/overview', label: 'Overview', icon: '⌂' },
  { to: '/sales', label: 'Sales', icon: '↗' },
  { to: '/products', label: 'Products', icon: '▦' },
  { to: '/regions', label: 'Markets', icon: '◌' },
  { to: '/customers', label: 'Customers', icon: '◎' },
  { to: '/forecast', label: 'Forecast', icon: '✦' },
  { to: '/anomalies', label: 'Anomalies', icon: '!' },
  { to: '/data-lab', label: 'Data Lab', icon: '⇧' },
  { to: '/system', label: 'System', icon: '◈' },
];

function DatasetBadge() {
  const { dataset } = useActiveDataset();
  if (!dataset) return <span className="dataset-mini">No dataset selected</span>;
  return (
    <Link to="/data-lab" className="dataset-mini" title={`${dataset.filename} · ${dataset.row_count.toLocaleString()} rows`}>
      <span className="dataset-mini__dot" />
      <span>{dataset.filename}</span>
    </Link>
  );
}

function MobileTopbar({ healthText }: { healthText: string }) {
  const location = useLocation();
  const current = useMemo(() => NAV.find((item) => location.pathname.startsWith(item.to)) ?? NAV[0], [location.pathname]);
  return (
    <div className="mobile-topbar">
      <Link to="/overview" className="brand" aria-label="Retail Intelligence home">
        <span className="brand__mark" aria-hidden />
        <span className="brand__title">Retail Intelligence</span>
      </Link>
      <div className="mobile-topbar__status">
        <span className="health-dot">{healthText}</span>
        <span className="mobile-current">{current.label}</span>
      </div>
    </div>
  );
}

function Sidebar({ healthText }: { healthText: string }) {
  return (
    <aside className="app-sidebar">
      <div className="sidebar__top">
        <Link to="/overview" className="brand" aria-label="Retail Intelligence home">
          <span className="brand__mark" aria-hidden />
          <span>
            <span className="brand__title">Retail Intelligence</span>
            <span className="brand__sub block">Sales · Forecasting · Insights</span>
          </span>
        </Link>
      </div>
      <div className="sidebar__label">Workspace</div>
      <PillNav items={NAV} variant="sidebar" />
      <div className="sidebar__bottom">
        <DatasetBadge />
        <div className="sidebar__health">
          <span className="health-dot">{healthText}</span>
          <span>API + database</span>
        </div>
        <Link to="/data-lab" className="upload-cta">
          <span className="upload-cta__icon">＋</span>
          <span><strong>Add dataset</strong><small>CSV · validation · marts</small></span>
        </Link>
      </div>
    </aside>
  );
}

function Shell() {
  const health = useQuery({ queryKey: ['health'], queryFn: api.health, staleTime: 15_000, retry: 1 });
  const healthText = health.data?.db ? 'Live' : health.isPending ? 'Checking' : 'Offline';
  return (
    <LazyMotion features={() => import('motion/react').then((m) => m.domMax)} strict>
      <MotionConfig reducedMotion="user" transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}>
        <div className="app-shell">
          <Sidebar healthText={healthText} />
          <MobileTopbar healthText={healthText} />
          <div className="app-content">
            <header className="app-topbar">
              <div className="app-topbar__search" role="search">
                <span aria-hidden>⌕</span>
                <span>Search sales, products, markets…</span>
                <kbd>⌘ K</kbd>
              </div>
              <div className="app-topbar__right">
                <span className="health-dot">{healthText}</span>
                <DatasetBadge />
                <span className="avatar" aria-label="Retail Intelligence user">RI</span>
              </div>
            </header>
            <main className="app-main">
              <Suspense fallback={<AnimatedContent><Spinner label="Opening workspace…" /></AnimatedContent>}>
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
              </Suspense>
            </main>
            <footer className="app-footer">
              <span>Retail Intelligence</span>
              <span>Every figure comes from the processed dataset.</span>
              <Link to="/system">How it works →</Link>
            </footer>
          </div>
        </div>
      </MotionConfig>
    </LazyMotion>
  );
}

export default function App() { return <Shell />; }
