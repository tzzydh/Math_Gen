# Math_Gen (v0.1 安全可运行版)

## 本次升级内容
- 移除代码中的明文 API Key，统一改为环境变量。
- 新增 `core/settings.py` 统一配置管理。
- 新增 `api_server.py` 提供最小可运行 API (`/health`, `/config/check`)。
- 新增 `.env.example` 和 `requirements.txt`，便于部署。

## 快速启动
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# 手动填写 .env 中的 OPENAI_API_KEY/GEMINI_API_KEY
```

## 运行 API
```bash
uvicorn api_server:app --reload --host 0.0.0.0 --port 8000
```

## 运行脚本
- 题库 PDF 抽题入库：
```bash
python Headless_Miner.py
```
- 学情诊断报告：
```bash
python Diagnostic_Engine.py
```

> 注意：上述脚本在未设置必要环境变量时会直接报错提醒。
