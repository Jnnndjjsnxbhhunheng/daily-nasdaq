from __future__ import annotations

from typing import Dict, List, Tuple


WINDOW_DRAWDOWN = 250
MA_BREADTH_DAYS = 20

# 当前纳斯达克100主要成分（静态列表，避免依赖外部网页结构）
NASDAQ100_TICKERS: List[str] = [
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "GOOG", "AVGO", "COST", "TSLA",
    "NFLX", "ASML", "PEP", "TMUS", "AMD", "CSCO", "AZN", "ADBE", "LIN", "QCOM",
    "TXN", "AMGN", "INTU", "INTC", "CMCSA", "BKNG", "PDD", "AMAT", "ISRG", "HON",
    "SBUX", "ADI", "GILD", "VRTX", "LRCX", "MU", "ADP", "MELI", "MDLZ", "PANW",
    "REGN", "KLAC", "CDNS", "SNPS", "CTAS", "MAR", "ORLY", "CSX", "FTNT", "ABNB",
    "MNST", "CRWD", "NXPI", "PAYX", "WDAY", "KDP", "ROST", "AEP", "ODFL", "MCHP",
    "MRVL", "KHC", "EXC", "CPRT", "XEL", "LULU", "FAST", "DDOG", "EA", "GEHC",
    "DASH", "BIIB", "CCEP", "BKR", "ON", "CTSH", "PCAR", "IDXX", "FANG", "TEAM",
    "DLTR", "ANSS", "VRSK", "ZS", "CDW", "CSGP", "GFS", "TTD", "PYPL", "WBD",
    "ILMN", "SIRI", "MRNA", "DXCM", "RIVN", "TTWO", "LCID", "SPLK", "OKTA", "MDB",
]


def _download_panel(tickers: List[str], period: str):
    try:
        import yfinance as yf
    except ModuleNotFoundError as e:
        raise ModuleNotFoundError("缺少依赖：yfinance（请先安装：pip install yfinance）") from e

    try:
        df = yf.download(
            tickers=" ".join(tickers),
            period=period,
            group_by="ticker",
            auto_adjust=False,
            progress=False,
            threads=True,
        )
    except Exception as e:
        raise ValueError(f"下载行情失败: {e}") from e
    if df is None or len(df) == 0:
        raise ValueError("无法下载市场数据")
    return df


def _extract_close(panel, ticker: str):
    import pandas as pd

    if isinstance(panel.columns, pd.MultiIndex):
        if ticker in panel.columns.get_level_values(0):
            s = panel[ticker]["Close"].copy()
            s.name = ticker
            return s
        return None

    if "Close" in panel.columns and ticker == "QQQ":
        s = panel["Close"].copy()
        s.name = ticker
        return s
    return None


def _get_market_data(symbol: str) -> Tuple[Dict[str, float | str] | None, str | None]:
    import pandas as pd

    symbol = (symbol or "QQQ").strip().upper()
    if symbol != "QQQ":
        return None, "market_breadth_dca 目前仅支持 QQQ"

    tickers = ["QQQ"] + NASDAQ100_TICKERS
    unique_tickers = list(dict.fromkeys(tickers))

    try:
        panel = _download_panel(unique_tickers, period="2y")
    except Exception as e:
        return None, f"下载数据失败: {e}"

    qqq_close = _extract_close(panel, "QQQ")
    if qqq_close is None or len(qqq_close.dropna()) < WINDOW_DRAWDOWN:
        return None, "QQQ 数据不足，无法计算回撤"

    qqq_close = qqq_close.dropna()
    current_price = float(qqq_close.iloc[-1])
    last_date = qqq_close.index[-1].strftime("%Y-%m-%d")

    high_250 = float(qqq_close.tail(WINDOW_DRAWDOWN).max())
    drawdown = (current_price - high_250) / high_250

    below_flags = []
    valid_count = 0
    for ticker in NASDAQ100_TICKERS:
        s = _extract_close(panel, ticker)
        if s is None:
            continue
        s = s.dropna()
        if len(s) < MA_BREADTH_DAYS:
            continue
        ma20 = s.rolling(window=MA_BREADTH_DAYS).mean().iloc[-1]
        px = s.iloc[-1]
        if pd.isna(ma20) or pd.isna(px):
            continue
        valid_count += 1
        below_flags.append(1 if float(px) < float(ma20) else 0)

    if valid_count == 0:
        return None, "成分股数据不足，无法计算市场宽度"

    below_ratio = float(sum(below_flags) / valid_count)

    return {
        "date": last_date,
        "price": round(current_price, 2),
        "high": round(high_250, 2),
        "drawdown": drawdown,
        "breadth_below20": below_ratio,
        "breadth_samples": valid_count,
    }, None


def _calculate_strategy(data: Dict[str, float | str], base_amount: float) -> Tuple[float, float, str]:
    drawdown = float(data["drawdown"])
    breadth_below20 = float(data["breadth_below20"])

    if drawdown <= -0.30:
        ratio = 5.0
        reason = "🚨 回撤超30%，极端加码。"
    elif breadth_below20 <= 0.25:
        ratio = 3.0
        reason = "🧭 市场宽度偏低（≤25%），趋势修复前布局。"
    elif drawdown <= -0.10:
        ratio = 2.0
        reason = "⚠️ 回撤超10%，主动增强定投。"
    else:
        ratio = 1.0
        reason = "📈 市场正常，常规定投。"

    buy_amount = base_amount * ratio
    return ratio, buy_amount, reason


def run(*, base_amount: float = 10000, symbol: str = "QQQ") -> Dict[str, str]:
    data, err = _get_market_data(symbol)
    if err:
        return {"title": "获取数据失败", "content": err}

    ratio, amount, reason = _calculate_strategy(data, base_amount=base_amount)
    dd_str = f"{float(data['drawdown']) * 100:.2f}%"
    below_str = f"{float(data['breadth_below20']) * 100:.2f}%"

    title = f"纳斯达克定投信号(市场宽度): {ratio}倍 买入{int(ratio * base_amount)}元"
    content = (
        f"📅 日期: {data['date']}<br>"
        f"🧾 标的: {symbol}<br>"
        f"💲 最新价格: ${data['price']}<br>"
        f"🔝 近250日高点: ${data['high']}<br>"
        f"📉 当前回撤: {dd_str}<br>"
        f"🧭 成分股低于MA20占比: {below_str} (样本{int(data['breadth_samples'])}只)<br>"
        f"-----------------------<br>"
        f"💡 <b>执行策略: {reason}</b><br>"
        f"💰 <b>建议买入: {amount} 元</b> (基准{ratio}倍)<br>"
    )
    return {"title": title, "content": content}
