# Dataset Contract

## Logical roles

Every uploaded CSV is mapped onto these logical roles. The uploader
auto-detects them (fuzzy header match + type inference); the user
confirms the mapping before processing.

| Role | Required | Type | Notes |
|---|---|---|---|
| `date` | yes | datetime | Any parseable date/timestamp. Day grain preferred. |
| `revenue` | yes* | numeric | *Or derivable as `quantity × unit_price`. |
| `quantity` | yes* | integer | May be negative (returns/cancellations) in raw retail data. |
| `unit_price` | no | numeric | Needed to derive revenue when absent. Must be > 0 after cleaning. |
| `product_id` | yes | string | SKU / StockCode. |
| `product_name` | no | string | Description. Nullable. |
| `category` | no | string | Enables product analytics depth. |
| `region` | no | string | Country / store / region. Enables regional analytics. |
| `customer_id` | no | string | Enables customer analytics. If absent, `/customers` shows an honest unsupported state — never fake data. |
| `discount` | no | numeric | Optional. |

## Header aliases (auto-detection)

- date: `invoicedate`, `invoice_date`, `date`, `orderdate`, `timestamp`, `dt`
- quantity: `quantity`, `qty`, `units`, `amount_sold`
- unit_price: `unitprice`, `unit_price`, `price`
- revenue: `revenue`, `sales`, `total`, `line_total`
- product_id: `stockcode`, `sku`, `product_id`, `item_code`
- product_name: `description`, `product_name`, `item`
- region: `country`, `region`, `store`, `market`
- customer_id: `customerid`, `customer_id`, `customer`

## Validation rules (fail fast, report honestly)

1. Required roles must resolve after mapping, else reject with 422 + reasons.
2. `date` must parse for ≥ 95% of rows; unparseable rows are quarantined, not dropped silently.
3. Numeric coercion failures are quarantined with counts reported.
4. Exact duplicate rows are removed; count reported.
5. Cancellations (negative quantity / `InvoiceNo` starting with `C`) are flagged, excluded from revenue, and counted.
6. Zero/near-zero actuals are detected for metric selection (MAPE instability → report + use WAPE/sMAPE). Never silently patched.

## Profiling output

Row count, null % per column, duplicate %, inferred types, date range /
granularity / gaps, cardinality per dimension, numeric distributions
(min/p5/median/p95/max), data-quality score + quarantine report.
