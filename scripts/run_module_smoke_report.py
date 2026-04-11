from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import settings
from app.db.models.asset import Asset
from app.db.models.gaokao_plan import GaokaoPlan
from app.schemas.gaokao import GaokaoConsultationRequest, GaokaoPlanRequest
from app.services.diagnostic_service import DiagnosticService
from app.services.essay_service import EssayService
from app.services.gaokao_report_service import GaokaoReportService
from app.services.gaokao_service import GaokaoService


@dataclass
class CaseResult:
    module: str
    case_name: str
    ok: bool
    duration_s: float
    highlights: list[str]
    error: str | None = None


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def make_fake_asset(object_key: str, mime_type: str = "text/plain") -> Asset:
    return Asset(
        user_id=0,
        bucket_provider=settings.oss_provider,
        bucket_name=settings.oss_bucket or "smoke",
        object_key=object_key,
        mime_type=mime_type,
        status="uploaded",
    )


def run_math_cases() -> list[CaseResult]:
    service = DiagnosticService()
    cases = [
        (
            "等差数列基础题",
            "已知等差数列{a_n}中，a_1=2，公差d=3，求前10项和S_10。",
        ),
        (
            "导数与最值题",
            "已知函数f(x)=x^3-3x^2+1，求函数的单调区间与极值。",
        ),
        (
            "概率统计题",
            "某班40名学生中男生24人，随机抽取2人，求恰有1名女生的概率。",
        ),
    ]
    results: list[CaseResult] = []
    for index, (case_name, raw_text) in enumerate(cases, start=1):
        started = time.perf_counter()
        try:
            asset = make_fake_asset(f"smoke/math/{index}.txt")
            result = service.classify_asset(asset=asset, raw_text=raw_text)
            classification = result["classification"]
            results.append(
                CaseResult(
                    module="数学诊断",
                    case_name=case_name,
                    ok=bool(classification.get("chapter")),
                    duration_s=time.perf_counter() - started,
                    highlights=[
                        f"章节：{classification.get('chapter')}",
                        f"置信度：{classification.get('confidence')}",
                        f"来源：{result.get('source')}",
                    ],
                )
            )
        except Exception as exc:
            results.append(
                CaseResult(
                    module="数学诊断",
                    case_name=case_name,
                    ok=False,
                    duration_s=time.perf_counter() - started,
                    highlights=[],
                    error=str(exc),
                )
            )
    return results


def run_essay_cases(subject: str, cases: list[tuple[str, str, str]]) -> list[CaseResult]:
    service = EssayService()
    module_name = "语文作文" if subject == "chinese" else "英语作文"
    results: list[CaseResult] = []
    for index, (case_name, title, raw_text) in enumerate(cases, start=1):
        started = time.perf_counter()
        try:
            asset = make_fake_asset(
                object_key=f"smoke/essay/{subject}/{index}.png",
                mime_type="image/png",
            )
            result = service.correct_asset(
                asset=asset,
                subject=subject,
                raw_text=raw_text,
                title=title,
            )
            results.append(
                CaseResult(
                    module=module_name,
                    case_name=case_name,
                    ok=bool(result.get("corrected_text")) and int(result.get("score_max") or 0) > 0,
                    duration_s=time.perf_counter() - started,
                    highlights=[
                        f"标题：{result.get('corrected_title')}",
                        f"得分：{result.get('score')}/{result.get('score_max')}",
                        f"PDF字节：{len(result.get('pdf_bytes') or b'')}",
                    ],
                )
            )
        except Exception as exc:
            results.append(
                CaseResult(
                    module=module_name,
                    case_name=case_name,
                    ok=False,
                    duration_s=time.perf_counter() - started,
                    highlights=[],
                    error=str(exc),
                )
            )
    return results


