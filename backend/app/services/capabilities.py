"""Dataset capability detection. Derived from schema_map, never guessed.

Capabilities gate every analytics endpoint: a missing dimension yields an
honest 409 with a reason, never fabricated numbers.
"""
ROLE_CAPABILITY = {
    "sales": ["date", "product_id"],       # revenue path validated at upload
    "products": ["product_id"],
    "quantity": ["quantity"],
    "customers": ["customer_id"],
    "geography": ["region"],
    "category": ["category"],
}


def capabilities(schema_map: dict[str, str]) -> dict[str, bool]:
    have = set(schema_map)
    return {cap: all(r in have for r in roles) for cap, roles in ROLE_CAPABILITY.items()}


def require(schema_map: dict[str, str], *caps: str) -> str | None:
    """Return a human reason when any capability is missing, else None."""
    missing = [c for c in caps if not capabilities(schema_map).get(c)]
    if not missing:
        return None
    return f"dataset does not support: {', '.join(missing)}"
