import { describe, expect, it } from 'vitest';
import { forecastLink, productsLink, regionsLink, salesLink } from './links';

describe('cross-page links', () => {
  it('carries country into sales', () => {
    expect(salesLink('United Kingdom')).toBe('/sales?country=United%20Kingdom');
    expect(salesLink()).toBe('/sales');
  });
  it('carries context into forecast', () => {
    expect(forecastLink('country', 'France')).toBe('/forecast?context=country&context_id=France');
    expect(forecastLink('product', '85123A')).toBe('/forecast?context=product&context_id=85123A');
    expect(forecastLink('global')).toBe('/forecast?context=global');
  });
  it('carries search into products and country into regions', () => {
    expect(productsLink('mug')).toBe('/products?search=mug');
    expect(productsLink()).toBe('/products');
    expect(regionsLink('EIRE')).toBe('/regions?country=EIRE');
    expect(regionsLink()).toBe('/regions');
  });
  it('never invents dimensions', () => {
    expect(forecastLink('global')).not.toContain('context_id');
  });
});
