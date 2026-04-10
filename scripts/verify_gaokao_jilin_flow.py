from __future__ import annotations

import json
import urllib.request


API_BASE = "http://127.0.0.1:8000/api/v1"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIzIiwidWlkIjozLCJvcGVuaWQiOiJvWWlBRzV0YVRfbXg4c0Z3VXJudGkwUnZ3MzZZIiwiZXhwIjoxNzc1OTE5MDcxfQ.e_YCq-2MJ8FbklNeqkpkClb4iOUMoqIeb-2QZM5qlVo"


def post_json(path: str, payload: dict) -> dict:
    request = urllib.request.Request(
        f"{API_BASE}{path}",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> None:
    physics_payload = {
        "province": "吉林省",
        "score": "560",
        "rank": "",
        "subject_combination": "物化生",
        "preferred_majors": "计算机,电气,自动化",
        "preferred_cities": "长春,天津,北京",
        "career_preferences": "就业稳定,工程技术",
        "family_budget": "优先公办",
        "notes": "愿意去省外, 不考虑中外合作",
    }
    history_payload = {
        "province": "吉林省",
        "score": "545",
        "rank": "",
        "subject_combination": "史政地",
        "preferred_majors": "师范,法学,会计",
        "preferred_cities": "长春,沈阳",
        "career_preferences": "稳定编制",
        "family_budget": "优先公办",
        "notes": "更看重就业稳定",
    }

    physics_result = post_json("/gaokao/plan", physics_payload)
    history_result = post_json("/gaokao/plan", history_payload)

    print("physics track:", physics_result["track"], "rank:", physics_result["calculated_rank"])
    print("physics first:", physics_result["recommendations"][0]["school"], physics_result["recommendations"][0]["bucket"])
    print("history track:", history_result["track"], "rank:", history_result["calculated_rank"])
    print("history first:", history_result["recommendations"][0]["school"], history_result["recommendations"][0]["bucket"])


if __name__ == "__main__":
    main()
