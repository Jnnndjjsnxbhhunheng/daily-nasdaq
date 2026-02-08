from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import date
import os
from typing import Dict, List, Tuple

try:
    from backtest.engine import (
        BacktestResult,
        backtest_daily_dca_with_ratios,
        backtest_monthly_dca_with_ratios,
        backtest_two_asset_dca_with_pool,
        compute_ma_drawdown_ratio,
    )
except ModuleNotFoundError:
    from engine import (  # type: ignore
        BacktestResult,
        backtest_daily_dca_with_ratios,
        backtest_monthly_dca_with_ratios,
        backtest_two_asset_dca_with_pool,
        compute_ma_drawdown_ratio,
    )


def _download_one(symbol: str, period: str = "20y") -> Tuple[List[date], List[float]]:
    try:
        import yfinance as yf
    except ModuleNotFoundError as e:
        raise SystemExit("Missing dependency: yfinance (install: pip install yfinance)") from e

    try:
        hist = yf.Ticker(symbol).history(period=period)
    except Exception as e:
        raise SystemExit(f"Failed to download {symbol} history: {e}") from e

    if len(hist) == 0:
        raise SystemExit(f"No data for {symbol}")

    dates = [d.date() for d in hist.index.to_pydatetime()]
    closes = [float(x) for x in hist["Close"].tolist()]
    return dates, closes


def _ratio_series_ma_drawdown(dates: List[date], closes: List[float], ma_days: int) -> List[float]:
    try:
        import pandas as pd
    except ModuleNotFoundError as e:
        raise SystemExit("Missing dependency: pandas (install: pip install pandas)") from e

    s = pd.Series(closes, index=pd.to_datetime(dates))
    ma_days = int(ma_days)
    if ma_days <= 0:
        raise ValueError("ma_days should be positive")

    ma = s.rolling(window=ma_days).mean()
    high_250 = s.rolling(window=250).max()
    drawdown = (s - high_250) / high_250

    ratios: List[float] = []
    for i in range(len(s)):
        if i < max(250, ma_days) or pd.isna(ma.iat[i]) or pd.isna(drawdown.iat[i]):
            ratios.append(1.0)
            continue
        r, _reason = compute_ma_drawdown_ratio(
            price=float(s.iat[i]),
            ma=float(ma.iat[i]),
            drawdown=float(drawdown.iat[i]),
            ma_days=ma_days,
        )
        ratios.append(r)
    return ratios


def _ratio_series_ma_drawdown_custom(
    dates: List[date],
    closes: List[float],
    *,
    ma_days: int,
    drawdown_5x: float,
    drawdown_3x: float,
) -> List[float]:
    try:
        import pandas as pd
    except ModuleNotFoundError as e:
        raise SystemExit("Missing dependency: pandas (install: pip install pandas)") from e

    s = pd.Series(closes, index=pd.to_datetime(dates))
    ma = s.rolling(window=int(ma_days)).mean()
    high_250 = s.rolling(window=250).max()
    drawdown = (s - high_250) / high_250

    ratios: List[float] = []
    for i in range(len(s)):
        if i < max(250, ma_days) or pd.isna(ma.iat[i]) or pd.isna(drawdown.iat[i]):
            ratios.append(1.0)
            continue
        dd = float(drawdown.iat[i])
        price = float(s.iat[i])
        ma_i = float(ma.iat[i])
        if dd <= float(drawdown_5x):
            ratios.append(5.0)
        elif dd <= float(drawdown_3x):
            ratios.append(3.0)
        elif price < ma_i:
            ratios.append(2.0)
        else:
            ratios.append(1.0)
    return ratios


def _ratio_series_discount_dca(dates: List[date], closes: List[float]) -> List[float]:
    try:
        import pandas as pd
    except ModuleNotFoundError as e:
        raise SystemExit("Missing dependency: pandas (install: pip install pandas)") from e

    s = pd.Series(closes, index=pd.to_datetime(dates))
    ma50 = s.rolling(window=50).mean()
    high_100 = s.rolling(window=100).max()
    discount = (s - high_100) / high_100

    ratios: List[float] = []
    for i in range(len(s)):
        if i < 100 or pd.isna(ma50.iat[i]) or pd.isna(discount.iat[i]):
            ratios.append(1.0)
            continue
        dis = float(discount.iat[i])
        px = float(s.iat[i])
        ma_i = float(ma50.iat[i])
        if dis <= -0.20:
            ratios.append(4.0)
        elif dis <= -0.10:
            ratios.append(2.0)
        elif px < ma_i:
            ratios.append(1.5)
        else:
            ratios.append(1.0)
    return ratios


