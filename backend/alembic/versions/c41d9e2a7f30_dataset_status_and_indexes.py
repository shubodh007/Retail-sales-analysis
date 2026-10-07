"""dataset async status + serving indexes

Revision ID: c41d9e2a7f30
Revises: bef5774bd309
Create Date: 2026-10-02

- datasets.error: human-readable failure reason for async ingestion
  (queued -> processing -> ready | failed).
- Covering indexes matching the actual API query patterns (Supabase and
  local PostgreSQL alike). No pgvector / no extensions required.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c41d9e2a7f30'
down_revision: Union[str, Sequence[str], None] = 'bef5774bd309'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


INDEXES = [
    # (name, table, columns)
    ("ix_sales_daily_dataset_date", "sales_daily", ["dataset_id", "date"]),
    ("ix_sales_monthly_dataset_month", "sales_monthly", ["dataset_id", "month"]),
    ("ix_product_daily_dataset_date", "product_daily", ["dataset_id", "date"]),
    ("ix_product_daily_dataset_stockcode_date", "product_daily",
     ["dataset_id", "stockcode", "date"]),
    ("ix_product_summary_dataset", "product_summary", ["dataset_id"]),
    ("ix_country_daily_dataset_date", "country_daily", ["dataset_id", "date"]),
    ("ix_country_daily_dataset_country_date", "country_daily",
     ["dataset_id", "country", "date"]),
    ("ix_customer_summary_dataset", "customer_summary", ["dataset_id"]),
    ("ix_anomalies_dataset_dimension", "anomalies", ["dataset_id", "dimension"]),
    ("ix_anomalies_dataset_date", "anomalies", ["dataset_id", "date"]),
    ("ix_forecast_runs_group", "forecast_runs", ["group_id"]),
    ("ix_forecast_points_run_date", "forecast_points", ["run_id", "date"]),
    ("ix_forecast_groups_dataset", "forecast_groups", ["dataset_id"]),
]


def upgrade() -> None:
    op.add_column("datasets", sa.Column("error", sa.Text(), nullable=True))
    for name, table, cols in INDEXES:
        op.create_index(name, table, cols)


def downgrade() -> None:
    for name, table, _cols in reversed(INDEXES):
        op.drop_index(name, table_name=table)
    op.drop_column("datasets", "error")
