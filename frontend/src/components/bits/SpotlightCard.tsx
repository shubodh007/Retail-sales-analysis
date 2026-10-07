import { useRef, type ReactNode, type MouseEvent } from 'react';

export function SpotlightCard({ children, className = '' }: { children: ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const move = (event: MouseEvent<HTMLDivElement>) => {
    const el = ref.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    el.style.setProperty('--spot-x', `${event.clientX - r.left}px`);
    el.style.setProperty('--spot-y', `${event.clientY - r.top}px`);
  };
  return (
    <div ref={ref} onMouseMove={move} className={`spotlight-card ${className}`}>
      {children}
    </div>
  );
}
