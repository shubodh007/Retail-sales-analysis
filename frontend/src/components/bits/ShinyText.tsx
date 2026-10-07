import { useReducedMotion } from 'motion/react';
import type { ReactNode } from 'react';
import * as m from 'motion/react-m';

export function ShinyText({ children }: { children: ReactNode }) {
  const reduce = useReducedMotion();
  return (
    <m.span
      animate={reduce ? undefined : { backgroundPosition: ['120% 0', '-20% 0'] }}
      transition={reduce ? undefined : { duration: 2.8, repeat: Infinity, ease: 'linear', repeatDelay: 1.4 }}
      className="shiny-text"
    >
      {children}
    </m.span>
  );
}
