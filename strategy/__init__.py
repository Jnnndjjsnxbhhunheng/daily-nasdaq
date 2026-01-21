from __future__ import annotations

from typing import Callable, Dict

from .etf_dca_dip_buy import run as run_etf_dca_dip_buy
from .ma250_drawdown import run as run_ma250_drawdown

StrategyRunner = Callable[..., Dict[str, str]]

STRATEGIES: Dict[str, StrategyRunner] = {
    "ma250_drawdown": run_ma250_drawdown,
    "etf_dca_dip_buy": run_etf_dca_dip_buy,
}


def list_strategies() -> Dict[str, StrategyRunner]:
    return dict(STRATEGIES)


def get_strategy(key: str) -> StrategyRunner:
    key = (key or "").strip()
    if key not in STRATEGIES:
        raise KeyError(f"Unknown strategy: {key}. Available: {', '.join(sorted(STRATEGIES))}")
    return STRATEGIES[key]
