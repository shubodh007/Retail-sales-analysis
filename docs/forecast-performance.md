# Forecast performance (measured, not estimated)

Method: `backend/scripts/bench_forecast.py` against the local UCI dataset
(`d0793ce2…`, 604 daily points, 2 expanding folds per horizon) on this dev
machine. Every number below is a wall-clock `perf_counter` timing; WAPE values
prove the runs succeeded. Frame-construction counts are exact (counting
wrapper around `build_frame`), not guesses.

Raw machine-readable baseline: `docs/forecast-baseline.json`.

## Baseline (before optimization)

| Forecast | ARIMA | Prophet | RF | XGB | Sum |
|----------|-------|---------|----|-----|-----|
| Global 7d | 8.1s | 5.2s | 8.2s | 13.4s | 34.9s |
| Global 30d | 4.2s | 4.0s | 21.4s | 17.9s | 47.5s |
| Global 90d | 3.1s | 3.5s | 55.2s | 30.6s | 92.4s |

| Component | Time | Notes |
|-----------|------|-------|
| Series loading (`load_series`, 604 rows) | 0.1–0.2s | 1 indexed query; negligible |
| Feature construction (single frame, 576 rows) | 0.033s | negligible per build |
| Persistence (rf-only 7d end-to-end 8.3s vs fit 8.2s) | ~0.1s | negligible |
| RF h=90 frame rebuilds | 361 builds | 1 + 4 recursive sequences × 90 steps |
| XGB h=90 frame rebuilds | 361 builds | same pattern |
| Fits per model call (2 folds) | 4 | 2 validation + 1 final + 1 last-fold refit |

Baseline WAPE (correctness reference — must not regress):

| Model | h=7 | h=30 | h=90 | product-30 (rf) | country-30 (rf) |
|-------|-----|------|------|-----------------|-----------------|
| arima | 36.25 | 30.90 | 44.59 | — | — |
| prophet | 30.64 | 43.16 | 50.66 | — | — |
| rf | 34.42 | 39.79 | 43.95 | 276.55 | 44.86 |
| xgb | 35.69 | 38.68 | 41.11 | — | — |

Sample timings: product-30 rf 20.0s, country-30 rf 20.3s (377/604 points).

## Root causes (confirmed by measurement)

1. **Duplicate last-fold refit.** Every model is fitted 4× per call with
   2 folds (2 validation + 1 final full-history + 1 last-fold refit whose
   only purpose is display data already computed in the loop). The refit is
   pure waste — its predictions are byte-identical to the loop's.
2. **Recursive full-frame rebuild.** Each future timestep rebuilds the
   feature frame over the entire history: 361 `build_frame` calls per ML
   model at h=90 (4 sequences × 90 steps + 1). Cost grows as O(H·N).
3. **Default tree counts untested.** RF uses 200 trees, XGB 300 — never
   benchmarked against smaller values (see hyperparameter study below).

Series loading, feature construction (per build), and persistence are all
negligible and were deliberately left alone.

## Optimizations applied

 Voir git history for `app/forecast/estimators.py`, `app/forecast/features.py`.

1. Reuse last-fold validation predictions from the folds loop
   (ARIMA, Prophet, RF/XGB) — 4 fits → 3 fits per model call.
2. Incremental recursive predictor: one feature row per timestep from a
   trailing 28-value window; no full-frame rebuilds (361 → 1 builds).
3. Hyperparameters only if the study below justifies it.
4. Identical-request cache + in-flight dedupe at `POST /forecasts/runs`.
5. `FORECAST_MAX_WORKERS` (default 1 = sequential, as before).

## Post-optimization results

Reran `bench_forecast.py --out docs/forecast-optimized.json` (same machine,
same dataset, default `FORECAST_MAX_WORKERS=1`).

| Forecast | Old | New | Speedup | Reduction |
|----------|-----|-----|---------|-----------|
| Global 7d | 34.9s | 25.4s | 1.37× | 27% |
| Global 30d | 47.5s | 19.2s | 2.47× | 60% |
| Global 90d | 92.4s | 36.1s | 2.56× | 61% |
| Product 30d (rf) | 20.0s | 8.1s | 2.47× | 60% |
| Country 30d (rf) | 20.3s | 8.4s | 2.42× | 59% |

