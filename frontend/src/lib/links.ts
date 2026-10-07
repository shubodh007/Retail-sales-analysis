/** Cross-page links. Pure functions (vitest-covered); no state library. */

export function salesLink(country?: string): string {
  return country ? `/sales?country=${encodeURIComponent(country)}` : '/sales';
}

export function forecastLink(context: string, context_id?: string | null): string {
  const q = new URLSearchParams({ context });
  if (context_id) q.set('context_id', context_id);
  return `/forecast?${q}`;
}

export function productsLink(search?: string): string {
  return search ? `/products?search=${encodeURIComponent(search)}` : '/products';
}

export function regionsLink(country?: string): string {
  return country ? `/regions?country=${encodeURIComponent(country)}` : '/regions';
}
