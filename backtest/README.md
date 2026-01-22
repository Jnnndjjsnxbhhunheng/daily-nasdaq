# Backtest

用过去约 20 年的数据回测定投策略（默认用 `QQQ` 作为纳指 100 的常用代理），并输出：

- 近 3 年年化收益（`trailing_3y_xirr`，按现金流计算的年化 IRR）
- 全周期年化收益（`full_period_xirr`）

## 依赖

```bash
pip install yfinance pandas
```

## 运行

```bash
python -m backtest.run_backtest --strategy ma250_drawdown --symbol QQQ --base-amount 10000 --invest-day 10 --period 20y
```

说明：
- `--invest-day` 为每月定投的“日”（1..28），会自动匹配到当月第一个 `day>=invest-day` 的交易日。

## 回测两个策略

1) `ma250_drawdown`（单标的，原策略）

```bash
python -m backtest.run_backtest --strategy ma250_drawdown --symbol QQQ --base-amount 10000 --invest-day 10 --period 20y
```

2) `etf_dca_dip_buy`（双标的：每月定投 + 下跌分档加仓）

由于 `VOO/QQQM` 上市时间不够 20 年，回测默认使用长历史代理：
- `SPY` 代理 `VOO`
- `QQQ` 代理 `QQQM`

```bash
python -m backtest.run_backtest --strategy etf_dca_dip_buy --symbols SPY,QQQ --monthly-total 900 --annual-pool 4000 --weights 0.5,0.5 --invest-day 10 --period 20y
```

## 对比图（柱状）

一次性跑两个策略并生成对比柱状图：

```bash
python -m backtest.run_backtest --strategy all --symbol QQQ --base-amount 10000 --symbols SPY,QQQ --monthly-total 900 --annual-pool 4000 --weights 0.5,0.5 --invest-day 10 --period 20y --out-dir backtest
```

会在输出目录生成两张柱状对比图：
- `total_return_compare.png`：总收益率（`final_value / total_invested - 1`）
- `trailing_3y_xirr_compare.png`：近3年年化（`trailing_3y_xirr`）

如需生成图片，请先安装：

```bash
pip install matplotlib
```