def _market_breadth_backtest_series(symbol: str, period: str) -> Tuple[List[date], List[float], List[float]]:
    try:
        import pandas as pd
    except ModuleNotFoundError as e:
        raise SystemExit("Missing dependency: pandas (install: pip install pandas)") from e

    try:
        from strategy.market_breadth_dca import NASDAQ100_TICKERS
    except Exception as e:
        raise SystemExit(f"Cannot load NASDAQ100 components: {e}") from e

    symbol = (symbol or "QQQ").strip().upper()
    if symbol != "QQQ":
        raise SystemExit("market_breadth_dca backtest currently supports symbol=QQQ only")

    tickers = [symbol] + list(dict.fromkeys(NASDAQ100_TICKERS))
    closes = _download_many(tickers, period=period)
    if symbol not in closes:
        raise SystemExit(f"No close series for {symbol}")

    qqq = closes[symbol].rename("qqq").dropna()
    if len(qqq) < 250:
        raise SystemExit("Not enough QQQ data for 250-day drawdown")

    comp_series = []
    for ticker in NASDAQ100_TICKERS:
        s = closes.get(ticker)
        if s is None:
            continue
        comp_series.append(s.rename(ticker))
    if not comp_series:
        raise SystemExit("No component stock data for breadth computation")

    comp_df = pd.concat(comp_series, axis=1)
    comp_df = comp_df.sort_index()
    ma20 = comp_df.rolling(window=20).mean()
    valid_mask = comp_df.notna() & ma20.notna()
    below_mask = (comp_df < ma20) & valid_mask
    valid_count = valid_mask.sum(axis=1)
    below_ratio = below_mask.sum(axis=1) / valid_count.where(valid_count > 0)

    high_250 = qqq.rolling(window=250).max()
    drawdown = (qqq - high_250) / high_250

    aligned = pd.concat(
        [qqq.rename("close"), drawdown.rename("drawdown"), below_ratio.rename("below_ratio"), valid_count.rename("n")],
        axis=1,
    )
    aligned = aligned.dropna(subset=["close"])

    ratios: List[float] = []
    for _, row in aligned.iterrows():
        dd = float(row["drawdown"]) if row["drawdown"] == row["drawdown"] else 0.0
        br = float(row["below_ratio"]) if row["below_ratio"] == row["below_ratio"] else 1.0
        n = int(row["n"]) if row["n"] == row["n"] else 0
        if dd <= -0.30:
            ratios.append(5.0)
        elif n >= 20 and br <= 0.25:
            ratios.append(3.0)
        elif dd <= -0.10:
            ratios.append(2.0)
        else:
            ratios.append(1.0)

    dates = list(aligned.index)
    close_vals = [float(x) for x in aligned["close"].tolist()]
    return dates, close_vals, ratios


