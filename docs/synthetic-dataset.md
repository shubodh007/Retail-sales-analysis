# Synthetic dataset (testing / fallback ONLY)

## Rule

Synthetic data is NEVER presented as real-world data. In the UI it is
labeled `SYNTHETIC — for pipeline testing`. In reports it is cited as
generated, with seed.

## What it is

`datasets/samples/retail_synthetic.csv`: deterministic daily retail sample
(2022-01-01 – 2023-12-31, 12 products × 3 categories × 4 regions),
weekly seasonality + annual seasonality + trend + Gaussian noise, plus
three injected anomalies (documented below) so anomaly/forecast work has
ground truth in tests.

## Reproduce

```powershell
cd datasets/samples
..\..\backend\.venv\Scripts\python.exe make_synthetic.py
```

Seed `42` (stdlib `random` only, no numpy dependency). Output columns match
the UCI layout (`InvoiceNo,StockCode,Description,Quantity,InvoiceDate,
UnitPrice,CustomerID,Country` + `Category`) so the same mapping path is tested.

## Injected anomalies (ground truth)

- `2022-11-25` region North, product P04: quantity ×8 (promo spike).
- `2023-02-14`: all regions quantity ×0.15 (outage dip).
- `2023-07-01` – `2023-07-07`: unit price of P09 halved (clearance).

## Used by

- backend tests (mini inline CSVs, same schema family)
- Data Lab manual smoke test without downloading the 43 MB UCI file
- offline fallback when the real dataset is unavailable
