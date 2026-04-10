# Local Development Setup

## 1. Prepare `.env`

Create `.env` from `.env.example` and fill in at least:

```env
DATABASE_URL=postgresql+psycopg://aimath:aimath_dev_password@localhost:5432/aimath
REDIS_URL=redis://localhost:6379/0
JWT_SECRET=replace_with_a_real_secret
WECHAT_APPID=your_real_wechat_appid
WECHAT_SECRET=your_real_wechat_secret
OSS_PROVIDER=aliyun
OSS_ENDPOINT=https://oss-cn-hangzhou.aliyuncs.com
OSS_BUCKET=your_bucket
OSS_ACCESS_KEY_ID=your_access_key_id
OSS_ACCESS_KEY_SECRET=your_access_key_secret
OSS_PUBLIC_BASE_URL=https://your-static-domain.com
```

## 2. Start local services

```bash
docker compose -f docker/docker-compose.yml up -d postgres redis
```

Or run the full local stack:

```bash
docker compose -f docker/docker-compose.yml up --build
```

## 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

## 4. Apply the first migration

```bash
alembic upgrade head
```

## 5. Start the API locally

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 6. Smoke test

```bash
curl http://127.0.0.1:8000/api/v1/health
```
