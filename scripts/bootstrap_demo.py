"""初始化一个可直接联调的 demo 数据集。"""

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.db import init_db, create_org, create_user, list_orgs, list_users
from core.settings import settings


def main():
    init_db()

    existing_orgs = list_orgs()
    if existing_orgs:
        org = existing_orgs[-1]
        org_id = org["id"]
        print(f"[*] 复用现有机构: id={org_id}, name={org['name']}")
    else:
        org_id = create_org("Demo School", plan="pro", status="active")
        print(f"[+] 创建机构成功: org_id={org_id}")

    existing_users = list_users(org_id=org_id)
    demo_user = next((u for u in existing_users if u["name"] == "demo_teacher"), None)
    if demo_user:
        user_id = demo_user["id"]
        print(f"[*] 复用现有账号: user_id={user_id}, name=demo_teacher")
    else:
        user_id = create_user(
            org_id=org_id,
            role="teacher",
            name="demo_teacher",
            email="demo@math-gen.local",
            password="demo123",
        )
        print(f"[+] 创建账号成功: user_id={user_id}")

    print("\n=== Demo 联调信息 ===")
    print(f"APP_DB_PATH={settings.app_db_path}")
    print(f"org_id={org_id}")
    print("username=demo_teacher")
    print("password=demo123")
    print("\n登录接口: POST /v0/auth/login")


if __name__ == "__main__":
    main()
