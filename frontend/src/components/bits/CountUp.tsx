/**
 * Vendored from React Bits (MIT + Commons Clause), TS-TW variant, adapted:
 * - removed 'use client' directive (not a Next app)
 * - default duration shortened for data-UI cadence
 * Source: https://reactbits.dev/text-animations/count-up
 */
import { useInView, useMotionValue, useSpring } from 'motion/react';
import { useCallback, useEffect, useRef } from 'react';

interface CountUpProps {
  to: number;
  from?: number;
  direction?: 'up' | 'down';
  delay?: number;
  duration?: number;
  className?: string;
  startWhen?: boolean;
  separator?: string;
  decimals?: number;
  prefix?: string;
  suffix?: string;
}

export default function CountUp({
  to,
  from = 0,
  direction = 'up',
  delay = 0,
  duration = 1.2,
  className = '',
  startWhen = true,
  separator = ',',
  decimals,
  prefix = '',
  suffix = '',
}: CountUpProps) {
  const ref = useRef<HTMLSpanElement>(null);
  const reduceMotion =
    typeof window !== 'undefined' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const motionValue = useMotionValue(direction === 'down' ? to : from);
  const springValue = useSpring(motionValue, {
    damping: reduceMotion ? 1000 : 20 + 40 * (1 / duration),
    stiffness: reduceMotion ? 1000 : 100 * (1 / duration),
  });
  const isInView = useInView(ref, { once: true, margin: '0px' });

  const formatValue = useCallback(
    (latest: number) => {
      const dec =
        decimals ??
        (() => {
          for (const n of [from, to]) {
            const s = n.toString();
            if (s.includes('.') && parseInt(s.split('.')[1], 10) !== 0) return s.split('.')[1].length;
          }
          return 0;
        })();
      const out = Intl.NumberFormat('en-US', {
        useGrouping: !!separator,
        minimumFractionDigits: dec,
        maximumFractionDigits: dec,
      }).format(latest);
      return `${prefix}${separator ? out : out.replace(/,/g, '')}${suffix}`;
    },
    [decimals, from, to, separator, prefix, suffix],
  );

  useEffect(() => {
    if (ref.current) ref.current.textContent = formatValue(direction === 'down' ? to : from);
  }, [from, to, direction, formatValue]);

  useEffect(() => {
    if (isInView && startWhen) {
      const t = setTimeout(() => motionValue.set(direction === 'down' ? from : to), delay * 1000);
      return () => clearTimeout(t);
    }
  }, [isInView, startWhen, motionValue, direction, from, to, delay]);

  useEffect(() => {
    const unsub = springValue.on('change', (latest: number) => {
      if (ref.current) ref.current.textContent = formatValue(latest);
    });
    return () => unsub();
  }, [springValue, formatValue]);

  return <span className={className} ref={ref} />;
}
