# Frontend 回测看板

该目录是独立前端页面，支持：

- 查看每个策略的回测指标（总投入、期末资产、收益率、年化等）
- 左侧点击策略后高亮该策略
- 左侧可多选显示/隐藏策略曲线（全选、仅看当前）
- 图表包含：年度 XIRR 折线、总收益率柱状图、近三年 XIRR 柱状图

## 1) 生成数据 JSON

先在项目根目录执行：

```bash
python -m backtest.run_backtest --strategy all --symbol QQQ --base-amount 10000 --symbols SPY,QQQ --monthly-total 900 --annual-pool 4000 --weights 0.5,0.5 --invest-day 10 --period 20y --out-dir backtest --json-out frontend/data/backtest_dashboard.json
```

说明：

- `frontend/data/backtest_dashboard.json` 是看板优先读取的数据文件
- 如果该文件不存在，会回退读取 `frontend/data/backtest_dashboard.sample.json`

## 2) 启动静态服务

```bash
python -m http.server 8000
```

浏览器打开：

`http://localhost:8000/frontend/`
