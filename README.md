# daily_nasdaq

纳斯达克 ETF（默认 QQQ）定投提醒脚本，支持 PushPlus 微信推送。

## 配置 PushPlus（不上传密钥）

1. 复制示例文件并填写你的 Token：
   - `cp .env.example .env`
   - 编辑 `.env`，设置 `PUSHPLUS_TOKEN=...`
2. `.env` 已在 `.gitignore` 中，不会被提交/上传。

## 运行

```bash
python main.py
```

如果不配置 `PUSHPLUS_TOKEN`，脚本只会在控制台打印，不发送推送。
