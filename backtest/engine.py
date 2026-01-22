from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Callable, Dict, List, Sequence, Tuple


Cashflow = Tuple[date, float]  # (date, amount); invest is negative, ending value is positive


@dataclass(frozen=True)
class BacktestResult:
    symbol: str
    strategy_key: str
    start: date
    end: date
    total_invested: float
    final_value: float
    shares: float
    yearly_xirr: Dict[int, float | None]
    trailing_3y_xirr: float | None
    full_period_xirr: float | None


def _as_date(d) -> date:
    if isinstance(d, date) and not isinstance(d, datetime):
        return d
    if isinstance(d, datetime):
        return d.date()
    if isinstance(d, str):
        return date.fromisoformat(d)
    raise TypeError(f"Unsupported date type: {type(d)}")


def yearfrac(d0: date, d1: date) -> float:
    return (d1 - d0).days / 365.25


def xnpv(rate: float, cashflows: Sequence[Cashflow]) -> float:
    if rate <= -1.0:
        return float("inf")
    t0 = cashflows[0][0]
    return sum(cf / (1.0 + rate) ** yearfrac(t0, d) for d, cf in cashflows)


def xirr(cashflows: Sequence[Cashflow]) -> float | None:
    cashflows = list(cashflows)
    if len(cashflows) < 2:
        return None
    if not (any(cf < 0 for _, cf in cashflows) and any(cf > 0 for _, cf in cashflows)):
        return None

    lo, hi = -0.9999, 10.0
    f_lo = xnpv(lo, cashflows)
    f_hi = xnpv(hi, cashflows)
    if f_lo == 0:
        return lo
    if f_hi == 0:
        return hi
    if f_lo * f_hi > 0:
        return None

    for _ in range(200):
        mid = (lo + hi) / 2.0
        f_mid = xnpv(mid, cashflows)
        if abs(f_mid) < 1e-8:
            return mid
        if f_lo * f_mid < 0:
            hi, f_hi = mid, f_mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2.0


def yearly_xirr_from_cashflows(
    *,
    cashflows: Sequence[Cashflow],
    daily_values: Sequence[Tuple[date, float]],
) -> Dict[int, float | None]:
    values_by_year: Dict[int, List[Tuple[date, float]]] = {}
    for d, v in daily_values:
        values_by_year.setdefault(d.year, []).append((d, float(v)))

    cashflows_by_year: Dict[int, List[Cashflow]] = {}
    for d, cf in cashflows:
        cashflows_by_year.setdefault(d.year, []).append((d, float(cf)))

    results: Dict[int, float | None] = {}
    for y in sorted(values_by_year):
        vals = values_by_year[y]
        start_d, start_v = vals[0]
        end_d, end_v = vals[-1]

        cfs = list(cashflows_by_year.get(y, []))
        cfs = [(d, cf) for d, cf in cfs if start_d <= d <= end_d]

        if start_v == 0.0 and end_v == 0.0 and not cfs:
            results[y] = None
            continue

        year_cfs: List[Cashflow] = [(start_d, -start_v)] + cfs + [(end_d, end_v)]
        results[y] = xirr(year_cfs)

    return results


def monthly_invest_dates(trading_dates: Sequence[date], invest_day: int = 10) -> List[date]:
    if not trading_dates:
        return []
    invest_day = int(invest_day)
    if invest_day < 1 or invest_day > 28:
        raise ValueError("invest_day should be 1..28 for predictable monthly scheduling")

    by_month = {}
    for d in trading_dates:
        by_month.setdefault((d.year, d.month), []).append(d)

    result: List[date] = []
    for (y, m) in sorted(by_month):
        days = by_month[(y, m)]
        picked = next((d for d in days if d.day >= invest_day), days[-1])
        result.append(picked)
    return result


def compute_ma250_drawdown_ratio(price: float, ma250: float, drawdown: float) -> Tuple[float, str]:
    if drawdown <= -0.30:
        return 5.0, "极度恐慌(回撤<=30%)"
    if drawdown <= -0.20:
        return 3.0, "深度回调(回撤<=20%)"
    if price < ma250:
        return 2.0, "跌破年线(MA250)"
    return 1.0, "趋势向上/正常"


