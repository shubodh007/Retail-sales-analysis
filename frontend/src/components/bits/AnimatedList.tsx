import { useReducedMotion } from 'motion/react';
import * as m from 'motion/react-m';
import type { ReactNode } from 'react';

export function AnimatedList({ items }: { items: ReactNode[] }) {
  const reduce = useReducedMotion();
  return (
    <div className="animated-list">
      {items.map((item, index) => (
        <m.div
          key={index}
          initial={reduce ? false : { opacity: 0, x: -8 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.3, delay: index * 0.055 }}
        >
          {item}
        </m.div>
      ))}
    </div>
  );
}
