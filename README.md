# Math_Gen (v0.3 默认方案迭代版)

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

## 运行测试
```bash
python -m unittest discover -s tests -p "test_*.py"
```

## 运行 API
```bash
uvicorn api_server:app --reload --host 0.0.0.0 --port 8000
```

## 一键本地可运行（推荐）
```bash
bash scripts/run_local.sh
```
这会自动：
1) 创建虚拟环境并安装依赖；  
2) 初始化数据库并生成 demo 账号；  
3) 启动 API 服务。

## 一键联调冒烟（服务启动后）
```bash
bash scripts/smoke_flow.sh
```

### v0.2 新增接口（机构/用户）
- `POST /v0/orgs`：创建机构
- `GET /v0/orgs`：机构列表
- `POST /v0/users`：创建用户
- `GET /v0/users?org_id=1`：用户列表（可按机构过滤）

如果设置了 `ADMIN_TOKEN`，以上接口需在 Header 里传 `X-Admin-Token`。

### v0.3 新增接口（登录/题库/组卷）
- `POST /v0/auth/login`：用户登录，返回 Bearer Token
- `POST /v0/questions`：创建题目（需 Bearer Token）
- `GET /v0/questions`：题目列表（按机构隔离）
- `POST /v0/papers/generate`：按章节/难度/题量生成试卷数据（需 Bearer Token）

> v0.3 默认流程：管理员建机构/账号 → 教师登录拿 token → 教师录题 → 调用组卷接口出卷。

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

## 常见问题（运行不通）
- 若 GUI 工具（`Question_Recorder.py` / `Batch_Auditor.py`）无法调用模型，请先确认：
  - 已设置 `GEMINI_API_KEY` / `OPENAI_API_KEY`
  - 若有网络代理需求，设置 `PROXY_URL`
- 本项目已移除脚本内置固定代理端口，改为读取环境变量，避免不同机器端口不一致导致连接失败。
- OpenAI 接口报文若有版本差异（`chat.completions` 与 `responses`），项目已做自动兼容降级处理。
- 若 API 启动时报数据库目录错误，请检查 `APP_DB_PATH` 的父目录是否有写权限。
- 若登录后接口返回 401，请检查 `Authorization: Bearer <token>` 是否正确，及 `JWT_SECRET` 是否变更。
