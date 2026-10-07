"""query speed indexes for dashboard and forecast polling

Adds indexes matching the hottest read paths. These are deliberately narrow
and dataset-scoped so Supabase/Postgres can answer dashboard queries without
scanning unrelated datasets.
"""
from typing import Sequence, Union

from alembic import op

revision: str = '9a6d2e1f4b77'
down_revision: Union[str, Sequence[str], None] = 'f2c8d4e6a1b3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # NOTE (local fix 2026-10-07): two indexes below already exist from
    # c41d9e2a7f30, so use IF NOT EXISTS for idempotency on fresh DBs.
    import sqlalchemy as sa
    statements = [
        'CREATE INDEX IF NOT EXISTS ix_product_daily_dataset_stockcode_date ON product_daily (dataset_id, stockcode, date)',
        'CREATE INDEX IF NOT EXISTS ix_country_daily_dataset_country_date ON country_daily (dataset_id, country, date)',
        'CREATE INDEX IF NOT EXISTS ix_product_summary_dataset_revenue ON product_summary (dataset_id, revenue)',
        'CREATE INDEX IF NOT EXISTS ix_customer_summary_dataset_revenue ON customer_summary (dataset_id, revenue)',
        'CREATE INDEX IF NOT EXISTS ix_forecast_groups_dataset_status ON forecast_groups (dataset_id, status, created_at)',
        'CREATE INDEX IF NOT EXISTS ix_forecast_runs_group_status ON forecast_runs (group_id, status)',
        'CREATE INDEX IF NOT EXISTS ix_forecast_points_run_kind_date ON forecast_points (run_id, kind, date)',
        'CREATE INDEX IF NOT EXISTS ix_datasets_status_created_at ON datasets (status, created_at)',
    ]
    for stmt in statements:
        op.execute(sa.text(stmt))


def downgrade() -> None:
    for name, table in (
        ('ix_datasets_status_created_at', 'datasets'),
        ('ix_forecast_points_run_kind_date', 'forecast_points'),
        ('ix_forecast_groups_dataset_status', 'forecast_groups'),
        ('ix_forecast_runs_group_status', 'forecast_runs'),
        ('ix_customer_summary_dataset_revenue', 'customer_summary'),
        ('ix_product_summary_dataset_revenue', 'product_summary'),
        ('ix_country_daily_dataset_country_date', 'country_daily'),
        ('ix_product_daily_dataset_stockcode_date', 'product_daily'),
    ):
        op.drop_index(name, table_name=table)
