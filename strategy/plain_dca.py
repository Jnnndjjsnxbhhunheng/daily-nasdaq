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
        hist = ticker.history(period="1mo")
    except Exception as e:
        return None, f"下载行情失败: {e}"
    if len(hist) == 0:
        return None, "没有获取到行情数据"

    current_price = float(hist["Close"].iloc[-1])
    last_date = hist.index[-1].strftime("%Y-%m-%d")

    return {
        "date": last_date,
        "price": round(current_price, 2),
    }, None


def run(*, base_amount: float = 10000, symbol: str = "QQQ") -> Dict[str, str]:
    data, err = _get_market_data(symbol)
    if err:
        return {"title": "获取数据失败", "content": err}

    ratio = 1.0
    amount = base_amount

    title = f"纳斯达克定投信号(普通定投): {ratio}倍 买入{int(amount)}元"
    content = (
        f"📅 日期: {data['date']}<br>"
        f"🧾 标的: {symbol}<br>"
        f"💲 最新价格: ${data['price']}<br>"
        f"-----------------------<br>"
        f"💡 <b>执行策略: 固定金额定投，不做择时。</b><br>"
        f"💰 <b>建议买入: {amount} 元</b> (基准{ratio}倍)<br>"
    )
    return {"title": title, "content": content}
