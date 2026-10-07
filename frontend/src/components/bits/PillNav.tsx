import { Link, useLocation } from 'react-router-dom';
import * as m from 'motion/react-m';

export function PillNav({ items, variant = 'top' }: {
  items: { to: string; label: string; icon?: string }[];
  variant?: 'top' | 'sidebar';
}) {
  const loc = useLocation();
  return (
    <nav className={`pill-nav pill-nav--${variant}`} aria-label="Primary navigation">
      {items.map((item) => {
        const active = loc.pathname === item.to || loc.pathname.startsWith(`${item.to}/`);
        return (
          <Link key={item.to} to={item.to} className={`pill-nav__item ${active ? 'is-active' : ''}`}>
            {active && <m.span layoutId="pill-active" className="pill-nav__pill" transition={{ type: 'spring', stiffness: 480, damping: 34 }} />}
            {item.icon && <span className="pill-nav__icon" aria-hidden>{item.icon}</span>}
            <span className="pill-nav__label">{item.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
