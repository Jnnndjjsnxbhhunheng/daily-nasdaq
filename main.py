import yfinance as yf
import pandas as pd
import datetime
import requests

# ================= 配置区域 =================
# 1. 你的基础定投金额 (例如：每次计划投 10000 元)
BASE_AMOUNT = 10000 

# 2. PushPlus Token (去 pushplus.plus 官网免费申请一个，填在这里)
# 如果留空，则只在电脑屏幕打印，不发送微信
PUSHPLUS_TOKEN = "" 

# 3. 标的物 (QQQ 代表纳斯达克100 ETF)
SYMBOL = "QQQ"
# ===========================================

def get_market_data():
    """获取行情数据并计算关键指标"""
    print(f"正在获取 {SYMBOL} 的数据...")
    
    # 获取过去 2 年的数据，足以计算 MA250
    ticker = yf.Ticker(SYMBOL)
    hist = ticker.history(period="2y")
    
    if len(hist) < 250:
        return None, "数据不足，无法计算年线"

    # 获取最新收盘价
    current_price = hist['Close'].iloc[-1]
    last_date = hist.index[-1].strftime("%Y-%m-%d")

    # 计算 MA250 (250日均线)
    ma250 = hist['Close'].rolling(window=250).mean().iloc[-1]

    # 计算最大回撤 (基于过去 1 年的最高点)
    # 取过去250个交易日的最高价
    high_52w = hist['Close'].tail(250).max()
    drawdown = (current_price - high_52w) / high_52w  # 结果是负数，例如 -0.2

    return {
        "date": last_date,
        "price": round(current_price, 2),
        "ma250": round(ma250, 2),
        "high": round(high_52w, 2),
        "drawdown": drawdown
    }, None

def calculate_strategy(data):
    """根据策略逻辑计算买入金额"""
    price = data['price']
    ma250 = data['ma250']
    dd = data['drawdown'] # 例如 -0.15 代表跌了15%
    
    # 策略逻辑层级 (优先匹配最极端的下跌)
    
    ratio = 1.0
    reason = "市场正常 (价格 > 年线)"
    
    # 逻辑 1: 钻石坑 (回撤 > 30%) -> 5倍定投
    if dd <= -0.30:
        ratio = 5.0
        reason = "🚨 极度恐慌 (回撤超30%)，钻石坑机会！"
    
    # 逻辑 2: 黄金坑 (回撤 > 20%) -> 3倍定投
    elif dd <= -0.20:
        ratio = 3.0
        reason = "⚠️ 深度回调 (回撤超20%)，加大力度！"
        
    # 逻辑 3: 跌破年线 (价格 < MA250) -> 2倍定投
    elif price < ma250:
        ratio = 2.0
        reason = "📉 跌破年线 (MA250)，价值低估区。"
        
    # 逻辑 4: 正常定投
    else:
        ratio = 1.0
        reason = "📈 趋势向上 (价格 > 年线)，保持在场。"

    buy_amount = BASE_AMOUNT * ratio
    
    return ratio, buy_amount, reason

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
    data, err = get_market_data()
    if err:
        print(err)
        return

    ratio, amount, reason = calculate_strategy(data)
    
    # 格式化回撤百分比
    dd_str = f"{data['drawdown']*100:.2f}%"
    
    # 构建消息内容
    title = f"纳斯达克定投信号: {ratio}倍"
    content = (
        f"📅 日期: {data['date']}<br>"
        f"💲 最新价格: ${data['price']}<br>"
        f"📏 250日年线: ${data['ma250']}<br>"
        f"📉 当前回撤: {dd_str}<br>"
        f"-----------------------<br>"
        f"💡 <b>执行策略: {reason}</b><br>"
        f"💰 <b>建议买入: {amount} 元</b> (基准{ratio}倍)<br>"
    )

    # 1. 控制台打印
    print("\n" + "="*30)
    print(title)
    print(content.replace("<br>", "\n").replace("<b>", "").replace("</b>", ""))
    print("="*30 + "\n")

    # 2. 发送推送
    send_push(title, content)

if __name__ == "__main__":
    main()