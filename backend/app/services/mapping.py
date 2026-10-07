"""CSV header -> logical role mapping + validation. See docs/dataset-contract.md."""
import csv
from dataclasses import dataclass, field

ALIASES: dict[str, list[str]] = {
    "date": ["invoicedate", "invoice_date", "date", "orderdate", "order_date", "timestamp", "dt"],
    "quantity": ["quantity", "qty", "units", "units_sold", "sales_quantity", "amount_sold"],
    "unit_price": ["unitprice", "unit_price", "price"],
    "revenue": ["revenue", "sales", "total", "line_total"],
    "product_id": ["stockcode", "stock_code", "sku", "product_id", "item_code"],
    "product_name": ["description", "product_name", "item"],
    "category": ["category", "department", "type"],
    "region": ["country", "region", "store", "market"],
    "customer_id": ["customerid", "customer_id", "customer"],
    "discount": ["discount"], 
    "invoice_no": ["invoiceno", "invoice_no", "invoice", "orderid", "order_id", "transaction_id"],
}

REQUIRED = ("date", "product_id")
REVENUE_PATHS = (("revenue",), ("quantity", "unit_price"))


def _norm(header: str) -> str:
    return "".join(ch for ch in header.strip().lower() if ch.isalnum() or ch == "_")


@dataclass
class MappingResult:
    role_to_column: dict[str, str] = field(default_factory=dict)
    unmapped_headers: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def detect_mapping(headers: list[str]) -> MappingResult:
    result = MappingResult()
    norm_to_raw = {_norm(h): h for h in headers}
    used: set[str] = set()
    for role, aliases in ALIASES.items():
        for alias in aliases:
            if alias in norm_to_raw and norm_to_raw[alias] not in used:
                result.role_to_column[role] = norm_to_raw[alias]
                used.add(norm_to_raw[alias])
                break
    result.unmapped_headers = [h for h in headers if h not in used]
    for role in REQUIRED:
        if role not in result.role_to_column:
            result.errors.append(f"required column missing: no header maps to '{role}'")
    if not any(all(r in result.role_to_column for r in path) for path in REVENUE_PATHS):
        result.errors.append(
            "revenue not derivable: need 'revenue' or ('quantity' + 'unit_price')"
        )
    return result


def read_headers(csv_path: str, encoding: str = "utf-8-sig") -> list[str]:
    with open(csv_path, newline="", encoding=encoding) as f:
        reader = csv.reader(f)
        try:
            headers = next(reader)
        except StopIteration:
            return []
    return [h for h in headers if h.strip() != ""]


def detect_invoice_column(columns: list[str]) -> str:
    """Line-group key (UCI: InvoiceNo). No logical role; used for order counts."""
    for c in columns:
        if _norm(c) in ("invoiceno", "invoice", "orderid", "order_id"):
            return c
    return columns[0]