def run_gaokao_cases() -> list[CaseResult]:
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    report_service = GaokaoReportService()
    cases = [
        {
          "case_name": "物理类电子信息稳保方案",
          "payload": GaokaoPlanRequest(
              province="吉林省",
              score="455",
              rank="39104",
              subject_combination="物化生",
              preferred_majors="电子信息",
              preferred_cities="长春",
              career_preferences="工程技术",
              family_budget="学费不是主要问题",
              notes="接受调剂 后期考研",
              advisor_mode="rules_only",
          ),
        },
        {
          "case_name": "物理类自动换算位次",
          "payload": GaokaoPlanRequest(
              province="吉林省",
              score="567",
              rank="按系统自动换算即可",
              subject_combination="物化生",
              preferred_majors="计算机 电子",
              preferred_cities="长春 杭州",
              career_preferences="工程技术",
              family_budget="优先公办",
              notes="能接受外省和调剂",
              advisor_mode="rules_only",
          ),
        },
        {
          "case_name": "历史类文科问诊与方案",
          "payload": GaokaoPlanRequest(
              province="吉林省",
              score="545",
              rank="",
              subject_combination="史政地",
              preferred_majors="法学 汉语言文学",
              preferred_cities="长春 北京",
              career_preferences="考公考编",
              family_budget="预算一般",
              notes="优先双一流",
              advisor_mode="hybrid",
          ),
        },
    ]
    consult_cases = [
        GaokaoConsultationRequest(
            province="吉林省",
            score="567",
            rank="",
            subject_combination="物化生",
            preferred_majors="电子信息",
            preferred_cities="长春",
        ),
        GaokaoConsultationRequest(
            province="吉林省",
            score="545",
            rank="",
            subject_combination="史政地",
            preferred_majors="法学",
            preferred_cities="长春",
        ),
    ]
    results: list[CaseResult] = []
    with SessionLocal() as db:
        service = GaokaoService(db)
        for idx, consult_payload in enumerate(consult_cases, start=1):
            started = time.perf_counter()
            try:
                consultation = service.build_consultation(consult_payload)
                results.append(
                    CaseResult(
                        module="高考报考",
                        case_name=f"顾问问诊 {idx}",
                        ok=bool(consultation.get("questions")),
                        duration_s=time.perf_counter() - started,
                        highlights=[
                            f"readiness：{consultation.get('readiness')}",
                            f"追问数：{len(consultation.get('questions') or [])}",
                        ],
                    )
                )
            except Exception as exc:
                results.append(
                    CaseResult(
                        module="高考报考",
                        case_name=f"顾问问诊 {idx}",
                        ok=False,
                        duration_s=time.perf_counter() - started,
                        highlights=[],
                        error=str(exc),
                    )
                )

        for case in cases:
            started = time.perf_counter()
            try:
                payload = case["payload"]
                plan = service.build_plan(payload)
                fake_plan_model = GaokaoPlan(
                    user_id=0,
                    province=payload.province,
                    subject_combination=payload.subject_combination,
                    score=payload.score,
                    rank=payload.rank,
                    target_json={
                        "preferred_majors": payload.preferred_majors,
                        "preferred_cities": payload.preferred_cities,
                        "career_preferences": payload.career_preferences,
                        "family_budget": payload.family_budget,
                        "notes": payload.notes,
                    },
                    summary=plan["summary"],
                    details_json=plan,
                )
                pdf_bytes = report_service.build_pdf_bytes(fake_plan_model)
                results.append(
                    CaseResult(
                        module="高考报考",
                        case_name=case["case_name"],
                        ok=len(plan.get("recommendations") or []) > 0 and len(pdf_bytes) > 0,
                        duration_s=time.perf_counter() - started,
                        highlights=[
                            f"位次：{plan.get('calculated_rank')}",
                            f"主推荐数：{len(plan.get('recommendations') or [])}",
                            f"扩展池数：{len(plan.get('extended_pool') or [])}",
                            f"PDF字节：{len(pdf_bytes)}",
                            f"增强状态：{plan.get('llm_enhanced')}",
                        ],
                    )
                )
            except Exception as exc:
                results.append(
                    CaseResult(
                        module="高考报考",
                        case_name=case["case_name"],
                        ok=False,
                        duration_s=time.perf_counter() - started,
                        highlights=[],
                        error=str(exc),
                    )
                )
    return results


def build_report(results: list[CaseResult]) -> str:
    grouped: dict[str, list[CaseResult]] = {}
    for item in results:
        grouped.setdefault(item.module, []).append(item)

    lines = [
        f"# 模块回归测试报告",
        "",
        f"- 生成时间：{now_text()}",
        f"- 测试环境：本地开发环境 / `E:\\001_Math`",
        f"- 覆盖模块：数学诊断、语文作文、英语作文、高考报考",
        "",
        "## 汇总",
        "",
    ]

    passed = sum(1 for item in results if item.ok)
    total = len(results)
    lines.append(f"- 通过：{passed}/{total}")
    lines.append(f"- 失败：{total - passed}/{total}")
    lines.append("")

    for module, items in grouped.items():
        lines.append(f"## {module}")
        lines.append("")
        for item in items:
            status = "PASS" if item.ok else "FAIL"
            lines.append(f"### {status} | {item.case_name}")
            lines.append(f"- 耗时：{item.duration_s:.2f}s")
            if item.highlights:
                for highlight in item.highlights:
                    lines.append(f"- {highlight}")
            if item.error:
                lines.append(f"- 错误：{item.error}")
            lines.append("")
    return "\n".join(lines)


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    results: list[CaseResult] = []
    results.extend(run_math_cases())
    results.extend(
        run_essay_cases(
            "chinese",
            [
                (
                    "议论文基础批改",
                    "向上生长",
                    "成长从来不是一蹴而就的。只有在一次次挫折中学会整理自己，我们才能真正向上生长。",
                ),
                (
                    "记叙文表达优化",
                    "那一次我懂得了坚持",
                    "那天雨下得很大，我本来想放弃比赛，但是想到老师和同学的鼓励，我还是咬牙跑到了终点。",
                ),
            ],
        )
    )
    results.extend(
        run_essay_cases(
            "english",
            [
                (
                    "English short essay 1",
                    "My Dream School",
                    "I want to study in a university where I can learn computer science and join many practical projects. I know the road is hard, but I will keep working every day.",
                ),
                (
                    "English short essay 2",
                    "An Unforgettable Day",
                    "Last month I joined a volunteer activity in my community. Although I felt tired, I learned how important teamwork is and I became more confident.",
                ),
            ],
        )
    )
    results.extend(run_gaokao_cases())

    report_text = build_report(results)
    report_path = REPORT_DIR / f"module_smoke_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    report_path.write_text(report_text, encoding="utf-8")
    print(report_path)
    print(report_text)


if __name__ == "__main__":
    main()
