#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -d .venv ]; then
  python -m venv .venv
fi

source .venv/bin/activate
pip install -r requirements.txt

if [ ! -f .env ]; then
  cp .env.example .env
  echo "[提示] 已创建 .env，请按需填写配置。"
fi

python scripts/bootstrap_demo.py

exec uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload
