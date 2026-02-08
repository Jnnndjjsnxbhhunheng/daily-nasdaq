from __future__ import annotations

from typing import Dict, Tuple


WINDOW_DISCOUNT = 100
MA_DAYS = 50


def _get_market_data(symbol: str) -> Tuple[Dict[str, float | str] | None, str | None]:
    try:
        import yfinance as yf
    except ModuleNotFoundError:
        return None, "缺少依赖：yfinance（请先安装：pip install yfinance）"

    print(f"正在获取 {symbol} 的数据...")

    ticker = yf.Ticker(symbol)
    try:
        hist = ticker.history(period="1y")
    except Exception as e:
        return None, f"下载行情失败: {e}"

    if len(hist) < WINDOW_DISCOUNT:
        return None, "数据不足，无法计算折扣与均线"

    close = hist["Close"]
    current_price = float(close.iloc[-1])
    last_date = hist.index[-1].strftime("%Y-%m-%d")

    ma50 = float(close.rolling(window=MA_DAYS).mean().iloc[-1])
    high_20w = float(close.tail(WINDOW_DISCOUNT).max())
    discount = (current_price - high_20w) / high_20w

    return {
        "date": last_date,
        "price": round(current_price, 2),
        "ma50": round(ma50, 2),
        "high_20w": round(high_20w, 2),
        "discount": discount,
    }, None


def _calculate_strategy(data: Dict[str, float | str], base_amount: float) -> Tuple[float, float, str]:
    price = float(data["price"])
    ma50 = float(data["ma50"])
    discount = float(data["discount"])

    if discount <= -0.20:
        ratio = 4.0
        reason = "🚨 折扣超20%，强力加码。"
    elif discount <= -0.10:
        ratio = 2.0
        reason = "⚠️ 折扣超10%，适度加码。"
    elif price < ma50:
        ratio = 1.5
        reason = "📉 跌破 MA50，轻度增强定投。"
    else:
        ratio = 1.0
        reason = "📈 未出现明显折扣，常规定投。"

    buy_amount = base_amount * ratio
    return ratio, buy_amount, reason


def run(*, base_amount: float = 10000, symbol: str = "QQQ") -> Dict[str, str]:
    data, err = _get_market_data(symbol)
    if err:
        return {"title": "获取数据失败", "content": err}

    ratio, amount, reason = _calculate_strategy(data, base_amount=base_amount)
    discount_str = f"{float(data['discount']) * 100:.2f}%"

    title = f"纳斯达克定投信号(折扣DCA): {ratio}倍 买入{int(ratio * base_amount)}元"
    content = (
        f"📅 日期: {data['date']}<br>"
        f"🧾 标的: {symbol}<br>"
        f"💲 最新价格: ${data['price']}<br>"
        f"📏 50日均线: ${data['ma50']}<br>"
        f"🔝 近20周高点: ${data['high_20w']}<br>"
        f"🏷️ 折扣(相对20周高点): {discount_str}<br>"
        f"-----------------------<br>"
        f"💡 <b>执行策略: {reason}</b><br>"
        f"💰 <b>建议买入: {amount} 元</b> (基准{ratio}倍)<br>"
    )
    return {"title": title, "content": content}
