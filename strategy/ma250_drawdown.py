from __future__ import annotations

from typing import Dict, Tuple


def _get_market_data(symbol: str) -> Tuple[Dict[str, float | str] | None, str | None]:
    try:
        import yfinance as yf
    except ModuleNotFoundError:
        return None, "缺少依赖：yfinance（请先安装：pip install yfinance）"

    print(f"正在获取 {symbol} 的数据...")

    ticker = yf.Ticker(symbol)
    hist = ticker.history(period="2y")

    if len(hist) < 250:
        return None, "数据不足，无法计算年线"

    current_price = float(hist["Close"].iloc[-1])
    last_date = hist.index[-1].strftime("%Y-%m-%d")

    ma250 = float(hist["Close"].rolling(window=250).mean().iloc[-1])

    high_52w = float(hist["Close"].tail(250).max())
    drawdown = (current_price - high_52w) / high_52w

    return {
        "date": last_date,
        "price": round(current_price, 2),
        "ma250": round(ma250, 2),
        "high": round(high_52w, 2),
        "drawdown": drawdown,
    }, None


def _calculate_strategy(data: Dict[str, float | str], base_amount: float) -> Tuple[float, float, str]:
    price = float(data["price"])
    ma250 = float(data["ma250"])
    dd = float(data["drawdown"])

    ratio = 1.0
    reason = "市场正常 (价格 > 年线)"

    if dd <= -0.30:
        ratio = 5.0
        reason = "🚨 极度恐慌 (回撤超30%)，钻石坑机会！"
    elif dd <= -0.20:
        ratio = 3.0
        reason = "⚠️ 深度回调 (回撤超20%)，加大力度！"
    elif price < ma250:
        ratio = 2.0
        reason = "📉 跌破年线 (MA250)，价值低估区。"
    else:
        ratio = 1.0
        reason = "📈 趋势向上 (价格 > 年线)，保持在场。"

    buy_amount = base_amount * ratio
    return ratio, buy_amount, reason


def run(*, base_amount: float = 10000, symbol: str = "QQQ") -> Dict[str, str]:
    data, err = _get_market_data(symbol)
    if err:
        return {"title": "获取数据失败", "content": err}

    ratio, amount, reason = _calculate_strategy(data, base_amount=base_amount)
    dd_str = f"{float(data['drawdown']) * 100:.2f}%"

    title = f"纳斯达克定投信号: {ratio}倍 买入{int(ratio * base_amount)}元"
    content = (
        f"📅 日期: {data['date']}<br>"
        f"🧾 标的: {symbol}<br>"
        f"💲 最新价格: ${data['price']}<br>"
        f"📏 250日年线: ${data['ma250']}<br>"
        f"📉 当前回撤: {dd_str}<br>"
        f"-----------------------<br>"
        f"💡 <b>执行策略: {reason}</b><br>"
        f"💰 <b>建议买入: {amount} 元</b> (基准{ratio}倍)<br>"
    )
    return {"title": title, "content": content}