def backtest_monthly_dca_with_ratios(
    *,
    symbol: str,
    strategy_key: str,
    dates: Sequence[date],
    closes: Sequence[float],
    ratio_for_index: Callable[[int], float],
    base_amount: float,
    invest_day: int = 10,
    trailing_years: int = 3,
) -> BacktestResult:
    if len(dates) != len(closes):
        raise ValueError("dates and closes length mismatch")
    if len(dates) == 0:
        raise ValueError("empty price series")

    invest_dates = set(monthly_invest_dates(dates, invest_day=invest_day))
    shares = 0.0
    cashflows: List[Cashflow] = []
    total_invested = 0.0
    daily_values: List[Tuple[date, float]] = []

    for i, d in enumerate(dates):
        px = float(closes[i])
        daily_values.append((d, shares * px))
        if d not in invest_dates:
            continue
        ratio = float(ratio_for_index(i))
        amount = float(base_amount) * ratio
        if px <= 0:
            continue
        shares += amount / px
        total_invested += amount
        cashflows.append((d, -amount))
        daily_values[-1] = (d, shares * px)

    end = dates[-1]
    final_value = shares * float(closes[-1])
    cashflows_end = cashflows + [(end, final_value)]

    full_xirr = xirr(cashflows_end)

    trailing_start = end - timedelta(days=int(trailing_years * 365.25))
    trailing_cashflows = [(d, cf) for d, cf in cashflows if d >= trailing_start] + [(end, final_value)]
    trailing_xirr = xirr(trailing_cashflows)

    yearly = yearly_xirr_from_cashflows(cashflows=cashflows, daily_values=daily_values)

    return BacktestResult(
        symbol=symbol,
        strategy_key=strategy_key,
        start=dates[0],
        end=end,
        total_invested=total_invested,
        final_value=final_value,
        shares=shares,
        yearly_xirr=yearly,
        trailing_3y_xirr=trailing_xirr,
        full_period_xirr=full_xirr,
    )


def backtest_two_asset_dca_with_pool(
    *,
    symbols: Tuple[str, str],
    strategy_key: str,
    dates: Sequence[date],
    closes_a: Sequence[float],
    closes_b: Sequence[float],
    drawdown_a: Sequence[float],
    drawdown_b: Sequence[float],
    vix: Sequence[float | None],
    monthly_total_usd: float,
    weights: Tuple[float, float] = (0.5, 0.5),
    invest_day: int = 10,
    annual_reserve_pool_usd: float = 4000,
    trailing_years: int = 3,
) -> BacktestResult:
    if not (len(dates) == len(closes_a) == len(closes_b) == len(drawdown_a) == len(drawdown_b) == len(vix)):
        raise ValueError("series length mismatch")

    invest_dates = set(monthly_invest_dates(dates, invest_day=invest_day))
    shares_a = 0.0
    shares_b = 0.0
    cashflows: List[Cashflow] = []
    total_invested = 0.0
    daily_values: List[Tuple[date, float]] = []

    pool_remaining = float(annual_reserve_pool_usd)
    current_year = dates[0].year

    for i, d in enumerate(dates):
        px_a_today = float(closes_a[i])
        px_b_today = float(closes_b[i])
        daily_values.append((d, shares_a * px_a_today + shares_b * px_b_today))
        if d.year != current_year:
            current_year = d.year
            pool_remaining = float(annual_reserve_pool_usd)

        if d not in invest_dates:
            continue

        base_a = float(monthly_total_usd) * float(weights[0])
        base_b = float(monthly_total_usd) * float(weights[1])

        px_a = px_a_today
        px_b = px_b_today
        if px_a > 0:
            shares_a += base_a / px_a
        if px_b > 0:
            shares_b += base_b / px_b
        total_invested += base_a + base_b
        cashflows.append((d, -(base_a + base_b)))

        worst_dd = min(float(drawdown_a[i]), float(drawdown_b[i]))
        vix_i = vix[i]

        extra_total = 0.0
        if worst_dd <= -0.35:
            extra_total = pool_remaining * 0.5
        elif worst_dd <= -0.25 and (vix_i is not None and float(vix_i) > 25.0):
            extra_total = float(monthly_total_usd) * 1.0
        elif worst_dd <= -0.15:
            extra_total = float(monthly_total_usd) * 0.5
        elif -0.14 <= worst_dd <= -0.08 and (vix_i is not None and float(vix_i) > 20.0):
            extra_total = float(monthly_total_usd) * 0.25

        if extra_total > 0:
            extra_total = min(extra_total, pool_remaining)
            if extra_total > 0:
                extra_a = extra_total * float(weights[0])
                extra_b = extra_total * float(weights[1])
                if px_a > 0:
                    shares_a += extra_a / px_a
                if px_b > 0:
                    shares_b += extra_b / px_b
                total_invested += extra_total
                cashflows.append((d, -extra_total))
                pool_remaining -= extra_total
        daily_values[-1] = (d, shares_a * px_a + shares_b * px_b)

    end = dates[-1]
    final_value = shares_a * float(closes_a[-1]) + shares_b * float(closes_b[-1])
    cashflows_end = cashflows + [(end, final_value)]

    full_xirr = xirr(cashflows_end)

    trailing_start = end - timedelta(days=int(trailing_years * 365.25))
    trailing_cashflows = [(d, cf) for d, cf in cashflows if d >= trailing_start] + [(end, final_value)]
    trailing_xirr = xirr(trailing_cashflows)

    yearly = yearly_xirr_from_cashflows(cashflows=cashflows, daily_values=daily_values)

    return BacktestResult(
        symbol=",".join(symbols),
        strategy_key=strategy_key,
        start=dates[0],
        end=end,
        total_invested=total_invested,
        final_value=final_value,
        shares=shares_a + shares_b,
        yearly_xirr=yearly,
        trailing_3y_xirr=trailing_xirr,
        full_period_xirr=full_xirr,
    )