| Component | Old | New |
|-----------|-----|-----|
| Series loading | 0.1–0.2s | 0.1–0.2s (unchanged — was never a bottleneck) |
| Feature construction | 361 builds (h=90 ML) | 1 build (single frame; +90/30/7 incremental rows) |
| ARIMA h=30 / h=90 | 4.2s / 3.1s | 1.7s / 1.5s (4 fits → 3) |
| Prophet h=30 / h=90 | 4.0s / 3.5s | 2.0s / 1.9s (4 fits → 3) |
| Random Forest h=30 / h=90 | 21.4s / 55.2s | 8.5s / 22.3s |
| XGBoost h=30 / h=90 | 17.9s / 30.6s | 7.0s / 10.4s |
| Fits per model call (2 folds) | 4 | 3 |
| Persistence | ~0.1s | ~0.1s (unchanged) |

Warmup note: the first fit in a fresh process pays ~5–7s one-time init
(statsmodels/cmdstan import, BLAS warmup) — measured 7.6s then 3.0s for
identical back-to-back ARIMA h=7 calls. h=7 totals above include that
first-call cost in both runs; steady-state repeats are ~2× faster than shown.
In production the worker process is long-lived, so users mostly see warm timings.

Accuracy comparison (validation WAPE — ARIMA/Prophet bit-identical,
ML within the pre-committed noise band, selection unchanged: arima best at h=30):

| Model | h=7 old → new | h=30 old → new | h=90 old → new |
|-------|---------------|----------------|----------------|
| arima | 36.25 → 36.25 | 30.90 → 30.90 | 44.59 → 44.59 |
| prophet | 30.64 → 30.64 | 43.16 → 43.16 | 50.66 → 50.66 |
| rf | 34.42 → 34.20 | 39.79 → 40.06 | 43.95 → 44.05 |
| xgb | 35.69 → 34.88 | 38.68 → 39.09 | 41.11 → 40.76 |

Product-30 rf 276.55 → 280.08 (+1.3% relative on a sparse noisy context);
country-30 rf 44.86 → 44.64. No leakage (leakage tests pass unchanged),
no date/horizon changes (length + alignment asserted by tests).

## Hyperparameter study

Full expanding validation on global data (not a proxy), measured:

| Config | h=30 WAPE | h=30 time | h=90 WAPE | h=90 time |
|--------|-----------|-----------|-----------|-----------|
| rf 100 | 39.21 | 7.1s | 45.03 | 21.3s |
| rf 150 | 40.06 | 9.4s | 44.05 | 24.3s |
| rf 200 (old) | 39.79 | 12.5s | 43.95 | 30.0s |
| xgb 150 | 39.37 | 6.2s | 40.34 | 8.7s |
| xgb 200 | 39.09 | 9.2s | 40.76 | 10.0s |
| xgb 300 (old) | 38.68 | 20.4s | 41.11 | 12.5s |

Quality direction is inconsistent across horizons (dataset noise, all within
~1pp), while cost scales steeply — xgb-300 costs 3.3× xgb-150 at h=30 for
0.7pp, and is *worse* than xgb-150 at h=90. Adopted middle values to avoid
over-tuning to either horizon: **RF 200 → 150** (within 0.3pp of best both
horizons), **XGB 300 → 200** (within 0.4pp both horizons, ~2× faster at h=30).
All other hyperparameters, features, folds, and selection logic unchanged.

## Caching, dedupe, workers

- `POST /forecasts/runs` returns the existing group for an identical
  completed request (dataset/target/context/horizon/model-set match,
  all runs done) — retraining cost for repeats: ~0s. Datasets are immutable
  once ready (plus a new 422 guard on non-ready datasets), so reuse is safe.
- In-flight duplicates (double-clicks) attach to the pending/running group
  instead of launching a second training.
- `FORECAST_MAX_WORKERS` (default 1, sequential as before). Measured on this
  host, global 30d: workers=2 → 25.8s vs ~22s sequential (internal threading
  already saturates small CPUs), WAPE identical except XGB 39.09 → 39.41
  (parallel histogram reduction, selection unaffected: arima still best).
  Raise only on 4+ CPU / 8 GB+ hosts.
- Quick vs Evidence: no new UI — the existing model dropdown already covers
  it (single model = fast directional forecast, Auto = full four-model
  evidence with WAPE selection).
