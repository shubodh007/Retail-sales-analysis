/**
 * Section entrance without a second animation engine.
 * React Bits FadeContent was evaluated and rejected: it pulls gsap, and our
 * one engine is motion (CountUp). This IO + CSS reveal covers the need.
 */
import { useEffect, useRef, useState, type ReactNode } from 'react';

export function Reveal({ children, className = '' }: { children: ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [shown, setShown] = useState(
    () =>
      typeof window === 'undefined' ||
      window.matchMedia('(prefers-reduced-motion: reduce)').matches,
  );

  useEffect(() => {
    if (shown) return;
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          setShown(true);
          io.disconnect();
        }
      },
      { threshold: 0.08 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [shown]);

  return (
    <div
      ref={ref}
      className={`transition-all duration-500 ease-out ${shown ? 'translate-y-0 opacity-100' : 'translate-y-3 opacity-0'} ${className}`}
    >
      {children}
    </div>
  );
}
