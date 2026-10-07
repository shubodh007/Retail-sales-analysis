import { AnimatedContent } from './bits/AnimatedContent';
import type { ReactNode } from 'react';

export function Reveal({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <AnimatedContent className={className}>{children}</AnimatedContent>;
}
