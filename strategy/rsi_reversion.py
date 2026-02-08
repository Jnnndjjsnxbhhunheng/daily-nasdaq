from __future__ import annotations

from typing import Dict, Tuple


def _compute_rsi(close, period: int = 14):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _get_market_data(symbol: str) -> Tuple[Dict[str, float | str] | None, str | None]:
    try:
        import yfinance as yf
        import pandas as pd
    except ModuleNotFoundError:
        return None, "缺少依赖：yfinance/pandas（请先安装：pip install yfinance pandas）"

    print(f"正在获取 {symbol} 的数据...")

    ticker = yf.Ticker(symbol)
    try:
        hist = ticker.history(period="2y")
    except Exception as e:
        return None, f"下载行情失败: {e}"

    if len(hist) < 260:
        return None, "数据不足，无法计算 RSI + 回撤"

    close = hist["Close"].dropna()
    rsi = _compute_rsi(close, period=14)

    price = float(close.iloc[-1])
    rsi_now = float(rsi.iloc[-1])
    high_250 = float(close.tail(250).max())
    drawdown = (price - high_250) / high_250

    return {
        "date": hist.index[-1].strftime("%Y-%m-%d"),
        "price": round(price, 2),
        "rsi": round(rsi_now, 2),
        "drawdown": drawdown,
    }, None


def _calc_action(data: Dict[str, float | str], base_amount: float) -> Tuple[str, float, str, float]:
    rsi = float(data["rsi"])
    drawdown = float(data["drawdown"])

    if rsi <= 30:
        ratio = 2.0 if drawdown <= -0.20 else 1.0
        reason = "🟢 RSI≤30 超卖买入"
        if ratio > 1.0:
            reason += " + 回撤超20%加倍"
        amount = base_amount * ratio
        return "buy", amount, reason, ratio

    if rsi >= 70:
        return "sell", 0.0, "🔴 RSI≥70 超买卖出", 0.0

    return "hold", 0.0, "🟡 RSI中性区间，继续观察", 0.0


def run(*, base_amount: float = 10000, symbol: str = "QQQ") -> Dict[str, str]:
    data, err = _get_market_data(symbol)
    if err:
        return {"title": "获取数据失败", "content": err}

    action, amount, reason, ratio = _calc_action(data, base_amount=base_amount)
    dd_str = f"{float(data['drawdown']) * 100:.2f}%"

    if action == "buy":
        title = f"RSI均值回归信号: 买入 {amount:.0f} 元"
        action_line = f"💰 <b>建议操作: 买入 {amount:.0f} 元</b> (基准{ratio:.1f}倍)<br>"
    elif action == "sell":
        title = "RSI均值回归信号: 卖出"
        action_line = "💰 <b>建议操作: 卖出仓位（或分批止盈）</b><br>"
    else:
        title = "RSI均值回归信号: 持有"
        action_line = "💰 <b>建议操作: 持有，等待阈值触发</b><br>"

    content = (
        f"📅 日期: {data['date']}<br>"
        f"🧾 标的: {symbol}<br>"
        f"💲 当前价格: ${data['price']}<br>"
        f"📐 RSI(14): {data['rsi']}<br>"
        f"📉 近250日高点回撤: {dd_str}<br>"
        f"-----------------------<br>"
        f"💡 <b>信号说明: {reason}</b><br>"
        f"{action_line}"
    )
    return {"title": title, "content": content}

