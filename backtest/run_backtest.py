from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import date
import os
from typing import List, Tuple

try:
    from backtest.engine import (
        BacktestResult,
        backtest_monthly_dca_with_ratios,
        backtest_two_asset_dca_with_pool,
        compute_ma250_drawdown_ratio,
    )
except ModuleNotFoundError:
    from engine import (  # type: ignore
        BacktestResult,
        backtest_monthly_dca_with_ratios,
        backtest_two_asset_dca_with_pool,
        compute_ma250_drawdown_ratio,
    )


def _download_one(symbol: str, period: str = "20y") -> Tuple[List[date], List[float]]:
    try:
        import yfinance as yf
    except ModuleNotFoundError as e:
        raise SystemExit("Missing dependency: yfinance (install: pip install yfinance)") from e

    hist = yf.Ticker(symbol).history(period=period)
    if len(hist) == 0:
        raise SystemExit(f"No data for {symbol}")

    dates = [d.date() for d in hist.index.to_pydatetime()]
    closes = [float(x) for x in hist["Close"].tolist()]
    return dates, closes


def _ratio_series_ma250_drawdown(dates: List[date], closes: List[float]) -> List[float]:
    try:
        import pandas as pd
    except ModuleNotFoundError as e:
        raise SystemExit("Missing dependency: pandas (install: pip install pandas)") from e

    s = pd.Series(closes, index=pd.to_datetime(dates))
    ma250 = s.rolling(window=250).mean()
    high_250 = s.rolling(window=250).max()
    drawdown = (s - high_250) / high_250

    ratios: List[float] = []
    for i in range(len(s)):
        if i < 250 or pd.isna(ma250.iat[i]) or pd.isna(drawdown.iat[i]):
            ratios.append(1.0)
            continue
        r, _reason = compute_ma250_drawdown_ratio(
            price=float(s.iat[i]),
            ma250=float(ma250.iat[i]),
            drawdown=float(drawdown.iat[i]),
        )
        ratios.append(r)
    return ratios


def _download_many(symbols: List[str], period: str = "20y"):
    try:
        import yfinance as yf
    except ModuleNotFoundError as e:
        raise SystemExit("Missing dependency: yfinance (install: pip install yfinance)") from e

    try:
        import pandas as pd
    except ModuleNotFoundError as e:
        raise SystemExit("Missing dependency: pandas (install: pip install pandas)") from e

    df = yf.download(
        tickers=" ".join(symbols),
        period=period,
        group_by="ticker",
        auto_adjust=False,
        progress=False,
        threads=True,
    )
    if df is None or len(df) == 0:
        raise SystemExit("No data returned")

    closes = {}
    for sym in symbols:
        if sym in df.columns.get_level_values(0):
            close = df[sym]["Close"].copy()
        else:
            close = df["Close"].copy()
        close.index = pd.to_datetime(close.index).date
        closes[sym] = close
    return closes


def _align_two_assets_and_vix(
    sym_a: str,
    sym_b: str,
    vix_sym: str,
    period: str,
) -> Tuple[List[date], List[float], List[float], List[float], List[float], List[float | None]]:
    import pandas as pd

    closes = _download_many([sym_a, sym_b, vix_sym], period=period)
    a = closes[sym_a].rename("a")
    b = closes[sym_b].rename("b")
    v = closes[vix_sym].rename("vix")

    df = pd.concat([a, b, v], axis=1)
    df = df.dropna(subset=["a", "b"])
    df["vix"] = df["vix"].ffill()

    roll_max_a = df["a"].rolling(window=126).max()
    roll_max_b = df["b"].rolling(window=126).max()
    dd_a = (df["a"] - roll_max_a) / roll_max_a
    dd_b = (df["b"] - roll_max_b) / roll_max_b

    df["dd_a"] = dd_a
    df["dd_b"] = dd_b

    dates = list(df.index)
    closes_a = [float(x) for x in df["a"].tolist()]
    closes_b = [float(x) for x in df["b"].tolist()]
    drawdown_a = [float(x) if x == x else 0.0 for x in df["dd_a"].tolist()]
    drawdown_b = [float(x) if x == x else 0.0 for x in df["dd_b"].tolist()]
    vix = [float(x) if x == x else None for x in df["vix"].tolist()]
    return dates, closes_a, closes_b, drawdown_a, drawdown_b, vix


