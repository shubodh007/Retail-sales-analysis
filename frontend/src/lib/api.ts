/** Single API client. No duplicate fetch wrappers. */
export interface Dataset {
  id: string;
  filename: string;
  status: string;
  row_count: number;
  date_from: string | null;
  date_to: string | null;
  schema_map: Record<string, string>;
  error: string | null;
  created_at: string;
}

export interface DatasetStatus {
  id: string;
  status: string;
  error: string | null;
  row_count: number;
}

export interface DatasetProfile extends Dataset {
  profile: {
    row_count: number;
    curated_count: number;
    duplicate_rows: number;
    unparseable_dates: number;
    unparseable_date_pct: number;
    date_from: string | null;
    date_to: string | null;
    span_days: number | null;
    null_pct: Record<string, number>;
    cardinality: Record<string, number>;
    numeric_summary: Record<string, { min: number | null; max: number | null; mean: number | null; non_numeric: number }>;
    columns: string[];
    parquet_path: string;
    quality: {
      accepted: number; quarantined: number; quarantine_reasons: Record<string, number>;
      cancellations: number; cancel_abs_revenue: number; duplicates: number;
    };
    marts?: Record<string, number>;
    anomalies?: Record<string, number>;
  };
  parquet_path: string;
}

export interface Overview {
  dataset: { id: string; filename: string; capabilities: Record<string, boolean> };
  totals: { revenue: number; qty: number; orders: number; products: number };
  daily: { date: string; revenue: number; qty: number; orders: number }[];
  top_products: { stockcode: string; description: string; revenue: number; qty: number }[];
  top_countries: { country: string; revenue: number; qty: number }[];
  quality: {
    accepted: number; quarantined: number; quarantine_reasons: Record<string, number>;
    cancellations: number; cancel_abs_revenue: number; duplicates: number;
  };
}

export interface TrendPoint {
  date: string;
  revenue: number;
  qty: number;
  orders: number;
}

export interface ProductItem {
  stockcode: string;
  description: string;
  qty: number;
  revenue: number;
  orders: number;
  first_date: string | null;
  last_date: string | null;
}

export interface FcRun {
  model: string;
  status: string;
  metrics: { mae: number | null; rmse: number | null; wape: number | null; smape: number | null; mape: number | null };
  mape_status: string;
  interval_type: string;
  config: Record<string, unknown>;
  train_from: string;
  train_to: string;
  val_from: string;
  val_to: string;
  duration_s: number;
  error: string | null;
  history: { date: string; actual: number }[];
  validation: { date: string; actual: number; predicted: number }[];
  forecast: { date: string; predicted: number; lower: number | null; upper: number | null }[];
}

export interface FcGroup {
  id: string;
  status: string;
  target: string;
  context_type: string;
  context_id: string | null;
  horizon: number;
  best_model: string | null;
  selection_metric: string;
  error: string | null;
  created_at: string | null;
  runs: FcRun[];
}

export interface FcCompare {
  group_id: string;
  status: string;
  selection: { metric: string; best_model: string | null; criterion: string };
  models: { model: string; status: string; metrics: FcRun['metrics']; mape_status: string; duration_s: number }[];
}

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown) {
    super(typeof detail === 'string' ? detail : `request failed (${status})`);
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  // VITE_API_BASE_URL points at the FastAPI origin in production
  // (e.g. https://retail-intel-api.onrender.com). Empty = same origin,
  // which is the local dev setup (Vite proxies /api -> 127.0.0.1:8000).
  const base = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '');
  const res = await fetch(`${base}${path}`, init);
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = body && typeof body === 'object' && 'detail' in body ? body.detail : body;
    throw new ApiError(res.status, detail ?? res.statusText);
  }
  return body as T;
}

