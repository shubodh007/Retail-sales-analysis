"""Error metrics. MAPE is reported only when valid; otherwise sMAPE/WAPE.

A series is 'zero-unstable' when any |actual| < eps (default 1.0 in revenue
units). Selection across models always uses WAPE (scale-free, zero-safe).
"""
import math

EPS = 1.0


def mae(a: list[float], p: list[float]) -> float:
    return sum(abs(x - y) for x, y in zip(a, p)) / len(a)


def rmse(a: list[float], p: list[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, p)) / len(a))


def mape(a: list[float], p: list[float]) -> float:
    return sum(abs((x - y) / x) for x, y in zip(a, p)) / len(a) * 100.0


def smape(a: list[float], p: list[float]) -> float:
    return sum(2 * abs(x - y) / (abs(x) + abs(y) + 1e-12) for x, y in zip(a, p)) / len(a) * 100.0


def wape(a: list[float], p: list[float]) -> float:
    denom = sum(abs(x) for x in a)
    return (sum(abs(x - y) for x, y in zip(a, p)) / denom * 100.0) if denom else 0.0


def zero_unstable(a: list[float], eps: float = EPS) -> bool:
    return any(abs(x) < eps for x in a)


def evaluate(actual: list[float], predicted: list[float]) -> tuple[dict, str]:
    m = {
        "mae": mae(actual, predicted),
        "rmse": rmse(actual, predicted),
        "wape": wape(actual, predicted),
        "smape": smape(actual, predicted),
        "mape": None,
    }
    status = "ok"
    if zero_unstable(actual):
        status = "unstable_zero_actuals"
    else:
        m["mape"] = mape(actual, predicted)
    return m, status
