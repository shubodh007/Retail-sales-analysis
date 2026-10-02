/** Minimal industrial primitives. No component library in Phase 1 by design
 *  (shadcn/radix arrives when a real need — dialog, select, tabs — appears).
 */
import type { ReactNode } from 'react';

export function Button({
  children,
  disabled,
  type = 'button',
  onClick,
}: {
  children: ReactNode;
  disabled?: boolean;
  type?: 'button' | 'submit';
  onClick?: () => void;
}) {
  return (
    <button
      type={type}
      disabled={disabled}
      onClick={onClick}
      className="inline-flex items-center gap-2 bg-ink px-4 py-2 font-mono text-xs tracking-widest text-paper uppercase transition-colors hover:bg-graphite disabled:cursor-not-allowed disabled:opacity-40"
    >
      {children}
    </button>
  );
}

export function Card({ children, title, aside }: { children: ReactNode; title?: string; aside?: ReactNode }) {
  return (
    <section className="border border-ink/15 bg-paper">
      {title && (
        <header className="flex items-center justify-between border-b border-ink/15 px-4 py-2">
          <h2 className="font-mono text-[11px] tracking-[0.2em] text-fog uppercase">{title}</h2>
          {aside}
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

export function Badge({ children, tone = 'steel' }: { children: ReactNode; tone?: 'steel' | 'safety' | 'moss' | 'brass' }) {
  const tones: Record<string, string> = {
    steel: 'bg-steel/15 text-fog',
    safety: 'bg-safety/15 text-ember',
    moss: 'bg-moss/15 text-pine',
    brass: 'bg-brass/20 text-ink',
  };
  return (
    <span className={`inline-block px-2 py-0.5 font-mono text-[11px] tracking-wider uppercase ${tones[tone]}`}>
      {children}
    </span>
  );
}

export function Spinner({ label = 'Working…' }: { label?: string }) {
  return (
    <div role="status" aria-live="polite" className="flex items-center gap-3 py-6">
      <span className="inline-block h-4 w-4 animate-spin border-2 border-steel border-t-safety" aria-hidden />
      <span className="font-mono text-xs tracking-wider text-fog uppercase">{label}</span>
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="border border-safety/50 bg-safety/5 p-4">
      <p className="font-mono text-xs tracking-wider text-ember uppercase">Failed</p>
      <p className="mt-1 text-sm">{message}</p>
      {onRetry && (
        <div className="mt-3">
          <Button onClick={onRetry}>Retry</Button>
        </div>
      )}
    </div>
  );
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="border border-dashed border-steel/50 p-8 text-center">
      <p className="font-mono text-xs tracking-[0.2em] text-fog uppercase">{title}</p>
      {hint && <p className="mt-2 text-sm text-ink/70">{hint}</p>}
    </div>
  );
}

export function Stat({ label, value, mono = true }: { label: string; value: ReactNode; mono?: boolean }) {
  return (
    <div className="border-l-2 border-ink/20 pl-3">
      <p className="font-mono text-[11px] tracking-[0.2em] text-fog uppercase">{label}</p>
      <p className={`mt-1 text-xl ${mono ? 'tnum font-mono' : ''}`}>{value}</p>
    </div>
  );
}
