# Forecasting engine (Phase 3)

## Contract

One interface (`app/forecast/interface.py:ForecastResult`), four estimators
(`app/forecast/estimators.py`), selected by lowest validation WAPE — never
hardcoded. Horizons: 7 / 30 / 90 days. Target: daily revenue.
Contexts: global (sales_daily), product (product_daily), country
(country_daily); a context trains only with >= max(60, 2*horizon) points.

## Validation

Chronological expanding folds (2 when history allows, else 1 trailing
holdout). No shuffling. Final forecast refits on full history. Lags
(1/7/14/28) and rolling means/stds (7/14/30) sit on the lag-1 series;
calendar parts (dow/month/weekend) + trend index are the only exogeneous
inputs. Leakage tests in `tests/test_forecast.py` pin the boundary behavior.

## Metrics

MAE, RMSE always. MAPE only when no |actual| < 1.0, else `mape_status =
unstable_zero_actuals` with sMAPE + WAPE reported. Selection metric: WAPE.

## Intervals

- ARIMA: analytic 95% (`get_forecast().conf_int`).
- Prophet: analytic uncertainty 90%.
- RF/XGBoost: empirical residual band (p10–p90 of out-of-fold residuals).
  Labeled as such in API (`interval_type`) and UI — never presented as
  analytic confidence.

## Jobs

`POST /forecasts/runs` → 202 + group id; training runs in a BackgroundTasks
worker thread, persisting to `forecast_groups / forecast_runs /
forecast_points`. Frontend polls `GET /runs/{id}`; `GET /compare/{id}` is the
evidence table. No celery/redis in Phase 3 by design (single-node training).

## Timezone

Spark/JVM zones are GMT (the local pgserver build has no tzdata and rejects
`TimeZone=UTC`; GMT is instant-identical). Bounds cross into Python as UTC
strings only. Managed Postgres deployments are unaffected.
