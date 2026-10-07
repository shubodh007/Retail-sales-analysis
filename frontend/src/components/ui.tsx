import type { ReactNode } from 'react';
import { SpotlightCard } from './bits/SpotlightCard';

export function Button({ children, disabled, type = 'button', onClick }: { children: ReactNode; disabled?: boolean; type?: 'button' | 'submit'; onClick?: () => void }) {
  return (
    <button type={type} disabled={disabled} onClick={onClick} className="app-button">
      <span>{children}</span>
    </button>
  );
}

export function Card({ children, title, aside, className = '' }: { children: ReactNode; title?: string; aside?: ReactNode; className?: string }) {
  return (
    <SpotlightCard className={`app-card ${className}`}>
      {title && (
        <header className="app-card__header">
          <div>
            <p className="eyebrow">{title}</p>
          </div>
          {aside}
        </header>
      )}
      <div className="app-card__body">{children}</div>
    </SpotlightCard>
  );
}

export function Badge({ children, tone = 'steel' }: { children: ReactNode; tone?: 'steel' | 'safety' | 'moss' | 'brass' }) {
  const tones = { steel: 'badge--blue', safety: 'badge--coral', moss: 'badge--sage', brass: 'badge--butter' };
  return <span className={`badge ${tones[tone]}`}>{children}</span>;
}

export function Spinner({ label = 'Working…' }: { label?: string }) {
  return (
    <div role="status" aria-live="polite" className="status-row">
      <span className="spinner" aria-hidden />
      <span>{label}</span>
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="state state--error">
      <div className="state__icon">!</div>
      <div className="min-w-0 flex-1"><strong>Something needs attention</strong><p>{message}</p></div>
      {onRetry && <Button onClick={onRetry}>Try again</Button>}
    </div>
  );
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return <div className="state state--empty"><div className="state__icon">○</div><div><strong>{title}</strong>{hint && <p>{hint}</p>}</div></div>;
}

export function Stat({ label, value, mono = true }: { label: string; value: ReactNode; mono?: boolean }) {
  return (
    <div className="metric-mini">
      <p>{label}</p>
      <strong className={mono ? 'tnum' : ''}>{value}</strong>
    </div>
  );
}

export function Insight({ title, children, tone = 'sage' }: { title: string; children: ReactNode; tone?: 'sage' | 'blue' | 'plum' | 'coral' }) {
  return <div className={`insight insight--${tone}`}><span className="insight__mark">✦</span><div><strong>{title}</strong><p>{children}</p></div></div>;
}
