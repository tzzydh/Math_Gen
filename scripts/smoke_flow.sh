#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
ORG_ID="${ORG_ID:-1}"
USER_NAME="${USER_NAME:-demo_teacher}"
PASSWORD="${PASSWORD:-demo123}"

LOGIN_RESP=$(curl -sS -X POST "$BASE_URL/v0/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"org_id\":$ORG_ID,\"name\":\"$USER_NAME\",\"password\":\"$PASSWORD\"}")

TOKEN=$(echo "$LOGIN_RESP" | python -c 'import json,sys;print(json.load(sys.stdin).get("access_token",""))')
if [ -z "$TOKEN" ]; then
  echo "[失败] 登录失败: $LOGIN_RESP"
  exit 1
fi

echo "[成功] 登录获取 token"

curl -sS -X POST "$BASE_URL/v0/questions" \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"stem":"1+1=?","options":["1","2","3","4"],"answer":"2","analysis":"基础计算","difficulty":"易","chapter":"第1讲 集合"}'

echo "\n[成功] 已写入题目，开始组卷..."

curl -sS -X POST "$BASE_URL/v0/papers/generate" \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"chapter":"第1讲 集合","difficulty":"易","num_questions":1}'

echo "\n[完成] smoke flow 通过"
