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
