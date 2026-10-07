"""Single forecasting interface. One result shape for all four models."""
from dataclasses import dataclass, field


@dataclass
class ForecastResult:
    model: str
    horizon: int
    # validation slice (out-of-sample, chronological)
    val_dates: list[str] = field(default_factory=list)
    val_actual: list[float] = field(default_factory=list)
    val_predicted: list[float] = field(default_factory=list)
    # future forecast
    fc_dates: list[str] = field(default_factory=list)
    fc_points: list[float] = field(default_factory=list)
    fc_lower: list[float | None] = field(default_factory=list)
    fc_upper: list[float | None] = field(default_factory=list)
    interval_type: str = "none"  # analytic | empirical_residual | none
    metrics: dict[str, float | None] = field(default_factory=dict)
    mape_status: str = "ok"  # ok | unstable_zero_actuals
    train_from: str = ""
    train_to: str = ""
    val_from: str = ""
    val_to: str = ""
    config: dict = field(default_factory=dict)
    duration_s: float = 0.0


class InsufficientHistory(Exception):
    pass
