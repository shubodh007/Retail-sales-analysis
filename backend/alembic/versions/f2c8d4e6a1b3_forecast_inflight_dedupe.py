"""single-flight forecast groups

Revision ID: f2c8d4e6a1b3
Revises: c41d9e2a7f30
Create Date: 2026-10-02

Partial unique index: at most one pending/running forecast group per
(dataset, target, context, horizon) key. This closes the check-then-act
race between the cache SELECT and the group INSERT in POST /forecasts/runs:
the loser gets IntegrityError and attaches to the winner instead of
training twice. COALESCE handles NULL context_id (global), which plain
unique indexes treat as distinct. Done/failed groups are unaffected.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f2c8d4e6a1b3'
down_revision: Union[str, Sequence[str], None] = 'c41d9e2a7f30'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE UNIQUE INDEX uq_forecast_groups_inflight ON forecast_groups "
        "(dataset_id, target, context_type, COALESCE(context_id, ''), horizon) "
        "WHERE status IN ('pending', 'running')"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_forecast_groups_inflight")
