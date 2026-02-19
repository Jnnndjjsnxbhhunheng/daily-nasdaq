# Backtest

使用历史数据回测策略并输出：

- `trailing_3y_xirr`：近 3 年年化收益（现金流口径）
- `full_period_xirr`：全周期年化收益（现金流口径）

## 依赖

```bash
pip install yfinance pandas matplotlib
```

## 支持策略

- `ma250_drawdown`
- `ma200_drawdown`
- `ma150_drawdown`
- `discount_dca`
- `market_breadth_dca`
- `plain_dca`（每日固定金额定投）
- `etf_dca_dip_buy`
- `all`（一次运行并生成对比图）

## 运行示例

```bash
python -m backtest.run_backtest --strategy ma250_drawdown --symbol QQQ --base-amount 10000 --invest-day 10 --period 20y
python -m backtest.run_backtest --strategy ma200_drawdown --symbol QQQ --base-amount 10000 --invest-day 10 --period 20y
python -m backtest.run_backtest --strategy ma150_drawdown --symbol QQQ --base-amount 10000 --invest-day 10 --period 20y
python -m backtest.run_backtest --strategy discount_dca --symbol QQQ --base-amount 10000 --invest-day 10 --period 20y
python -m backtest.run_backtest --strategy market_breadth_dca --symbol QQQ --base-amount 10000 --invest-day 10 --period 20y
python -m backtest.run_backtest --strategy plain_dca --symbol QQQ --base-amount 10000 --period 20y
```

双 ETF 策略（20 年回测常用代理：`SPY->VOO`, `QQQ->QQQM`）：

```bash
python -m backtest.run_backtest --strategy etf_dca_dip_buy --symbols SPY,QQQ --monthly-total 900 --annual-pool 4000 --weights 0.5,0.5 --invest-day 10 --period 20y
```

## 生成对比图

```bash
python -m backtest.run_backtest --strategy all --symbol QQQ --base-amount 10000 --symbols SPY,QQQ --monthly-total 900 --annual-pool 4000 --weights 0.5,0.5 --invest-day 10 --period 20y --out-dir backtest
```

生成前端看板 JSON：

```bash
python -m backtest.run_backtest --strategy all --symbol QQQ --base-amount 10000 --symbols SPY,QQQ --monthly-total 900 --annual-pool 4000 --weights 0.5,0.5 --invest-day 10 --period 20y --out-dir backtest --json-out frontend/data/backtest_dashboard.json
```

输出文件：
- `yearly_xirr_compare.png`
- `total_return_compare.png`
- `trailing_3y_xirr_compare.png`
- `frontend/data/backtest_dashboard.json`（若使用 `--json-out`）

说明：
- `--invest-day` 仅用于按“月定投”的策略（1..28）
- `plain_dca` 是“每个交易日都投固定金额”，不使用 `--invest-day`
- Yahoo 数据源可能触发限流（`YFRateLimitError`），建议稍后重试
