from __future__ import annotations

from typing import Callable, Dict

from .etf_dca_dip_buy import run as run_etf_dca_dip_buy
from .discount_dca import run as run_discount_dca
from .ma150_drawdown import run as run_ma150_drawdown
from .ma200_drawdown import run as run_ma200_drawdown
from .ma250_drawdown import run as run_ma250_drawdown
from .ma_cross_sell import run as run_ma_cross_sell
from .macd_weekly import run as run_macd_weekly
from .market_breadth_dca import run as run_market_breadth_dca
from .plain_dca import run as run_plain_dca
from .rsi_reversion import run as run_rsi_reversion

StrategyRunner = Callable[..., Dict[str, str]]

STRATEGIES: Dict[str, StrategyRunner] = {
    "ma150_drawdown": run_ma150_drawdown,
    "ma200_drawdown": run_ma200_drawdown,
    "ma250_drawdown": run_ma250_drawdown,
    "ma_cross_sell": run_ma_cross_sell,
    "macd_weekly": run_macd_weekly,
    "discount_dca": run_discount_dca,
    "market_breadth_dca": run_market_breadth_dca,
    "rsi_reversion": run_rsi_reversion,
    "plain_dca": run_plain_dca,
    "etf_dca_dip_buy": run_etf_dca_dip_buy,
}


def list_strategies() -> Dict[str, StrategyRunner]:
    return dict(STRATEGIES)


def get_strategy(key: str) -> StrategyRunner:
    key = (key or "").strip()
    if key not in STRATEGIES:
        raise KeyError(f"Unknown strategy: {key}. Available: {', '.join(sorted(STRATEGIES))}")
    return STRATEGIES[key]
