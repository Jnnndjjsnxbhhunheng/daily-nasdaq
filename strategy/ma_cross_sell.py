from __future__ import annotations

from typing import Dict, Tuple


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

    if len(hist) < 260:
        return None, "数据不足，无法计算 MA200 交叉"

    close = hist["Close"]
    ma200 = close.rolling(window=200).mean()

    price = float(close.iloc[-1])
    prev_price = float(close.iloc[-2])
    ma_now = float(ma200.iloc[-1])
    ma_prev = float(ma200.iloc[-2])

    high_250 = float(close.tail(250).max())
    drawdown = (price - high_250) / high_250

    return {
        "date": hist.index[-1].strftime("%Y-%m-%d"),
        "price": round(price, 2),
        "prev_price": round(prev_price, 2),
        "ma200": round(ma_now, 2),
        "prev_ma200": round(ma_prev, 2),
        "drawdown": drawdown,
    }, None


def _calculate_strategy(data: Dict[str, float | str], base_amount: float) -> Tuple[str, float, str, float]:
    price = float(data["price"])
    prev_price = float(data["prev_price"])
    ma200 = float(data["ma200"])
    prev_ma200 = float(data["prev_ma200"])
    drawdown = float(data["drawdown"])

    crossed_up = prev_price <= prev_ma200 and price > ma200
    crossed_down = prev_price >= prev_ma200 and price < ma200

    if crossed_up:
        ratio = 2.0 if drawdown <= -0.20 else 1.0
        amount = base_amount * ratio
        reason = "🟢 上穿 MA200（金叉）"
        if ratio > 1.0:
            reason += " + 回撤超20%加码"
        return "buy", amount, reason, ratio

    if crossed_down:
        return "sell", 0.0, "🔴 下穿 MA200（死叉），卖出趋势仓位", 0.0

    return "hold", 0.0, "🟡 未发生交叉，维持当前仓位", 0.0


def run(*, base_amount: float = 10000, symbol: str = "QQQ") -> Dict[str, str]:
    data, err = _get_market_data(symbol)
    if err:
        return {"title": "获取数据失败", "content": err}

    action, amount, reason, ratio = _calculate_strategy(data, base_amount=base_amount)
    dd_str = f"{float(data['drawdown']) * 100:.2f}%"

    if action == "buy":
        title = f"MA交叉信号: 买入 {amount:.0f} 元"
        action_line = f"💰 <b>建议操作: 买入 {amount:.0f} 元</b> (基准{ratio:.1f}倍)<br>"
    elif action == "sell":
        title = "MA交叉信号: 卖出"
        action_line = "💰 <b>建议操作: 卖出趋势仓位（100%）</b><br>"
    else:
        title = "MA交叉信号: 持有"
        action_line = "💰 <b>建议操作: 持有（不新增）</b><br>"

    content = (
        f"📅 日期: {data['date']}<br>"
        f"🧾 标的: {symbol}<br>"
        f"💲 当前价格: ${data['price']}<br>"
        f"📏 MA200: ${data['ma200']}<br>"
        f"📉 近250日高点回撤: {dd_str}<br>"
        f"-----------------------<br>"
        f"💡 <b>信号说明: {reason}</b><br>"
        f"{action_line}"
    )
    return {"title": title, "content": content}

