# daily_nasdaq

纳斯达克 ETF（默认 QQQ）定投提醒脚本，支持 PushPlus 微信推送。

## 配置 PushPlus（不上传密钥）

1. 复制示例文件并填写你的 Token：
   - `cp .env.example .env`
   - 编辑 `.env`，设置 `PUSHPLUS_TOKEN=...`
2. `.env` 已在 `.gitignore` 中，不会被提交/上传。

## 选择策略

在 `.env` 里设置 `STRATEGY`：

- `STRATEGY=ma250_drawdown`：原本的 QQQ 年线+回撤加码策略（默认）
- `STRATEGY=etf_dca_dip_buy`：VOO+QQQM 每月10号定投 + 近6个月高点回撤分档加仓策略

## 运行

```bash
python main.py
```

如果不配置 `PUSHPLUS_TOKEN`，脚本只会在控制台打印，不发送推送。

## 回测（20年数据 + 近3年年化）

回测脚本在 `backtest/` 下，默认用 `QQQ` 作为纳指100的常用代理，并输出：
- `trailing_3y_xirr`：近3年年化收益（按现金流 IRR/XIRR 计算）
- `full_period_xirr`：全周期年化收益（按现金流 IRR/XIRR 计算）

依赖：

- `pip install yfinance pandas matplotlib`

运行两个策略（分别执行两次）：

- `python -m backtest.run_backtest --strategy ma250_drawdown --symbol QQQ --base-amount 10000 --invest-day 10 --period 20y`
  - 原本的 QQQ 年线（MA250）+ 回撤加码策略
- `python -m backtest.run_backtest --strategy etf_dca_dip_buy --symbols SPY,QQQ --monthly-total 900 --annual-pool 4000 --weights 0.5,0.5 --invest-day 10 --period 20y`
  - VOO+QQQM 的定投+下跌加仓策略（回测默认用 `SPY,QQQ` 代理 `VOO,QQQM`，因为后者历史不足20年）

一次跑完两个策略并生成对比图（输出目录默认 `backtest/`）：

- `python -m backtest.run_backtest --strategy all --symbol QQQ --base-amount 10000 --symbols SPY,QQQ --monthly-total 900 --annual-pool 4000 --weights 0.5,0.5 --invest-day 10 --period 20y --out-dir backtest`

### 展示图

总收益率柱状对比：

![total_return_compare](backtest/total_return_compare.png)

近三年三年化（XIRR）柱状对比：

![trailing_3y_xirr_compare](backtest/trailing_3y_xirr_compare.png)
