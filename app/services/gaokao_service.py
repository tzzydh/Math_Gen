from __future__ import annotations

import math
import re
from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.gaokao_admission_baseline import GaokaoAdmissionBaseline
from app.db.models.gaokao_control_line import GaokaoControlLine
from app.db.models.gaokao_score_rank import GaokaoScoreRank
from app.schemas.gaokao import GaokaoPlanRequest


YEAR = 2025
PROVINCE = "吉林省"

TRACK_LABELS = {
    "physics": "物理类",
    "history": "历史类",
}

BUCKET_LABELS = {
    "chong": "冲",
    "wen": "稳",
    "bao": "保",
}

DEFAULT_BUCKET_COUNTS = {
    "chong": 4,
    "wen": 4,
    "bao": 4,
}


class GaokaoService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def build_plan(self, payload: GaokaoPlanRequest) -> dict[str, Any]:
        province = self._normalize_province(payload.province)
        if province != PROVINCE:
            raise ValueError("当前高考数据版只支持吉林省")

        score = self._parse_positive_int(payload.score, "分数")
        track = self._infer_track(payload.subject_combination)
        control_lines = self._get_control_lines(track)
        calculated_rank = self._resolve_rank(track=track, score=score, raw_rank=payload.rank)
        baselines = self._get_baselines(track)
        if not baselines:
            raise ValueError("吉林省公开录取基线尚未导入")

        recommendations = self._build_recommendations(
            payload=payload,
            track=track,
            score=score,
            rank=calculated_rank,
            baselines=baselines,
        )
        if not recommendations:
            recommendations = self._build_fallback_recommendations(baselines, calculated_rank, payload)

        direction_cards = self._build_direction_cards(payload, track, score, calculated_rank, control_lines)
        direction_advice = [card["content"] for card in direction_cards]
        advisor_takeaways = self._build_advisor_takeaways(payload, track, score, calculated_rank, recommendations)
        school_choice_logic = self._build_school_choice_logic(payload, track, calculated_rank, recommendations)
        major_observations = self._build_major_observations(payload, track, recommendations)
        strategy = self._build_strategy(payload, track, score, calculated_rank, control_lines)
        risk_notes = self._build_risk_notes(payload, track, score, calculated_rank, control_lines, recommendations)
        execution_checklist = self._build_execution_checklist(payload, recommendations)
        summary = self._build_summary(track, score, calculated_rank, control_lines, recommendations)

        return {
            "year": YEAR,
            "track": track,
            "calculated_rank": calculated_rank,
            "summary": summary,
            "direction_advice": direction_advice,
            "direction_cards": direction_cards,
            "advisor_takeaways": advisor_takeaways,
            "school_choice_logic": school_choice_logic,
            "major_observations": major_observations,
            "strategy": strategy,
            "risk_notes": risk_notes,
            "execution_checklist": execution_checklist,
            "control_lines": [
                {"line_type": line.line_type, "score": line.score}
                for line in control_lines
            ],
            "recommendations": recommendations,
            "raw_output": None,
        }

    def _normalize_province(self, value: str) -> str:
        normalized = re.sub(r"\s+", "", value or "")
        if normalized in {"吉林", "吉林省"}:
            return PROVINCE
        return value.strip()

    def _parse_positive_int(self, value: str | None, field_name: str) -> int:
        matched = re.findall(r"\d+", value or "")
        if not matched:
            raise ValueError(f"{field_name}格式不正确")
        return int(matched[0])

    def _infer_track(self, subject_combination: str) -> str:
        normalized = (subject_combination or "").replace(" ", "")
        if "史" in normalized:
            return "history"
        if "物" in normalized:
            return "physics"
        raise ValueError("暂时只支持吉林省新高考物理类或历史类组合")

    def _resolve_rank(self, track: str, score: int, raw_rank: str | None) -> int:
        if raw_rank and raw_rank.strip():
            return self._parse_positive_int(raw_rank, "位次")

        rank = self.db.scalar(
            select(GaokaoScoreRank.rank).where(
                GaokaoScoreRank.year == YEAR,
                GaokaoScoreRank.province == PROVINCE,
                GaokaoScoreRank.track == track,
                GaokaoScoreRank.score == score,
            )
        )
        if rank is None:
            raise ValueError("未找到对应分数的吉林省位次，请手动填写位次")
        return int(rank)

    def _get_control_lines(self, track: str) -> list[GaokaoControlLine]:
        return list(
            self.db.scalars(
                select(GaokaoControlLine).where(
                    GaokaoControlLine.year == YEAR,
                    GaokaoControlLine.province == PROVINCE,
                    GaokaoControlLine.track == track,
                )
            )
        )

    def _get_baselines(self, track: str) -> list[GaokaoAdmissionBaseline]:
        return list(
            self.db.scalars(
                select(GaokaoAdmissionBaseline).where(
                    GaokaoAdmissionBaseline.data_year == YEAR,
                    GaokaoAdmissionBaseline.province == PROVINCE,
                    GaokaoAdmissionBaseline.track == track,
                )
            )
        )

    def _build_recommendations(
        self,
        payload: GaokaoPlanRequest,
        track: str,
        score: int,
        rank: int,
        baselines: list[GaokaoAdmissionBaseline],
    ) -> list[dict[str, Any]]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        ranked_rows: list[dict[str, Any]] = []

        for baseline in baselines:
            if baseline.min_rank is None:
                continue

            gap = rank - baseline.min_rank
            bucket = self._classify_bucket(gap)
            match_score, match_reasons, decision_tags = self._score_direction_match(payload, track, baseline)
            fit_score = self._fit_score(bucket, gap, match_score)
            row = {
                "school": baseline.school,
                "major": baseline.major,
                "city": baseline.city,
                "school_level": baseline.school_level,
                "bucket": bucket,
                "fit_score": fit_score,
                "risk_level": self._risk_level(bucket, gap),
                "reason": self._build_reason(rank, baseline, bucket, match_reasons),
                "major_comment": self._build_major_comment(payload, track, baseline, gap),
                "decision_tags": decision_tags,
                "data_year": baseline.data_year,
                "min_score": baseline.min_score,
                "min_rank": baseline.min_rank,
                "source_name": baseline.source_name,
                "_gap": gap,
            }
            grouped[bucket].append(row)
            ranked_rows.append(row)

        for bucket in grouped:
            grouped[bucket] = sorted(
                grouped[bucket],
                key=lambda item: (-item["fit_score"], abs(item["_gap"]), item["min_rank"] or math.inf),
            )

        selected: list[dict[str, Any]] = []
        used_keys: set[tuple[str, str, str]] = set()
        for bucket in ("chong", "wen", "bao"):
            count = DEFAULT_BUCKET_COUNTS[bucket]
            for item in grouped.get(bucket, [])[:count]:
                key = (item["school"], item["major"], item["bucket"])
                if key in used_keys:
                    continue
                used_keys.add(key)
                selected.append(item)

        if len(selected) < 10:
            for item in sorted(
                ranked_rows,
                key=lambda row: (-row["fit_score"], abs(row["_gap"]), row["min_rank"] or math.inf),
            ):
                key = (item["school"], item["major"], item["bucket"])
                if key in used_keys:
                    continue
                used_keys.add(key)
                selected.append(item)
                if len(selected) >= 12:
                    break

        for item in selected:
            item.pop("_gap", None)
        return selected

    def _build_fallback_recommendations(
        self,
        baselines: list[GaokaoAdmissionBaseline],
        rank: int,
        payload: GaokaoPlanRequest,
    ) -> list[dict[str, Any]]:
        sorted_rows = sorted(
            [item for item in baselines if item.min_rank is not None],
            key=lambda item: abs((item.min_rank or rank) - rank),
        )[:8]
        results = []
        for item in sorted_rows:
            _, match_reasons, decision_tags = self._score_direction_match(payload, item.track, item)
            gap = rank - (item.min_rank or rank)
            bucket = self._classify_bucket(gap)
            results.append(
                {
                    "school": item.school,
                    "major": item.major,
                    "city": item.city,
                    "school_level": item.school_level,
                    "bucket": bucket,
                    "fit_score": self._fit_score(bucket, gap, 0),
                    "risk_level": self._risk_level(bucket, gap),
                    "reason": self._build_reason(rank, item, bucket, match_reasons),
                    "major_comment": self._build_major_comment(payload, item.track, item, gap),
                    "decision_tags": decision_tags,
                    "data_year": item.data_year,
                    "min_score": item.min_score,
                    "min_rank": item.min_rank,
                    "source_name": item.source_name,
                }
            )
        return results

    def _classify_bucket(self, gap: int) -> str:
        if gap <= -6500:
            return "bao"
        if gap <= -1500:
            return "wen"
        return "chong"

    def _score_direction_match(
        self,
        payload: GaokaoPlanRequest,
        track: str,
        baseline: GaokaoAdmissionBaseline,
    ) -> tuple[int, list[str], list[str]]:
        score = 0
        reasons: list[str] = []
        tags: list[str] = []
        haystack = " ".join(
            [
                baseline.school,
                baseline.major,
                baseline.city,
                baseline.school_level or "",
                baseline.major_tags or "",
                baseline.notes or "",
            ]
        ).lower()

        major_pref = self._tokenize(payload.preferred_majors)
        city_pref = self._tokenize(payload.preferred_cities)
        career_pref = self._tokenize(payload.career_preferences)
        budget_pref = (payload.family_budget or "").strip()

        major_hits = [token for token in major_pref if token.lower() in haystack]
        if major_hits:
            score += 20
            reasons.append(f"命中意向专业关键词：{'、'.join(major_hits[:3])}")
            tags.append("专业贴合")

        city_hits = [token for token in city_pref if token.lower() in baseline.city.lower()]
        if city_hits:
            score += 12
            reasons.append(f"符合城市偏好：{'、'.join(city_hits[:2])}")
            tags.append("城市贴合")

        career_map = {
            "稳定": ["师范", "医学", "会计", "法学", "教育", "电气"],
            "编制": ["师范", "教育", "医学", "会计"],
            "就业": ["计算机", "电气", "自动化", "会计", "护理", "电子"],
            "体制": ["师范", "法学", "会计", "医学"],
            "金融": ["金融", "会计", "财经"],
            "工科": ["工科", "计算机", "电子", "机械", "电气", "自动化"],
            "医生": ["医学", "临床", "口腔", "护理"],
        }
        for token in career_pref:
            for keyword, labels in career_map.items():
                if keyword in token and any(label in haystack for label in labels):
                    score += 10
                    reasons.append(f"和职业倾向“{token}”一致")
                    tags.append("职业导向")
                    break

        if track == "physics" and any(word in haystack for word in ["计算机", "电气", "电子", "自动化", "机械", "医学"]):
            score += 6
            tags.append("物理类优势")
        if track == "history" and any(word in haystack for word in ["法学", "会计", "师范", "汉语", "新闻"]):
            score += 6
            tags.append("历史类优势")

        if budget_pref and any(word in budget_pref for word in ["公办", "低", "一般", "有限"]):
            if baseline.school_level and ("中外合作" in baseline.school_level or "民办" in baseline.school_level):
                score -= 16
                reasons.append("家庭预算偏谨慎，不建议优先中外合作或民办")
            else:
                tags.append("预算友好")

        if baseline.school_level and "双一流" in baseline.school_level:
            tags.append("层级亮点")

        tags = list(dict.fromkeys(tags))
        return score, reasons, tags[:4]

    def _tokenize(self, raw_text: str | None) -> list[str]:
        if not raw_text:
            return []
        return [token for token in re.split(r"[、,，/\\\s]+", raw_text) if token]

    def _fit_score(self, bucket: str, gap: int, match_score: int) -> int:
        base = {"chong": 73, "wen": 84, "bao": 80}[bucket]
        closeness = max(0, 20 - min(abs(gap) // 350, 20))
        return max(52, min(99, base + closeness + match_score))

    def _risk_level(self, bucket: str, gap: int) -> str:
        if bucket == "bao":
            return "low"
        if bucket == "wen":
            return "medium"
        if gap > 2000:
            return "high"
        return "medium"

    def _build_reason(
        self,
        rank: int,
        baseline: GaokaoAdmissionBaseline,
        bucket: str,
        match_reasons: list[str],
    ) -> str:
        pieces = [
            f"{baseline.data_year}年吉林{TRACK_LABELS[baseline.track]}最低录取分为{baseline.min_score}分",
        ]
        if baseline.min_rank:
            pieces.append(f"最低位次约{baseline.min_rank}名，你当前位次约{rank}名")
        pieces.append(f"按当前公开数据属于“{BUCKET_LABELS[bucket]}”档")
        if match_reasons:
            pieces.append("；".join(match_reasons[:2]))
        if baseline.school_level:
            pieces.append(f"院校层级：{baseline.school_level}")
        return "，".join(pieces) + "。"

    def _build_major_comment(
        self,
        payload: GaokaoPlanRequest,
        track: str,
        baseline: GaokaoAdmissionBaseline,
        gap: int,
    ) -> str:
        major = baseline.major
        city = baseline.city
        comments: list[str] = []

        if any(word in major for word in ["计算机", "软件", "电子", "电气", "自动化"]):
            comments.append("这类专业就业口径普遍更宽，普通家庭更适合优先看专业实力和城市机会。")
        elif any(word in major for word in ["法学", "会计", "师范", "汉语言", "新闻"]):
            comments.append("这类专业更看重个人路径设计，读研、考编、考公和实习资源会直接影响后续上限。")
        elif any(word in major for word in ["金融", "财经"]):
            comments.append("金融财经不只看专业名，城市平台、学校层级和实习渠道往往比课表更重要。")
        elif any(word in major for word in ["医学", "护理", "临床", "口腔"]):
            comments.append("医学线培养周期更长，更适合目标明确、能接受长期投入的同学。")
        else:
            comments.append("这个专业不能只看名字，最好继续核对课程设置、读研比例和毕业去向。")

        if payload.preferred_cities:
            comments.append(f"{city}与您的城市偏好有一定重合时，落地资源会比单纯看学校名头更重要。")
        else:
            comments.append(f"{city}的城市资源和实习承接，需要和学校层级一起看，别只看一张分数线。")

        if gap <= -4000:
            comments.append("从位次上看更偏保底，可以当成兜底专业，不建议把全部名额都押在这类学校。")
        elif gap > 1500:
            comments.append("从位次上看更偏冲刺，如果特别想去，要接受专业调剂或结果波动。")
        else:
            comments.append("从位次上看属于可认真研究的一档，重点比较专业实力、城市和学费。")

        return "".join(comments[:3])

    def _build_direction_cards(
        self,
        payload: GaokaoPlanRequest,
        track: str,
        score: int,
        rank: int,
        control_lines: list[GaokaoControlLine],
    ) -> list[dict[str, str]]:
        line_map = {item.line_type: item.score for item in control_lines}
        cards = [
            {
                "title": "当前定位",
                "content": (
                    f"你在吉林{TRACK_LABELS[track]}中约位于第{rank}名，当前分数{score}分，"
                    f"比本科线高{score - line_map.get('undergraduate', 0)}分。"
                ),
            }
        ]

        if track == "physics":
            cards.append(
                {
                    "title": "方向优先级",
                    "content": (
                        "物理类不要先沉迷学校名头，先看专业出口。普通家庭更适合优先研究计算机、电气、自动化、电子信息、"
                        "机械、临床医学这类就业链路更清楚的方向。"
                    ),
                }
            )
        else:
            cards.append(
                {
                    "title": "方向优先级",
                    "content": (
                        "历史类更要防止‘名字好听但出口模糊’。优先看师范、法学、会计、汉语言、新闻传播这些后续路径更清晰的方向，"
                        "再决定学校层级。"
                    ),
                }
            )

        if payload.preferred_cities:
            cards.append(
                {
                    "title": "城市判断",
                    "content": f"你偏好“{payload.preferred_cities}”，这意味着城市资源、实习机会和未来就业半径也应该纳入一票否决项。",
                }
            )
        else:
            cards.append(
                {
                    "title": "城市判断",
                    "content": "如果暂时没有城市偏好，建议优先把长春、沈阳、大连、天津、北京、杭州这类资源更密集的城市放在前面研究。",
                }
            )

        if payload.family_budget:
            cards.append(
                {
                    "title": "预算约束",
                    "content": f"家庭预算偏好为“{payload.family_budget}”，所以推荐会主动压低高学费、中外合作和民办项目的优先级。",
                }
            )
        return cards

    def _build_advisor_takeaways(
        self,
        payload: GaokaoPlanRequest,
        track: str,
        score: int,
        rank: int,
        recommendations: list[dict[str, Any]],
    ) -> list[str]:
        top_school = recommendations[0]["school"] if recommendations else "当前推荐院校"
        takeaways = [
            f"先说结论：你这档位更适合“先定方向，再做冲稳保”，而不是为了学校名头把专业完全让出去。",
            f"你现在约第{rank}名，已经具备认真挑专业的空间，别把志愿填报做成单纯的分数换学校游戏。",
            f"目前推荐里，像“{top_school}”这类院校可以重点研究，但一定要把专业、城市、学费、保研或考公路径一起看。",
        ]
        if payload.preferred_majors:
            takeaways.append(f"你已经给出了意向专业“{payload.preferred_majors}”，这很好，后面所有筛选都要围绕这个核心，不要轻易被校名带跑。")
        if track == "history":
            takeaways.append("历史类最怕的是专业名字体面、就业出口模糊，所以每个选择都要问一句：毕业以后到底往哪里走。")
        else:
            takeaways.append("物理类最大的优势是专业出口更宽，真正要做的是把这种优势换成将来更稳定的城市和岗位。")
        return takeaways[:5]

    def _build_school_choice_logic(
        self,
        payload: GaokaoPlanRequest,
        track: str,
        rank: int,
        recommendations: list[dict[str, Any]],
    ) -> list[str]:
        logic = [
            "第一原则不是盲冲名校，而是先判断这个分数段有没有必要为了学校层级牺牲专业方向。",
            "第二原则是城市资源和行业机会不能忽略，同层次学校里，城市更强的一方往往会在实习和就业上更占便宜。",
            "第三原则是普通家庭更要考虑性价比，学费、读研成本、考公考编路径都是真问题，不是小问题。",
        ]
        if recommendations:
            logic.append(
                f"你当前推荐池里已经同时给了冲、稳、保三档，正确用法不是平均分配，而是围绕1到2条主方向去排阵型。"
            )
        if payload.preferred_cities:
            logic.append(f"你写了意向城市“{payload.preferred_cities}”，所以学校选择时要把城市作为专业后的第二筛选条件。")
        return logic[:5]

    def _build_major_observations(
        self,
        payload: GaokaoPlanRequest,
        track: str,
        recommendations: list[dict[str, Any]],
    ) -> list[str]:
        observations: list[str] = []
        preferred_majors = self._tokenize(payload.preferred_majors)

        if preferred_majors:
            observations.append(
                f"你当前最应该做的是把“{'、'.join(preferred_majors[:3])}”拆成具体专业方向，而不是停留在大类名称。"
            )

        if track == "physics":
            observations.extend(
                [
                    "工科和信息类看上去都很像，但课程难度、就业行业、读研价值差异很大，别把“计算机、电子、电气、自动化”当成一个东西。",
                    "如果未来倾向稳定就业，优先研究电气、自动化、医学、师范等路径更明确的专业；如果更想冲上限，再看计算机和电子信息。",
                ]
            )
        else:
            observations.extend(
                [
                    "历史类专业尤其要看毕业后去向，是否适合考编、考公、读研，比专业名字更重要。",
                    "法学、会计、师范、汉语言这几条线，各自路径完全不同，建议后续按“就业/考编/升学”三个方向分开研究。",
                ]
            )

        if any("中外合作" in (item.get("school_level") or "") for item in recommendations):
            observations.append("推荐里如果出现中外合作项目，一定要把总学费和家庭承受能力单独核算，不要只看录取分低。")

        return observations[:5]

    def _build_strategy(
        self,
        payload: GaokaoPlanRequest,
        track: str,
        score: int,
        rank: int,
        control_lines: list[GaokaoControlLine],
    ) -> list[str]:
        line_map = {item.line_type: item.score for item in control_lines}
        tips = [
            f"先用吉林{TRACK_LABELS[track]}一分一段把自己定位到约第{rank}名，再围绕这个位次做院校筛选，不要只盯分数。",
            f"你当前较特控线{'高' if score >= line_map.get('special', 0) else '低'}{abs(score - line_map.get('special', 0))}分，说明你有一定选择空间，但还没到可以随便任性的程度。",
            "志愿结构建议做成“2个冲方向、4个稳方向、4个保方向”的思路，同一方向尽量多留几个可替换方案。",
        ]
        if payload.preferred_majors:
            tips.append(f"意向专业“{payload.preferred_majors}”要优先看课程、去向和所在城市，不要只被学校名头带节奏。")
        return tips[:5]

    def _build_risk_notes(
        self,
        payload: GaokaoPlanRequest,
        track: str,
        score: int,
        rank: int,
        control_lines: list[GaokaoControlLine],
        recommendations: list[dict[str, Any]],
    ) -> list[str]:
        notes = [
            "这版结果已经能做方向判断和冲稳保初筛，但它仍然是公开数据版，不等同于完整志愿填报系统。",
            "公开录取最低分只代表去年的门槛，不代表今年一定能录；真正填报时还要看招生计划、专业组、服从调剂和院校冷热变化。",
            "如果你更看重将来稳定就业，就别把所有机会都押在冲档学校上，至少留出两档真正能兜底的专业。",
        ]
        if payload.family_budget and any(word in payload.family_budget for word in ["公办", "低", "有限"]):
            notes.append("家庭预算偏谨慎时，要特别注意民办和中外合作项目的总成本，不能只看入学那一年。")
        if any((item.get("bucket") == "chong" and item.get("risk_level") == "high") for item in recommendations):
            notes.append("本次冲档池里有部分学校更偏抬上限角色，如果非常执着，就要提前接受录取波动和专业调剂。")
        return notes[:5]

    def _build_execution_checklist(
        self,
        payload: GaokaoPlanRequest,
        recommendations: list[dict[str, Any]],
    ) -> list[str]:
        checklist = [
            "把本页推荐院校按“最想去 / 可以接受 / 只做保底”重新手动分组，不要直接照抄。",
            "逐个核对专业的学费、培养地点、是否中外合作、是否需要读研、近年就业去向。",
            "对最想去的3到5个专业，额外查一遍课程设置和毕业去向，确认自己不是只喜欢名字。",
        ]
        if payload.preferred_cities:
            checklist.append(f"重点复核意向城市“{payload.preferred_cities}”里的院校，看未来实习和落户是否匹配你的期待。")
        if recommendations:
            checklist.append("正式填报前，再把冲、稳、保三档按顺序拉开梯度，不要让同一档位全部挤在一起。")
        return checklist[:5]

    def _build_summary(
        self,
        track: str,
        score: int,
        rank: int,
        control_lines: list[GaokaoControlLine],
        recommendations: list[dict[str, Any]],
    ) -> str:
        line_map = {item.line_type: item.score for item in control_lines}
        top_bucket = BUCKET_LABELS.get(recommendations[0]["bucket"], "稳") if recommendations else "稳"
        return (
            f"按吉林省{YEAR}年公开数据，你当前属于{TRACK_LABELS[track]}约第{rank}名，"
            f"分数为{score}分，较本科线高{score - line_map.get('undergraduate', 0)}分。"
            f"这不是一个适合盲冲名校的档位，更适合采用“先顾方向、再做冲稳保”的填报策略："
            f"先把专业出口、城市资源、家庭预算想明白，再去决定学校层级，当前推荐结果以“{top_bucket}”档起步。"
        )
