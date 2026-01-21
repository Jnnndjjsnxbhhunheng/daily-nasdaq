from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import datetime as _dt


@dataclass(frozen=True)
class Tier:
    name: str
    min_drawdown: float | None  # negative value, e.g. -0.15
    max_drawdown: float | None  # negative value, e.g. -0.08
    extra_ratio: float | None  # relative to monthly dca total, e.g. 0.5 means +50%
    vix_min: float | None
    note: str


TIERS: List[Tier] = [
    Tier(name="档位4", min_drawdown=-0.35, max_drawdown=None, extra_ratio=None, vix_min=None, note="极端行情：动用剩余加仓金50%"),
    Tier(name="档位3", min_drawdown=-0.25, max_drawdown=None, extra_ratio=1.0, vix_min=25.0, note="中大回撤：加码100%（VIX>25）"),
    Tier(name="档位2", min_drawdown=-0.15, max_drawdown=None, extra_ratio=0.5, vix_min=None, note="常见回调：加码50%"),
    Tier(name="档位1", min_drawdown=-0.14, max_drawdown=-0.08, extra_ratio=0.25, vix_min=20.0, note="中等回调：加码20%-30%（VIX>20）"),
    Tier(name="档位0", min_drawdown=None, max_drawdown=-0.08, extra_ratio=0.0, vix_min=None, note="正常波动：仅定投不加码"),
]


def _history(symbol: str, period: str):
    try:
        import yfinance as yf
    except ModuleNotFoundError as e:
        raise ModuleNotFoundError("缺少依赖：yfinance（请先安装：pip install yfinance）") from e
    return yf.Ticker(symbol).history(period=period)


def _six_month_drawdown(symbol: str) -> Tuple[float, float, float]:
    hist = _history(symbol, period="1y")
    if len(hist) < 30:
        raise ValueError(f"{symbol} 数据不足")

    close = hist["Close"].dropna()
    tail = close.tail(126) if len(close) >= 126 else close
    current = float(tail.iloc[-1])
    high_6m = float(tail.max())
    dd = (current - high_6m) / high_6m
    return current, high_6m, dd


def _get_vix() -> float | None:
    try:
        hist = _history("^VIX", period="5d")
        if len(hist) == 0:
            return None
        return float(hist["Close"].dropna().iloc[-1])
    except Exception:
        return None


def _pick_tier(drawdown: float, vix: float | None) -> Tier:
    if drawdown > -0.08:
        return next(t for t in TIERS if t.name == "档位0")

    if -0.14 <= drawdown <= -0.08 and (vix is not None and vix > 20):
        return next(t for t in TIERS if t.name == "档位1")

    if drawdown <= -0.35:
        return next(t for t in TIERS if t.name == "档位4")

    if drawdown <= -0.25 and (vix is not None and vix > 25):
        return next(t for t in TIERS if t.name == "档位3")

    if drawdown <= -0.15:
        return next(t for t in TIERS if t.name == "档位2")

    return next(t for t in TIERS if t.name == "档位0")


def run(
    *,
    monthly_total_usd: float = 900,
    etfs: Tuple[str, str] = ("VOO", "QQQM"),
    weights: Tuple[float, float] = (0.5, 0.5),
    invest_day: int = 10,
    annual_reserve_pool_usd: float = 4000,
) -> Dict[str, str]:
    today = _dt.date.today()
    should_dca = today.day == invest_day

    try:
        vix = _get_vix()
    except ModuleNotFoundError as e:
        return {"title": "策略运行失败", "content": str(e)}

    per_symbol: Dict[str, Dict[str, float]] = {}
    worst_dd = 0.0
    try:
        for sym in etfs:
            current, high_6m, dd = _six_month_drawdown(sym)
            per_symbol[sym] = {"price": current, "high_6m": high_6m, "drawdown": dd}
            worst_dd = min(worst_dd, dd)
    except (ModuleNotFoundError, ValueError) as e:
        return {"title": "策略运行失败", "content": str(e)}

    tier = _pick_tier(worst_dd, vix=vix)

    base_allocations = {sym: monthly_total_usd * w for sym, w in zip(etfs, weights)}

    if tier.name == "档位4":
        extra_total = annual_reserve_pool_usd * 0.5
        extra_note = f"按策略动用加仓金 50%（假设当前资金池 {annual_reserve_pool_usd:.0f} 美元）"
    else:
        extra_ratio = float(tier.extra_ratio or 0.0)
        extra_total = monthly_total_usd * extra_ratio
        extra_note = f"加码 {extra_ratio*100:.0f}%（相对月定投总额）"

    extra_allocations = {sym: extra_total * w for sym, w in zip(etfs, weights)}

    title = "ETF定投+下跌加仓策略"

    symbol_lines = []
    for sym in etfs:
        dd_pct = per_symbol[sym]["drawdown"] * 100
        symbol_lines.append(
            f"{sym}: 现价 ${per_symbol[sym]['price']:.2f}｜6个月高点 ${per_symbol[sym]['high_6m']:.2f}｜跌幅 {dd_pct:.2f}%"
        )

    vix_str = f"{vix:.2f}" if vix is not None else "N/A"
    base_str = "；".join([f"{sym} ${base_allocations[sym]:.0f}" for sym in etfs])
    extra_str = "；".join([f"{sym} ${extra_allocations[sym]:.0f}" for sym in etfs])
    dd_worst_pct = worst_dd * 100

    content = (
        f"📅 日期: {today.isoformat()}<br>"
        f"🗓️ 定投日: 每月{invest_day}号｜本次{'执行' if should_dca else '不执行'}基础定投<br>"
        f"📌 标的: {', '.join(etfs)}<br>"
        + "<br>".join(symbol_lines)
        + "<br>"
        f"📉 参考跌幅(取最深): {dd_worst_pct:.2f}%（基于近6个月高点）<br>"
        f"🌡️ VIX: {vix_str}<br>"
        f"-----------------------<br>"
        f"🎯 触发档位: <b>{tier.name}</b>｜{tier.note}<br>"
        f"💵 基础定投(合计 ${monthly_total_usd:.0f}): {base_str}<br>"
        f"➕ 额外加仓(合计 ${extra_total:.0f}): {extra_str}<br>"
        f"🧾 说明: {extra_note}<br>"
    )

    return {"title": title, "content": content}