def _print_result(r: BacktestResult) -> None:
    def pct(x):
        return "N/A" if x is None else f"{x*100:.2f}%"

    multiple = (r.final_value / r.total_invested) if r.total_invested > 0 else 0.0
    print("== Backtest ==")
    print(f"symbol: {r.symbol}")
    print(f"strategy: {r.strategy_key}")
    print(f"period: {r.start} -> {r.end}")
    print(f"total_invested: ${r.total_invested:,.2f}")
    print(f"final_value:    ${r.final_value:,.2f}")
    print(f"multiple:       {multiple:.2f}x")
    print(f"shares:         {r.shares:,.6f}")
    print(f"trailing_3y_xirr: {pct(r.trailing_3y_xirr)}")
    print(f"full_period_xirr: {pct(r.full_period_xirr)}")
    if r.yearly_xirr:
        print("yearly_xirr:")
        for y in sorted(r.yearly_xirr):
            print(f"  {y}: {pct(r.yearly_xirr[y])}")


def _plot_total_return_bar(results: List[BacktestResult], out_path: str) -> None:
    try:
        import matplotlib.pyplot as plt
    except ModuleNotFoundError:
        print(">> Skip plot: missing dependency matplotlib (install: pip install matplotlib)")
        return

    parent = os.path.dirname(out_path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    labels = [f"{r.strategy_key}\n({r.symbol})" for r in results]
    total_return_pct = [
        ((r.final_value / r.total_invested) - 1.0) * 100.0 if r.total_invested > 0 else 0.0 for r in results
    ]

    plt.figure(figsize=(8, 4.5))
    bars = plt.bar(labels, total_return_pct)
    plt.title("Total Return (Final / Invested - 1)")
    plt.ylabel("Total return (%)")
    plt.grid(True, axis="y", linestyle="--", alpha=0.3)

    for b, v in zip(bars, total_return_pct):
        plt.text(b.get_x() + b.get_width() / 2.0, b.get_height(), f"{v:.1f}%", ha="center", va="bottom", fontsize=9)

    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    print(f">> Saved total return bar: {out_path}")


def _plot_yearly_xirr_line_with_table(results: List[BacktestResult], out_path: str) -> None:
    try:
        import matplotlib.pyplot as plt
    except ModuleNotFoundError:
        print(">> Skip plot: missing dependency matplotlib (install: pip install matplotlib)")
        return

    parent = os.path.dirname(out_path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    years = sorted({y for r in results for y in r.yearly_xirr.keys()})
    if not years:
        print(">> Skip plot: no yearly_xirr data")
        return

    fig = plt.figure(figsize=(14, 8))
    gs = fig.add_gridspec(nrows=2, ncols=1, height_ratios=[3, 2])
    ax = fig.add_subplot(gs[0])
    ax_table = fig.add_subplot(gs[1])
    ax_table.axis("off")

    for r in results:
        ys = []
        for y in years:
            v = r.yearly_xirr.get(y)
            ys.append(None if v is None else float(v) * 100.0)
        ax.plot(years, ys, marker="o", linewidth=2, label=f"{r.strategy_key} ({r.symbol})")

    ax.set_title("Yearly Annualized Return (XIRR)")
    ax.set_xlabel("Year")
    ax.set_ylabel("Annualized return (%)")
    ax.grid(True, linestyle="--", alpha=0.3)
    ax.legend()

    col_labels = ["Year"] + [f"{r.strategy_key}\n({r.symbol})" for r in results]
    cell_text = []
    for y in years:
        row = [str(y)]
        for r in results:
            v = r.yearly_xirr.get(y)
            row.append("N/A" if v is None else f"{float(v)*100.0:.2f}%")
        cell_text.append(row)

    table = ax_table.table(
        cellText=cell_text,
        colLabels=col_labels,
        loc="center",
        cellLoc="center",
        colLoc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.2)

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    print(f">> Saved yearly XIRR line+table: {out_path}")


def _plot_trailing_3y_xirr_bar(results: List[BacktestResult], out_path: str) -> None:
    try:
        import matplotlib.pyplot as plt
    except ModuleNotFoundError:
        print(">> Skip plot: missing dependency matplotlib (install: pip install matplotlib)")
        return

    parent = os.path.dirname(out_path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    labels = [f"{r.strategy_key}\n({r.symbol})" for r in results]
    trailing_pct = [(float(r.trailing_3y_xirr) * 100.0) if r.trailing_3y_xirr is not None else 0.0 for r in results]

    plt.figure(figsize=(8, 4.5))
    bars = plt.bar(labels, trailing_pct)
    plt.title("Trailing 3Y Annualized Return (XIRR)")
    plt.ylabel("Annualized return (%)")
    plt.grid(True, axis="y", linestyle="--", alpha=0.3)

    for b, v, r in zip(bars, trailing_pct, results):
        label = "N/A" if r.trailing_3y_xirr is None else f"{v:.1f}%"
        plt.text(b.get_x() + b.get_width() / 2.0, b.get_height(), label, ha="center", va="bottom", fontsize=9)

    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    print(f">> Saved trailing 3Y XIRR bar: {out_path}")


def main() -> None:
    p = argparse.ArgumentParser(description="Backtest monthly DCA strategies on Nasdaq proxy data (default QQQ).")
    p.add_argument(
        "--strategy",
        default="ma250_drawdown",
        choices=["ma250_drawdown", "etf_dca_dip_buy", "all"],
        help="Strategy key to backtest (use 'all' to run both and plot a comparison).",
    )
    p.add_argument("--symbol", default="QQQ", help="For ma250_drawdown: data symbol (QQQ is a common Nasdaq-100 proxy).")
    p.add_argument(
        "--symbols",
        default="SPY,QQQ",
        help="For etf_dca_dip_buy: two symbols, comma-separated (defaults to SPY,QQQ as long-history proxies for VOO/QQQM).",
    )
    p.add_argument("--base-amount", type=float, default=10000, help="For ma250_drawdown: base monthly contribution amount.")
    p.add_argument("--monthly-total", type=float, default=900, help="For etf_dca_dip_buy: total monthly DCA amount in USD.")
    p.add_argument("--annual-pool", type=float, default=4000, help="For etf_dca_dip_buy: annual reserve pool in USD (reset each year).")
    p.add_argument("--weights", default="0.5,0.5", help="For etf_dca_dip_buy: weights, comma-separated (e.g. 0.6,0.4).")
    p.add_argument("--invest-day", type=int, default=10, help="Calendar day-of-month to invest (1..28).")
    p.add_argument("--period", default="20y", help="Data period (e.g. 20y).")
    p.add_argument("--out-dir", default="backtest", help="Output directory for comparison charts (all-mode).")
    args = p.parse_args()

    if args.strategy in ("ma250_drawdown", "all"):
        dates, closes = _download_one(args.symbol, period=args.period)
        ratios = _ratio_series_ma250_drawdown(dates, closes)
        result_ma = backtest_monthly_dca_with_ratios(
            symbol=args.symbol,
            strategy_key=args.strategy,
            dates=dates,
            closes=closes,
            ratio_for_index=lambda i: ratios[i],
            base_amount=args.base_amount,
            invest_day=args.invest_day,
            trailing_years=3,
        )
        result_ma = replace(result_ma, strategy_key="ma250_drawdown")
        if args.strategy == "ma250_drawdown":
            _print_result(result_ma)
            return

    if args.strategy in ("etf_dca_dip_buy", "all"):
        sym_list = [s.strip() for s in str(args.symbols).split(",") if s.strip()]
        if len(sym_list) != 2:
            raise SystemExit("--symbols must contain exactly 2 symbols, e.g. SPY,QQQ")
        w_list = [s.strip() for s in str(args.weights).split(",") if s.strip()]
        if len(w_list) != 2:
            raise SystemExit("--weights must contain exactly 2 numbers, e.g. 0.5,0.5")
        w0, w1 = float(w_list[0]), float(w_list[1])
        if w0 < 0 or w1 < 0 or abs((w0 + w1) - 1.0) > 1e-6:
            raise SystemExit("--weights must be non-negative and sum to 1.0")

        dts, ca, cb, dda, ddb, vix = _align_two_assets_and_vix(sym_list[0], sym_list[1], "^VIX", period=args.period)
        result_dip = backtest_two_asset_dca_with_pool(
            symbols=(sym_list[0], sym_list[1]),
            strategy_key=args.strategy,
            dates=dts,
            closes_a=ca,
            closes_b=cb,
            drawdown_a=dda,
            drawdown_b=ddb,
            vix=vix,
            monthly_total_usd=float(args.monthly_total),
            weights=(w0, w1),
            invest_day=args.invest_day,
            annual_reserve_pool_usd=float(args.annual_pool),
            trailing_years=3,
        )
        result_dip = replace(result_dip, strategy_key="etf_dca_dip_buy")
        if args.strategy == "etf_dca_dip_buy":
            _print_result(result_dip)
            return

    if args.strategy == "all":
        results = [result_ma, result_dip]  # type: ignore[name-defined]
        for r in results:
            _print_result(r)
        plot_dir = str(args.out_dir)
        _plot_yearly_xirr_line_with_table(results, out_path=os.path.join(plot_dir, "yearly_xirr_compare.png"))
        _plot_total_return_bar(results, out_path=os.path.join(plot_dir, "total_return_compare.png"))
        _plot_trailing_3y_xirr_bar(results, out_path=os.path.join(plot_dir, "trailing_3y_xirr_compare.png"))
        return

    raise SystemExit(f"Unsupported strategy: {args.strategy}")


if __name__ == "__main__":
    main()
