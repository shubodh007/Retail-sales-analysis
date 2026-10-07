# Real dataset (primary demonstration)

## Selected: UCI Online Retail II

- **Source:** UCI Machine Learning Repository, dataset ID 502
  (`https://archive.ics.uci.edu/dataset/502/online+retail+ii`)
- **Donors:** Chen, D., Sain, S., Guo, K. (2012). Data originally used for
  customer-behavior analysis of a UK online retailer.
- **Coverage:** 01/12/2009 – 09/12/2011 (2 full years, daily grain capable).
- **Size:** 1,067,371 rows × 8 columns (verified on download 2026-09-30:
  `Year 2009-2010` = 525,461 rows, `Year 2010-2011` = 541,910 rows).
- **License:** CC BY 4.0 (sharing/adaptation allowed with credit).
  Cite: Chen, D. (2012). Online Retail II [Dataset]. UCI Machine Learning
  Repository. https://doi.org/10.24432/C5CG6D.
- **Local files (not committed):** `datasets/raw/online_retail_ii.zip` (source),
  `datasets/raw/online_retail_II.xlsx`, `datasets/raw/online_retail_II.csv`
  (canonical UTF-8 input, converted by `datasets/raw/to_csv.py`).
- **Business:** UK-based non-store online retail, mostly all-occasion
  gift-ware; many customers are wholesalers.
- **Access:** free download from UCI (registration may be required);
  Kaggle mirrors exist. Do not redistribute the file; link, don't vendor.

## Columns -> our contract

| UCI column | Role | Notes |
|---|---|---|
| `InvoiceDate` | `date` | Transaction timestamp |
| `Quantity` | `quantity` | Negative = cancellation/return |
| `UnitPrice` (listed as `Price`) | `unit_price` | GBP |
| `Quantity × UnitPrice` | `revenue` | Derived; cancellations excluded |
| `StockCode` | `product_id` | 5-digit + letter variants |
| `Description` | `product_name` | Nullable |
| `Customer ID` | `customer_id` | Nullable (guest/wholesale gaps) |
| `Country` | `region` | Country-as-region proxy |
| `InvoiceNo` | — | Line-group key; leading `C` = cancellation |

`category` is absent -> product analytics degrades gracefully to
product-level (no fabricated categories).

## Why it fits

Date + revenue + product + quantity + customer + region-proxy,
two-year history (seasonality learnable), 1M+ rows (exercises the
Spark/Parquet/Postgres path, not just toy sizes).

## Known limitations (handled, not hidden)

1. No store/region below country; regional analytics = country-level.
2. Wholesaler skew: a few large orders dominate revenue (document in analysis).
3. Cancellations as negative quantities + `C`-prefixed invoices: flagged and
   excluded from revenue, counted in the quality report.
4. Null `Customer ID`s: guest rows excluded from customer analytics only.
5. Gift-ware 2009–2011 is dated/niche: fine for demonstrating method;
   conclusions are labeled as dataset-specific.
6. `.xlsx` source: convert `Year 2009-2010` + `Year 2010-2011` sheets to one
   UTF-8 CSV before upload (Phase 2 runbook).

## License / provenance honesty

UCI datasets are provided for research/education; cite Chen et al. (2012)
and link the UCI page in any report. Never claim ownership. Never present
synthetic data alongside it without labeling (see `synthetic-dataset.md`).
