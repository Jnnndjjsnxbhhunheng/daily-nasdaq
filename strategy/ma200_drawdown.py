from __future__ import annotations

from typing import Dict, Tuple


WINDOW_HIGH = 250
MA_DAYS = 200


def _get_market_data(symbol: str) -> Tuple[Dict[str, float | str] | None, str | None]:
    try:
        import yfinance as yf
    except ModuleNotFoundError:
        return None, "缺少依赖：yfinance（请先安装：pip install yfinance）"

    print(f"正在获取 {symbol} 的数据...")

    ticker = yf.Ticker(symbol)
    try:
        hist = ticker.history(period="2y")
    except Exception as e:
        return None, f"下载行情失败: {e}"

    if len(hist) < WINDOW_HIGH:
        return None, "数据不足，无法计算回撤与均线"

    current_price = float(hist["Close"].iloc[-1])
    last_date = hist.index[-1].strftime("%Y-%m-%d")

    ma200 = float(hist["Close"].rolling(window=MA_DAYS).mean().iloc[-1])

    high_250 = float(hist["Close"].tail(WINDOW_HIGH).max())
    drawdown = (current_price - high_250) / high_250

    return {
        "date": last_date,
        "price": round(current_price, 2),
        "ma200": round(ma200, 2),
        "high": round(high_250, 2),
        "drawdown": drawdown,
    }, None


def _calculate_strategy(data: Dict[str, float | str], base_amount: float) -> Tuple[float, float, str]:
    price = float(data["price"])
    ma200 = float(data["ma200"])
    drawdown = float(data["drawdown"])

    if drawdown <= -0.25:
        ratio = 5.0
        reason = "🚨 极度恐慌 (回撤超25%)，重仓加码。"
    elif drawdown <= -0.15:
        ratio = 3.0
        reason = "⚠️ 中深回撤 (回撤超15%)，主动加码。"
    elif price < ma200:
        ratio = 2.0
        reason = "📉 跌破 MA200，估值性价比较高。"
    else:
        ratio = 1.0
        reason = "📈 趋势正常，维持常规定投。"

    buy_amount = base_amount * ratio
    return ratio, buy_amount, reason


def run(*, base_amount: float = 10000, symbol: str = "QQQ") -> Dict[str, str]:
    data, err = _get_market_data(symbol)
    if err:
        return {"title": "获取数据失败", "content": err}

    ratio, amount, reason = _calculate_strategy(data, base_amount=base_amount)
    dd_str = f"{float(data['drawdown']) * 100:.2f}%"

    title = f"纳斯达克定投信号(MA200): {ratio}倍 买入{int(ratio * base_amount)}元"
    content = (
        f"📅 日期: {data['date']}<br>"
        f"🧾 标的: {symbol}<br>"
        f"💲 最新价格: ${data['price']}<br>"
        f"📏 200日均线: ${data['ma200']}<br>"
        f"📉 近250日高点回撤: {dd_str}<br>"
        f"-----------------------<br>"
        f"💡 <b>执行策略: {reason}</b><br>"
        f"💰 <b>建议买入: {amount} 元</b> (基准{ratio}倍)<br>"
    )
    return {"title": title, "content": content}
