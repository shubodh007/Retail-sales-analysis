import { useReducedMotion } from 'motion/react';
import * as m from 'motion/react-m';

export function BlurText({ text, className = '' }: { text: string; className?: string }) {
  const reduce = useReducedMotion();
  return (
    <m.span
      initial={reduce ? false : { opacity: 0, filter: 'blur(10px)', y: 8 }}
      animate={{ opacity: 1, filter: 'blur(0px)', y: 0 }}
      transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1] }}
      className={className}
    >
      {text}
    </m.span>
  );
}