def _download_many(symbols: List[str], period: str = "20y"):
    try:
        import yfinance as yf
    except ModuleNotFoundError as e:
        raise SystemExit("Missing dependency: yfinance (install: pip install yfinance)") from e

    try:
        import pandas as pd
    except ModuleNotFoundError as e:
        raise SystemExit("Missing dependency: pandas (install: pip install pandas)") from e

    try:
        df = yf.download(
            tickers=" ".join(symbols),
            period=period,
            group_by="ticker",
            auto_adjust=False,
            progress=False,
            threads=True,
        )
    except Exception as e:
        raise SystemExit(f"Failed to download symbols via yfinance: {e}") from e

    if df is None or len(df) == 0:
        raise SystemExit("No data returned")

    closes: Dict[str, pd.Series] = {}
    for sym in symbols:
        if isinstance(df.columns, pd.MultiIndex):
            if sym not in df.columns.get_level_values(0):
                continue
            close = df[sym]["Close"].copy()
        else:
            if "Close" not in df.columns:
                continue
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
    if sym_a not in closes or sym_b not in closes or vix_sym not in closes:
        raise SystemExit(f"Missing close series in download: need {sym_a},{sym_b},{vix_sym}")

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

    width = max(8.0, 1.6 * len(results) + 2.0)
    plt.figure(figsize=(width, 4.5))
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
        from matplotlib.colors import to_rgba
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

    fig = plt.figure(figsize=(14, 9))
    gs = fig.add_gridspec(nrows=2, ncols=1, height_ratios=[3, 2.6])
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
    best_cols: List[int | None] = []
    values_matrix: List[List[float | None]] = []
    for y in years:
        row = [str(y)]
        vals_pct: List[float | None] = []
        for r in results:
            v = r.yearly_xirr.get(y)
            vp = None if v is None else float(v) * 100.0
            vals_pct.append(vp)
            row.append("—" if vp is None else f"{vp:+.2f}%")
        cell_text.append(row)
        values_matrix.append(list(vals_pct))
        best = max((v for v in vals_pct if v is not None), default=None)
        best_cols.append(None if best is None else (1 + vals_pct.index(best)))

    year_col_w = 0.12
    other_w = (1.0 - year_col_w) / max(1, len(results))
    col_widths = [year_col_w] + [other_w] * len(results)
    table = ax_table.table(
        cellText=cell_text,
        colLabels=col_labels,
        bbox=[0.02, 0.0, 0.96, 1.0],
        cellLoc="center",
        colLoc="center",
        colWidths=col_widths,
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.3)

    header_bg = "#1f2937"
    header_fg = "#ffffff"
    row_bg_even = "#f6f8fa"
    row_bg_odd = "#ffffff"
    text_pos = "#0b6e4f"
    text_neg = "#b00020"
    text_na = "#6b7280"
    text_default = "#111827"
    border = "#d1d5db"

    flat_vals = [v for row in values_matrix for v in row if v is not None]
    max_abs = max((abs(v) for v in flat_vals), default=0.0) or 1.0
    pos_bg = "#86efac"
    neg_bg = "#fca5a5"
    best_accent = "#22c55e"

    def _blend(base_hex: str, overlay_hex: str, alpha: float) -> tuple[float, float, float, float]:
        br, bg, bb, ba = to_rgba(base_hex)
        or_, og, ob, oa = to_rgba(overlay_hex)
        a = max(0.0, min(1.0, float(alpha)))
        return (
            (1 - a) * br + a * or_,
            (1 - a) * bg + a * og,
            (1 - a) * bb + a * ob,
            1.0,
        )

    for (row_i, col_i), cell in table.get_celld().items():
        cell.set_edgecolor(border)
        cell.set_linewidth(0.5)
        cell.PAD = 0.015

        if row_i == 0:
            cell.set_facecolor(header_bg)
            cell.get_text().set_color(header_fg)
            cell.get_text().set_weight("bold")
            continue

        base_bg = row_bg_even if (row_i % 2 == 0) else row_bg_odd
        cell.set_facecolor(base_bg)

        if col_i == 0:
            cell.get_text().set_weight("bold")
            cell.get_text().set_color(text_default)
        else:
            v = values_matrix[row_i - 1][col_i - 1] if (row_i - 1) < len(values_matrix) else None
            if v is None:
                cell.get_text().set_color(text_na)
            else:
                overlay = pos_bg if v >= 0 else neg_bg
                strength = min(0.55, 0.10 + 0.45 * (abs(v) / max_abs))
                cell.set_facecolor(_blend(base_bg, overlay, strength))
                if v > 0:
                    cell.get_text().set_color(text_pos)
                elif v < 0:
                    cell.get_text().set_color(text_neg)
                else:
                    cell.get_text().set_color(text_default)

        best_col = best_cols[row_i - 1] if (0 <= row_i - 1 < len(best_cols)) else None
        if best_col is not None and col_i == best_col:
            cell.set_facecolor(_blend(cell.get_facecolor(), best_accent, 0.22))
            cell.get_text().set_weight("bold")
            cell.set_linewidth(1.2)
            cell.set_edgecolor("#10b981")

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

    width = max(8.0, 1.6 * len(results) + 2.0)
    plt.figure(figsize=(width, 4.5))
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
    p = argparse.ArgumentParser(description="Backtest DCA strategies on Nasdaq proxy data (default QQQ).")
    p.add_argument(
        "--strategy",
        default="ma250_drawdown",
        choices=[
            "ma250_drawdown",
            "ma200_drawdown",
            "ma150_drawdown",
            "discount_dca",
            "market_breadth_dca",
            "plain_dca",
            "etf_dca_dip_buy",
            "all",
        ],
        help="Strategy key to backtest (use 'all' to run all and plot a comparison).",
    )
    p.add_argument(
        "--symbol",
        default="QQQ",
        help="For single-symbol strategies: data symbol (QQQ is a common Nasdaq-100 proxy).",
    )
    p.add_argument(
        "--symbols",
        default="SPY,QQQ",
        help="For etf_dca_dip_buy: two symbols, comma-separated (defaults to SPY,QQQ as long-history proxies for VOO/QQQM).",
    )
    p.add_argument(
        "--base-amount",
        type=float,
        default=10000,
        help="For single-symbol strategies: base contribution amount.",
    )
    p.add_argument("--monthly-total", type=float, default=900, help="For etf_dca_dip_buy: total monthly DCA amount in USD.")
    p.add_argument("--annual-pool", type=float, default=4000, help="For etf_dca_dip_buy: annual reserve pool in USD (reset each year).")
    p.add_argument("--weights", default="0.5,0.5", help="For etf_dca_dip_buy: weights, comma-separated (e.g. 0.6,0.4).")
    p.add_argument("--invest-day", type=int, default=10, help="Calendar day-of-month to invest for monthly DCA strategies (1..28).")
    p.add_argument("--period", default="20y", help="Data period (e.g. 20y).")
    p.add_argument("--out-dir", default="backtest", help="Output directory for comparison charts (all-mode).")
    args = p.parse_args()

    single_symbol_keys = {
        "ma250_drawdown",
        "ma200_drawdown",
        "ma150_drawdown",
        "discount_dca",
        "market_breadth_dca",
        "plain_dca",
    }
    need_single_symbol = args.strategy in single_symbol_keys or args.strategy == "all"

    result_map: Dict[str, BacktestResult] = {}

    if need_single_symbol:
        if args.strategy == "market_breadth_dca":
            dates, closes, ratios_breadth = _market_breadth_backtest_series(args.symbol, period=args.period)
        else:
            dates, closes = _download_one(args.symbol, period=args.period)
            ratios_breadth = []

        ratios_250 = _ratio_series_ma_drawdown(dates, closes, ma_days=250)
        ratios_200 = _ratio_series_ma_drawdown_custom(
            dates,
            closes,
            ma_days=200,
            drawdown_5x=-0.25,
            drawdown_3x=-0.15,
        )
        ratios_150 = _ratio_series_ma_drawdown(dates, closes, ma_days=150)
        ratios_discount = _ratio_series_discount_dca(dates, closes)

        result_map["ma250_drawdown"] = backtest_monthly_dca_with_ratios(
            symbol=args.symbol,
            strategy_key="ma250_drawdown",
            dates=dates,
            closes=closes,
            ratio_for_index=lambda i: ratios_250[i],
            base_amount=args.base_amount,
            invest_day=args.invest_day,
            trailing_years=3,
        )
        result_map["ma200_drawdown"] = backtest_monthly_dca_with_ratios(
            symbol=args.symbol,
            strategy_key="ma200_drawdown",
            dates=dates,
            closes=closes,
            ratio_for_index=lambda i: ratios_200[i],
            base_amount=args.base_amount,
            invest_day=args.invest_day,
            trailing_years=3,
        )
        result_map["ma150_drawdown"] = backtest_monthly_dca_with_ratios(
            symbol=args.symbol,
            strategy_key="ma150_drawdown",
            dates=dates,
            closes=closes,
            ratio_for_index=lambda i: ratios_150[i],
            base_amount=args.base_amount,
            invest_day=args.invest_day,
            trailing_years=3,
        )
        result_map["discount_dca"] = backtest_monthly_dca_with_ratios(
            symbol=args.symbol,
            strategy_key="discount_dca",
            dates=dates,
            closes=closes,
            ratio_for_index=lambda i: ratios_discount[i],
            base_amount=args.base_amount,
            invest_day=args.invest_day,
            trailing_years=3,
        )

        if args.strategy == "market_breadth_dca" or args.strategy == "all":
            if args.strategy != "market_breadth_dca":
                dates_b, closes_b, ratios_breadth = _market_breadth_backtest_series(args.symbol, period=args.period)
            else:
                dates_b, closes_b = dates, closes
            result_map["market_breadth_dca"] = backtest_monthly_dca_with_ratios(
                symbol=args.symbol,
                strategy_key="market_breadth_dca",
                dates=dates_b,
                closes=closes_b,
                ratio_for_index=lambda i: ratios_breadth[i],
                base_amount=args.base_amount,
                invest_day=args.invest_day,
                trailing_years=3,
            )

        result_map["plain_dca"] = backtest_daily_dca_with_ratios(
            symbol=args.symbol,
            strategy_key="plain_dca",
            dates=dates,
            closes=closes,
            ratio_for_index=lambda _i: 1.0,
            base_amount=args.base_amount,
            trailing_years=3,
        )

        if args.strategy in single_symbol_keys and args.strategy != "market_breadth_dca":
            _print_result(result_map[args.strategy])
            return
        if args.strategy == "market_breadth_dca":
            _print_result(result_map["market_breadth_dca"])
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
        result_map["etf_dca_dip_buy"] = replace(result_dip, strategy_key="etf_dca_dip_buy")
        if args.strategy == "etf_dca_dip_buy":
            _print_result(result_map["etf_dca_dip_buy"])
            return

    if args.strategy == "all":
        ordered_keys = [
            "ma250_drawdown",
            "ma200_drawdown",
            "ma150_drawdown",
            "discount_dca",
            "market_breadth_dca",
            "plain_dca",
            "etf_dca_dip_buy",
        ]
        results = [result_map[k] for k in ordered_keys if k in result_map]
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
