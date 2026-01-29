"""
多因子动态定投策略 (Multi-Factor Dynamic DCA)

核心改进点（相比现有策略）：
1. 多周期回撤融合：同时考虑 6 个月和 52 周回撤，综合判断
2. 趋势确认：加入 MA200 判断大趋势方向
3. RSI 超卖信号：加入 RSI 指标确认超卖区域
4. 动态资产配置：根据市场状态调整 VOO/QQQ 权重
5. 多重确认机制：需要多个指标同时满足才触发高档位加仓
6. 更精细的档位：6 档设计，加仓更平滑
7. 信号强度评分：综合多因子给出信号强度分数
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class Signal:
    """单个信号的状态"""
    name: str
    triggered: bool
    value: float
    threshold: float
    weight: float  # 信号权重
    description: str


@dataclass(frozen=True)
class Tier:
    """加仓档位"""
    name: str
    min_score: float  # 最低信号分数
    extra_ratio: float  # 相对月定投的加码比例
    use_pool_ratio: float | None  # 动用年度金池比例（None 表示不动用）
    note: str


# 6 档设计，基于信号强度分数
TIERS: List[Tier] = [
    Tier(name="档位5-极端", min_score=90, extra_ratio=0.0, use_pool_ratio=0.6, note="极端恐慌：动用年度金池 60%"),
    Tier(name="档位4-恐慌", min_score=75, extra_ratio=0.0, use_pool_ratio=0.35, note="深度恐慌：动用年度金池 35%"),
    Tier(name="档位3-深跌", min_score=55, extra_ratio=1.0, use_pool_ratio=None, note="深度回调：加码 100%"),
    Tier(name="档位2-回调", min_score=35, extra_ratio=0.5, use_pool_ratio=None, note="中等回调：加码 50%"),
    Tier(name="档位1-微跌", min_score=20, extra_ratio=0.25, use_pool_ratio=None, note="轻度回调：加码 25%"),
    Tier(name="档位0-正常", min_score=0, extra_ratio=0.0, use_pool_ratio=None, note="正常波动：仅定投"),
]


def _history(symbol: str, period: str):
    """获取历史数据"""
    try:
        import yfinance as yf
    except ModuleNotFoundError as e:
        raise ModuleNotFoundError("缺少依赖：yfinance") from e
    return yf.Ticker(symbol).history(period=period)


def _get_market_data(symbol: str) -> Dict[str, float]:
    """
    获取单个标的的多维度市场数据
    返回：当前价格、MA200、6个月回撤、52周回撤、RSI
    """
    hist = _history(symbol, period="2y")
    if len(hist) < 250:
        raise ValueError(f"{symbol} 数据不足 250 天")

    close = hist["Close"].dropna()
    current = float(close.iloc[-1])

    # MA200
    ma200 = float(close.rolling(window=200).mean().iloc[-1])

    # 6 个月（126 交易日）回撤
    tail_6m = close.tail(126) if len(close) >= 126 else close
    high_6m = float(tail_6m.max())
    dd_6m = (current - high_6m) / high_6m

    # 52 周（250 交易日）回撤
    tail_52w = close.tail(250)
    high_52w = float(tail_52w.max())
    dd_52w = (current - high_52w) / high_52w

    # RSI(14)
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(window=14).mean()
    rs = gain / loss.replace(0, 1e-10)
    rsi = float(100 - (100 / (1 + rs.iloc[-1])))

    return {
        "price": current,
        "ma200": ma200,
        "high_6m": high_6m,
        "high_52w": high_52w,
        "dd_6m": dd_6m,
        "dd_52w": dd_52w,
        "rsi": rsi,
    }


def _get_vix() -> float | None:
    """获取 VIX 指数"""
    try:
        hist = _history("^VIX", period="5d")
        if len(hist) == 0:
            return None
        return float(hist["Close"].dropna().iloc[-1])
    except Exception:
        return None


def _calculate_signals(
    dd_6m: float,
    dd_52w: float,
    price: float,
    ma200: float,
    rsi: float,
    vix: float | None,
) -> Tuple[List[Signal], float]:
    """
    计算所有信号并返回加权总分

    信号设计原则：
    - 每个信号独立触发，有各自的权重
    - 总分 = sum(信号权重) if triggered
    - 最高 100 分
    """
    signals: List[Signal] = []

    # 信号 1：6 个月回撤（权重 25）
    # 分段计分：-8% 开始触发，-30% 满分
    dd_6m_pct = dd_6m * 100
    if dd_6m_pct <= -8:
        # 线性插值：-8% -> 5分，-30% -> 25分
        score_6m = min(25, 5 + (abs(dd_6m_pct) - 8) * (20 / 22))
        signals.append(Signal(
            name="6个月回撤",
            triggered=True,
            value=dd_6m_pct,
            threshold=-8.0,
            weight=score_6m,
            description=f"回撤 {dd_6m_pct:.1f}%（触发阈值 -8%）"
        ))
    else:
        signals.append(Signal(
            name="6个月回撤",
            triggered=False,
            value=dd_6m_pct,
            threshold=-8.0,
            weight=0,
            description=f"回撤 {dd_6m_pct:.1f}%（未达阈值 -8%）"
        ))

    # 信号 2：52 周回撤（权重 25）
    dd_52w_pct = dd_52w * 100
    if dd_52w_pct <= -10:
        score_52w = min(25, 5 + (abs(dd_52w_pct) - 10) * (20 / 25))
        signals.append(Signal(
            name="52周回撤",
            triggered=True,
            value=dd_52w_pct,
            threshold=-10.0,
            weight=score_52w,
            description=f"回撤 {dd_52w_pct:.1f}%（触发阈值 -10%）"
        ))
    else:
        signals.append(Signal(
            name="52周回撤",
            triggered=False,
            value=dd_52w_pct,
            threshold=-10.0,
            weight=0,
            description=f"回撤 {dd_52w_pct:.1f}%（未达阈值 -10%）"
        ))

    # 信号 3：跌破 MA200（权重 15）
    below_ma = price < ma200
    ma_diff_pct = (price - ma200) / ma200 * 100
    if below_ma:
        # 跌破越多，分数越高
        score_ma = min(15, 8 + abs(ma_diff_pct) * 0.5)
        signals.append(Signal(
            name="跌破MA200",
            triggered=True,
            value=ma_diff_pct,
            threshold=0,
            weight=score_ma,
            description=f"价格低于 MA200 {abs(ma_diff_pct):.1f}%"
        ))
    else:
        signals.append(Signal(
            name="跌破MA200",
            triggered=False,
            value=ma_diff_pct,
            threshold=0,
            weight=0,
            description=f"价格高于 MA200 {ma_diff_pct:.1f}%"
        ))

    # 信号 4：RSI 超卖（权重 15）
    if rsi < 40:
        # RSI 40 -> 5分，RSI 20 -> 15分
        score_rsi = min(15, 5 + (40 - rsi) * (10 / 20))
        signals.append(Signal(
            name="RSI超卖",
            triggered=True,
            value=rsi,
            threshold=40,
            weight=score_rsi,
            description=f"RSI={rsi:.1f}（触发阈值 <40）"
        ))
    else:
        signals.append(Signal(
            name="RSI超卖",
            triggered=False,
            value=rsi,
            threshold=40,
            weight=0,
            description=f"RSI={rsi:.1f}（未达阈值 <40）"
        ))

    # 信号 5：VIX 恐慌（权重 20）
    if vix is not None:
        if vix > 20:
            # VIX 20 -> 5分，VIX 40 -> 20分
            score_vix = min(20, 5 + (vix - 20) * (15 / 20))
            signals.append(Signal(
                name="VIX恐慌",
                triggered=True,
                value=vix,
                threshold=20,
                weight=score_vix,
                description=f"VIX={vix:.1f}（触发阈值 >20）"
            ))
        else:
            signals.append(Signal(
                name="VIX恐慌",
                triggered=False,
                value=vix,
                threshold=20,
                weight=0,
                description=f"VIX={vix:.1f}（未达阈值 >20）"
            ))
    else:
        signals.append(Signal(
            name="VIX恐慌",
            triggered=False,
            value=0,
            threshold=20,
            weight=0,
            description="VIX 数据不可用"
        ))

    total_score = sum(s.weight for s in signals)
    return signals, total_score


def _pick_tier(score: float) -> Tier:
    """根据信号总分选择档位"""
    for tier in TIERS:
        if score >= tier.min_score:
            return tier
    return TIERS[-1]


def _dynamic_weights(
    score: float,
    base_weights: Tuple[float, float],
) -> Tuple[float, float]:
    """
    动态调整资产权重

    策略：市场恐慌时增加 VOO 比例（更稳健），正常时保持原比例
    - 分数 > 50：VOO 权重 +10%
    - 分数 > 70：VOO 权重 +15%
    """
    w_voo, w_qqq = base_weights

    if score > 70:
        shift = 0.15
    elif score > 50:
        shift = 0.10
    else:
        shift = 0.0

    # 确保权重在合理范围
    new_w_voo = min(0.7, w_voo + shift)
    new_w_qqq = 1.0 - new_w_voo

    return (new_w_voo, new_w_qqq)


def run(
    *,
    monthly_total_usd: float = 900,
    etfs: Tuple[str, str] = ("VOO", "QQQM"),
    base_weights: Tuple[float, float] = (0.5, 0.5),
    invest_day: int = 10,
    annual_reserve_pool_usd: float = 5000,
) -> Dict[str, str]:
    """
    多因子动态定投策略主入口

    参数：
    - monthly_total_usd: 每月基础定投金额
    - etfs: ETF 标的（默认 VOO, QQQM）
    - base_weights: 基础权重（默认各 50%）
    - invest_day: 每月定投日
    - annual_reserve_pool_usd: 年度加仓金池
    """
    today = _dt.date.today()
    should_dca = today.day == invest_day

    # 获取 VIX
    try:
        vix = _get_vix()
    except ModuleNotFoundError as e:
        return {"title": "策略运行失败", "content": str(e)}

    # 获取各标的数据
    per_symbol: Dict[str, Dict[str, float]] = {}
    all_signals: Dict[str, Tuple[List[Signal], float]] = {}

    try:
        for sym in etfs:
            data = _get_market_data(sym)
            per_symbol[sym] = data
            signals, score = _calculate_signals(
                dd_6m=data["dd_6m"],
                dd_52w=data["dd_52w"],
                price=data["price"],
                ma200=data["ma200"],
                rsi=data["rsi"],
                vix=vix,
            )
            all_signals[sym] = (signals, score)
    except (ModuleNotFoundError, ValueError) as e:
        return {"title": "策略运行失败", "content": str(e)}

    # 取最高信号分数作为决策依据
    max_score = max(s[1] for s in all_signals.values())
    max_score_symbol = [k for k, v in all_signals.items() if v[1] == max_score][0]

    # 选择档位
    tier = _pick_tier(max_score)

    # 动态调整权重
    weights = _dynamic_weights(max_score, base_weights)

    # 计算投资金额
    base_allocations = {sym: monthly_total_usd * w for sym, w in zip(etfs, weights)}

    if tier.use_pool_ratio is not None:
        extra_total = annual_reserve_pool_usd * tier.use_pool_ratio
        extra_note = f"动用年度金池 {tier.use_pool_ratio*100:.0f}%（假设金池 ${annual_reserve_pool_usd:.0f}）"
    else:
        extra_total = monthly_total_usd * tier.extra_ratio
        extra_note = f"加码 {tier.extra_ratio*100:.0f}%（相对月定投总额）"

    extra_allocations = {sym: extra_total * w for sym, w in zip(etfs, weights)}

    # 构建输出
    title = f"多因子定投信号: {tier.name}（信号分 {max_score:.0f}）"

    # 各标的数据行
    symbol_lines = []
    for sym in etfs:
        d = per_symbol[sym]
        sigs, sc = all_signals[sym]
        triggered_count = sum(1 for s in sigs if s.triggered)
        symbol_lines.append(
            f"<b>{sym}</b>: ${d['price']:.2f} | "
            f"MA200 ${d['ma200']:.2f} | "
            f"6M回撤 {d['dd_6m']*100:.1f}% | "
            f"52W回撤 {d['dd_52w']*100:.1f}% | "
            f"RSI {d['rsi']:.0f} | "
            f"信号 {triggered_count}/5 | "
            f"分数 {sc:.0f}"
        )

    # 信号详情（取分数最高的标的）
    signal_details = []
    for sig in all_signals[max_score_symbol][0]:
        status = "✅" if sig.triggered else "❌"
        signal_details.append(f"{status} {sig.name}: {sig.description} (+{sig.weight:.0f}分)")

    vix_str = f"{vix:.2f}" if vix is not None else "N/A"
    base_str = " | ".join([f"{sym} ${base_allocations[sym]:.0f}" for sym in etfs])
    extra_str = " | ".join([f"{sym} ${extra_allocations[sym]:.0f}" for sym in etfs])
    weight_str = " | ".join([f"{sym} {w*100:.0f}%" for sym, w in zip(etfs, weights)])

    content = (
        f"📅 日期: {today.isoformat()}<br>"
        f"🗓️ 定投日: 每月{invest_day}号｜本次{'✅执行' if should_dca else '⏸️不执行'}基础定投<br>"
        f"📌 标的: {', '.join(etfs)}<br>"
        f"🌡️ VIX: {vix_str}<br>"
        f"-----------------------<br>"
        f"<b>📊 市场数据</b><br>"
        + "<br>".join(symbol_lines)
        + "<br>-----------------------<br>"
        f"<b>📈 信号分析（{max_score_symbol}）</b><br>"
        + "<br>".join(signal_details)
        + f"<br><b>总分: {max_score:.0f}/100</b><br>"
        f"-----------------------<br>"
        f"🎯 触发档位: <b>{tier.name}</b><br>"
        f"📝 档位说明: {tier.note}<br>"
        f"⚖️ 动态权重: {weight_str}<br>"
        f"💵 基础定投（${monthly_total_usd:.0f}）: {base_str}<br>"
        f"➕ 额外加仓（${extra_total:.0f}）: {extra_str}<br>"
        f"🧾 加仓说明: {extra_note}<br>"
    )

    return {"title": title, "content": content}
