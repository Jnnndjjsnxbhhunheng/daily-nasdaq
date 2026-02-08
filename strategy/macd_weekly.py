from __future__ import annotations

from typing import Dict, Tuple


def _get_weekly_data(symbol: str) -> Tuple[Dict[str, float | str] | None, str | None]:
    try:
        import yfinance as yf
        import pandas as pd
    except ModuleNotFoundError:
        return None, "缺少依赖：yfinance/pandas（请先安装：pip install yfinance pandas）"

    print(f"正在获取 {symbol} 周线数据...")

    ticker = yf.Ticker(symbol)
    try:
        hist = ticker.history(period="5y", interval="1d")
    except Exception as e:
        return None, f"下载行情失败: {e}"

    if len(hist) < 180:
        return None, "数据不足，无法计算周线 MACD"

    close = hist["Close"].dropna()
    weekly = close.resample("W-FRI").last().dropna()
    if len(weekly) < 40:
        return None, "周线数据不足，无法计算 MACD"

    ema12 = weekly.ewm(span=12, adjust=False).mean()
    ema26 = weekly.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()

    return {
        "date": weekly.index[-1].strftime("%Y-%m-%d"),
        "price": round(float(weekly.iloc[-1]), 2),
        "macd": round(float(macd.iloc[-1]), 4),
        "signal": round(float(signal.iloc[-1]), 4),
        "prev_macd": round(float(macd.iloc[-2]), 4),
        "prev_signal": round(float(signal.iloc[-2]), 4),
    }, None


def _calc_action(data: Dict[str, float | str]) -> Tuple[str, str]:
    macd = float(data["macd"])
    signal = float(data["signal"])
    prev_macd = float(data["prev_macd"])
    prev_signal = float(data["prev_signal"])

    crossed_up = prev_macd <= prev_signal and macd > signal
    crossed_down = prev_macd >= prev_signal and macd < signal

    if crossed_up:
        return "buy", "🟢 周线 MACD 金叉（上穿信号线）"
    if crossed_down:
        return "sell", "🔴 周线 MACD 死叉（下穿信号线）"
    if macd > signal:
        return "hold", "🟡 多头趋势延续（MACD在线上方）"
    return "hold", "🟡 空头趋势延续（MACD在线下方）"


def run(*, base_amount: float = 10000, symbol: str = "QQQ") -> Dict[str, str]:
    data, err = _get_weekly_data(symbol)
    if err:
        return {"title": "获取数据失败", "content": err}

    action, reason = _calc_action(data)

    if action == "buy":
        title = f"周线MACD信号: 买入 {base_amount:.0f} 元"
        action_line = f"💰 <b>建议操作: 买入 {base_amount:.0f} 元</b>（可用于Q/TQQQ趋势仓）<br>"
    elif action == "sell":
        title = "周线MACD信号: 卖出/减仓"
        action_line = "💰 <b>建议操作: 卖出或减仓 1/3~1/2</b><br>"
    else:
        title = "周线MACD信号: 持有"
        action_line = "💰 <b>建议操作: 持有，等待交叉确认</b><br>"

    content = (
        f"📅 周线日期: {data['date']}<br>"
        f"🧾 标的: {symbol}<br>"
        f"💲 周收盘: ${data['price']}<br>"
        f"📈 MACD: {data['macd']}<br>"
        f"📊 Signal: {data['signal']}<br>"
        f"-----------------------<br>"
        f"💡 <b>信号说明: {reason}</b><br>"
        f"{action_line}"
    )
    return {"title": title, "content": content}

