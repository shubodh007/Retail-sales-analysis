# Data-quality policy (deterministic, no silent drops)

Applies to every CSV processed by `app/services/profiling.py`. Order matters;
counts reconcile as:

`raw_rows = duplicates + quarantined + cancellations + accepted`

## Steps (in order)

1. **Exact duplicates** — whole-row duplicates removed, counted as `duplicates`.
2. **Date parse** — `InvoiceDate` parsed against known formats (ISO first).
   Unparseable → `quarantine:bad_date`.
3. **Product presence** — empty `StockCode` → `quarantine:missing_product`.
4. **Numerics** — `Quantity` must cast to int, `UnitPrice` must cast to double
   and be **> 0**. Failures → `quarantine:bad_quantity` / `quarantine:bad_price`.
   Zero/negative prices are invalid (freebies are not revenue); negative
   quantities are handled as cancellations below, not as errors.
5. **Cancellations/returns** — `InvoiceNo` starting with `C` (case-insensitive)
   OR `Quantity < 0` → `cancellations`. Written to a separate `cancel/`
   parquet, excluded from revenue marts, reported with absolute-value totals.
6. **Accepted** — everything else. `revenue = quantity * unit_price`.
   Missing `CustomerID` is NOT a defect (guest checkout): accepted, excluded
   from customer marts only. Descriptions are trimmed; empty names kept as-is.

## Rules

- Quarantine stores **counts + reasons**, not full row dumps (Phase 2 scope).
- Nothing is imputed. No MAPE-style silent patching anywhere.
- The same code path processes synthetic and real data; only the input differs.
- Monetary values are doubles rounded at presentation, never in storage.
