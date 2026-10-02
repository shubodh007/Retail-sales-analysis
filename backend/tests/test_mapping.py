"""Unit tests for CSV header -> role mapping."""
from app.services.mapping import detect_mapping


def test_uci_retail_headers_map():
    headers = ["InvoiceNo", "StockCode", "Description", "Quantity",
               "InvoiceDate", "UnitPrice", "CustomerID", "Country"]
    m = detect_mapping(headers)
    assert m.errors == []
    assert m.role_to_column["date"] == "InvoiceDate"
    assert m.role_to_column["quantity"] == "Quantity"
    assert m.role_to_column["unit_price"] == "UnitPrice"
    assert m.role_to_column["product_id"] == "StockCode"
    assert m.role_to_column["region"] == "Country"
    assert m.role_to_column["customer_id"] == "CustomerID"


def test_missing_required_date_rejected():
    m = detect_mapping(["product_id", "quantity", "unit_price"])
    assert any("date" in e for e in m.errors)


def test_revenue_paths():
    m1 = detect_mapping(["date", "product_id", "revenue"])
    assert m1.errors == []
    m2 = detect_mapping(["date", "product_id", "quantity", "unit_price"])
    assert m2.errors == []
    m3 = detect_mapping(["date", "product_id", "quantity"])
    assert any("revenue" in e for e in m3.errors)