export const api = {
  health: () => request<{ status: string; db: boolean }>('/api/v1/health'),
  datasets: () => request<Dataset[]>('/api/v1/datasets'),
  datasetStatus: (id: string) => request<DatasetStatus>(`/api/v1/datasets/${id}/status`),
  profile: (id: string) => request<DatasetProfile>(`/api/v1/datasets/${id}/profile`),
  overview: (id: string) => request<Overview>(`/api/v1/analytics/overview?dataset_id=${id}`),
  trend: (id: string, grain: 'daily' | 'monthly', country?: string) =>
    request<{ grain: string; points: TrendPoint[] }>(
      `/api/v1/analytics/sales/trend?dataset_id=${id}&grain=${grain}${country ? `&country=${encodeURIComponent(country)}` : ''}`,
    ),
  products: (id: string, params: { sort?: string; limit?: number; offset?: number; search?: string } = {}) => {
    const q = new URLSearchParams({ dataset_id: id });
    for (const [k, v] of Object.entries(params)) if (v !== undefined) q.set(k, String(v));
    return request<{ total: number; limit: number; offset: number; items: ProductItem[] }>(
      `/api/v1/analytics/products?${q}`,
    );
  },
  productTrend: (id: string, stockcode: string) =>
    request<{ stockcode: string; points: { date: string; revenue: number; qty: number }[] }>(
      `/api/v1/analytics/products/${encodeURIComponent(stockcode)}/trend?dataset_id=${id}`,
    ),
  geography: (id: string) =>
    request<{ countries: { country: string; revenue: number; qty: number; orders: number }[] }>(
      `/api/v1/analytics/geography?dataset_id=${id}`,
    ),
  fcCreate: (body: { dataset_id: string; target?: string; context_type: string; context_id?: string | null; horizon: number; models?: string[] | null }) =>
    request<{ id: string; status: string }>('/api/v1/forecasts/runs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  fcGroup: (gid: string) => request<FcGroup>(`/api/v1/forecasts/runs/${gid}`),
  fcCompare: (gid: string) => request<FcCompare>(`/api/v1/forecasts/compare/${gid}`),
  fcCapabilities: (id: string, horizon = 30) =>
    request<{ horizons: number[]; models: string[]; selection_metric: string; global_points: number; history?: { from: string; to: string }; insufficient?: string }>(
      `/api/v1/forecasts/capabilities?dataset_id=${id}&horizon=${horizon}`,
    ),
  anomalies: (id: string, dimension = 'global', key?: string, limit = 100, offset = 0) => {
    const q = new URLSearchParams({ dataset_id: id, dimension, limit: String(limit), offset: String(offset) });
    if (key) q.set('key', key);
    return request<{ total: number; limit: number; offset: number; method: string; language: string; items: { date: string; dimension: string; key: string; observed: number; expected: number; deviation: number }[] }>(
      `/api/v1/analytics/anomalies?${q}`,
    );
  },
  anomaliesSummary: (id: string) =>
    request<{ by_dimension: Record<string, number>; latest: { date: string; dimension: string; key: string; observed: number; deviation: number }[] }>(
      `/api/v1/analytics/anomalies/summary?dataset_id=${id}`,
    ),
  rfm: (id: string) =>
    request<{
      segments: { segment: string; customers: number; revenue: number; orders: number; revenue_share: number }[];
      customers: { customer_id: string; country: string; orders: number; revenue: number; recency_days: number; r: number; f: number; m: number; segment: string; last_date: string | null }[];
      customers_total: number;
      methodology: Record<string, string>;
    }>(`/api/v1/analytics/customers/rfm?dataset_id=${id}`),
  upload: (file: File): Promise<DatasetStatus> => {
    const form = new FormData();
    form.append('file', file);
    // 202 Accepted: Spark ingestion continues in the background; poll
    // api.datasetStatus(id) until status is ready | failed.
    return request<DatasetStatus>('/api/v1/datasets/upload', { method: 'POST', body: form });
  },
};

export function formatApiError(e: unknown): string {
  if (e instanceof ApiError) {
    if (typeof e.detail === 'string') return e.detail;
    if (e.detail && typeof e.detail === 'object' && 'message' in e.detail) {
      const { message, errors } = e.detail as { message: string; errors?: string[] };
      return errors?.length ? `${message}: ${errors.join('; ')}` : message;
    }
    return `request failed (${e.status})`;
  }
  return e instanceof Error ? e.message : 'unexpected error';
}
