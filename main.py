import requests
import os
from pathlib import Path

from strategy import get_strategy, list_strategies

# ================= 配置区域 =================
# 1. 你的基础定投金额 (例如：每次计划投 10000 元)
BASE_AMOUNT = 10000 

def _load_env_file(filename: str = ".env") -> None:
    env_path = Path(__file__).resolve().parent / filename
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_env_file()

# 2. PushPlus Token (去 pushplus.plus 官网免费申请一个，填到 .env 里)
# 如果留空，则只在电脑屏幕打印，不发送微信
PUSHPLUS_TOKEN = os.getenv("PUSHPLUS_TOKEN", "").strip()

# 3. 选择策略
# - ma150_drawdown: QQQ 150日均线+回撤策略
# - ma200_drawdown: QQQ 200日均线+回撤策略
# - ma250_drawdown: 原本的 QQQ 年线+回撤策略
# - ma_cross_sell: QQQ MA200 交叉买卖策略
# - macd_weekly: QQQ 周线MACD趋势策略
# - discount_dca: QQQ 折扣定投 (20周高点折扣 + MA50)
# - market_breadth_dca: QQQ 市场宽度 + 回撤策略
# - rsi_reversion: QQQ RSI均值回归策略
# - plain_dca: 普通固定金额定投
# - etf_dca_dip_buy: VOO+QQQM 每月定投 + 下跌分档加仓策略
STRATEGY_KEY = os.getenv("STRATEGY", "ma250_drawdown").strip() or "ma250_drawdown"
# ===========================================

def send_push(title, content):
    """发送微信推送 (使用 PushPlus)"""
    if not PUSHPLUS_TOKEN:
        print(">> 未配置 PushPlus Token，跳过推送")
        return
    
    url = "http://www.pushplus.plus/send"
    data = {
        "token": PUSHPLUS_TOKEN,
        "title": title,
        "content": content,
        "template": "html"
    }
    try:
        r = requests.post(url, json=data)
        print(f">> 推送结果: {r.text}")
    except Exception as e:
        print(f">> 推送失败: {e}")

def main():
    try:
        runner = get_strategy(STRATEGY_KEY)
    except KeyError as e:
        print(str(e))
        print(f"Available strategies: {', '.join(sorted(list_strategies()))}")
        return

    if STRATEGY_KEY in {
        "ma250_drawdown",
        "ma200_drawdown",
        "ma150_drawdown",
        "ma_cross_sell",
        "macd_weekly",
        "discount_dca",
        "market_breadth_dca",
        "rsi_reversion",
        "plain_dca",
    }:
        result = runner(base_amount=BASE_AMOUNT, symbol=os.getenv("SYMBOL", "QQQ").strip() or "QQQ")
    else:
        result = runner()

    title = result["title"]
    content = result["content"]

    # 1. 控制台打印
    print("\n" + "="*30)
    print(title)
    print(content.replace("<br>", "\n").replace("<b>", "").replace("</b>", ""))
    print("="*30 + "\n")

    # 2. 发送推送
    send_push(title, content)

if __name__ == "__main__":
    main()
