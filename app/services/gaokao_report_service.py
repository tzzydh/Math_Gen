from __future__ import annotations

import os
import tempfile
from typing import Any
from xml.sax.saxutils import escape

from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.db.models.gaokao_plan import GaokaoPlan


TRACK_LABELS = {
    "physics": "物理类",
    "history": "历史类",
}

LINE_LABELS = {
    "special": "特控线",
    "undergraduate": "本科线",
    "specialty": "专科线",
}

BUCKET_LABELS = {
    "chong": "冲档",
    "wen": "稳档",
    "bao": "保档",
}

BUCKET_COLORS = {
    "chong": colors.HexColor("#ef4444"),
    "wen": colors.HexColor("#f59e0b"),
    "bao": colors.HexColor("#16a34a"),
}


def ensure_cjk_font_registered() -> None:
    try:
        pdfmetrics.getFont("STSong-Light")
    except KeyError:
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))


class GaokaoReportService:
    def build_pdf_bytes(self, plan: GaokaoPlan) -> bytes:
        ensure_cjk_font_registered()
        self.styles = self._build_styles()

        fd, temp_path = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)

        doc = SimpleDocTemplate(
            temp_path,
            pagesize=A4,
            topMargin=14 * mm,
            bottomMargin=14 * mm,
            leftMargin=14 * mm,
            rightMargin=14 * mm,
        )

        doc.build(self._build_story(plan))
        try:
            with open(temp_path, "rb") as handle:
                return handle.read()
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def _build_styles(self) -> dict[str, ParagraphStyle]:
        styles = getSampleStyleSheet()
        return {
            "title": ParagraphStyle(
                "title",
                parent=styles["Title"],
                fontName="STSong-Light",
                fontSize=22,
                leading=28,
                textColor=colors.white,
                alignment=TA_LEFT,
            ),
            "subtitle": ParagraphStyle(
                "subtitle",
                parent=styles["BodyText"],
                fontName="STSong-Light",
                fontSize=10.5,
                leading=15,
                textColor=colors.HexColor("#dcfce7"),
            ),
            "section": ParagraphStyle(
                "section",
                parent=styles["Heading2"],
                fontName="STSong-Light",
                fontSize=14,
                leading=20,
                textColor=colors.HexColor("#14532d"),
                spaceAfter=8,
            ),
            "body": ParagraphStyle(
                "body",
                parent=styles["BodyText"],
                fontName="STSong-Light",
                fontSize=10.5,
                leading=17,
                textColor=colors.HexColor("#334155"),
            ),
            "small": ParagraphStyle(
                "small",
                parent=styles["BodyText"],
                fontName="STSong-Light",
                fontSize=9.2,
                leading=13,
                textColor=colors.HexColor("#475569"),
            ),
            "card_title": ParagraphStyle(
                "card_title",
                parent=styles["BodyText"],
                fontName="STSong-Light",
                fontSize=10.5,
                leading=14,
                textColor=colors.HexColor("#166534"),
            ),
            "stat_label": ParagraphStyle(
                "stat_label",
                parent=styles["BodyText"],
                fontName="STSong-Light",
                fontSize=9.2,
                leading=13,
                textColor=colors.HexColor("#15803d"),
            ),
            "stat_value": ParagraphStyle(
                "stat_value",
                parent=styles["BodyText"],
                fontName="STSong-Light",
                fontSize=18,
                leading=22,
                textColor=colors.HexColor("#14532d"),
            ),
        }

    def _build_story(self, plan: GaokaoPlan) -> list[Any]:
        details = plan.details_json or {}
        target = plan.target_json or {}
        control_lines = [item for item in details.get("control_lines", []) if isinstance(item, dict)]
        recommendations = [item for item in details.get("recommendations", []) if isinstance(item, dict)]
        extended_pool = [item for item in details.get("extended_pool", []) if isinstance(item, dict)]
        major_profile = details.get("major_profile") if isinstance(details.get("major_profile"), dict) else None
        major_breakdown = [item for item in details.get("major_breakdown", []) if isinstance(item, dict)]
        direction_cards = [item for item in details.get("direction_cards", []) if isinstance(item, dict)]

        story: list[Any] = []
        story.extend(self._build_hero(plan, details))
        story.append(Spacer(1, 10))
        story.extend(self._build_stat_cards(plan, details, control_lines))
        story.append(Spacer(1, 10))
        story.extend(self._section("顾问结论", [self._paragraph(plan.summary)]))
        story.extend(self._section("基础画像", [self._basic_profile_table(target)]))
        story.extend(self._section("分数与位次定位", [self._score_chart(plan, details, control_lines)]))
        story.extend(self._section("顾问判断", [self._bullet_paragraph(details.get("advisor_takeaways", []))]))
        if details.get("deep_analysis"):
            story.extend(self._section("深度分析", [self._bullet_paragraph(details.get("deep_analysis", []))]))
        if direction_cards:
            story.extend(self._section("方向建议", [self._cards_from_items(direction_cards)]))
        if details.get("school_choice_logic"):
            story.extend(self._section("择校逻辑", [self._bullet_paragraph(details.get("school_choice_logic", []))]))
        if details.get("major_observations"):
            story.extend(self._section("专业提醒", [self._bullet_paragraph(details.get("major_observations", []))]))
        if major_profile:
            story.extend(self._section("专业详细解析", self._major_profile_flowables(major_profile)))
        if major_breakdown:
            story.extend(self._section("专业深度建议", [self._cards_from_items(major_breakdown)]))
        if details.get("signature_advice"):
            story.extend(self._section("差异化判断", [self._bullet_paragraph(details.get("signature_advice", []))]))
        if details.get("strategy"):
            story.extend(self._section("填报策略", [self._bullet_paragraph(details.get("strategy", []))]))
        if details.get("risk_notes"):
            story.extend(self._section("风险提醒", [self._bullet_paragraph(details.get("risk_notes", []))]))
        if details.get("execution_checklist"):
            story.extend(self._section("执行清单", [self._bullet_paragraph(details.get("execution_checklist", []))]))
        story.extend(self._section("主推荐院校池", [self._recommendation_table(recommendations)]))
        if extended_pool:
            story.extend(self._section("方向扩展池", [self._extended_pool_table(extended_pool)]))
        return story

    def _build_hero(self, plan: GaokaoPlan, details: dict[str, Any]) -> list[Any]:
        provider = details.get("advisor_provider") or "系统默认"
        model = details.get("advisor_model") or "未启用"
        provider_line = f"顾问引擎：{provider} / {model}"
        track = TRACK_LABELS.get(str(details.get("track", "physics")), str(details.get("track", "physics")))
        subtitle = self._join_lines(
            [
                f"{plan.province} · {track} · {plan.score}分",
                f"估算位次 {details.get('calculated_rank', plan.rank or '-')}",
                provider_line,
            ]
        )

        hero = Table(
            [[
                Paragraph("AI 高考志愿顾问报告", self.styles["title"]),
                Paragraph(self._paragraphize(subtitle), self.styles["subtitle"]),
            ]],
            colWidths=[182 * mm],
        )
        hero.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#14532d")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 18),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 18),
                    ("TOPPADDING", (0, 0), (-1, -1), 18),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 18),
                ]
            )
        )
        return [hero]

    def _build_stat_cards(self, plan: GaokaoPlan, details: dict[str, Any], control_lines: list[dict[str, Any]]) -> list[Any]:
        cards = [
            ("高考分数", f"{plan.score}分"),
            ("估算位次", f"{details.get('calculated_rank', '-') }名"),
        ]
        for item in control_lines[:2]:
            cards.append((LINE_LABELS.get(str(item.get("line_type")), str(item.get("line_type"))), f"{item.get('score')}分"))

        rows = []
        row: list[Any] = []
        for label, value in cards:
            row.append(self._stat_card(label, value))
            if len(row) == 2:
                rows.append(row)
                row = []
        if row:
            row.append("")
            rows.append(row)
        table = Table(rows, colWidths=[88 * mm, 88 * mm], hAlign="LEFT")
        table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
        return [table]

    def _stat_card(self, label: str, value: str) -> Table:
        card = Table(
            [[Paragraph(escape(label), self.styles["stat_label"])], [Paragraph(escape(value), self.styles["stat_value"])]],
            colWidths=[84 * mm],
        )
        card.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f0fdf4")),
                    ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#dcfce7")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 14),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 14),
                    ("TOPPADDING", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ]
            )
        )
        return card

    def _basic_profile_table(self, target: dict[str, Any]) -> Table:
        rows = [
            ["意向专业", target.get("preferred_majors") or "未填写", "意向城市", target.get("preferred_cities") or "未填写"],
            ["职业倾向", target.get("career_preferences") or "未填写", "家庭预算", target.get("family_budget") or "未填写"],
            ["补充说明", target.get("notes") or "未填写", "", ""],
        ]
        table = Table(rows, colWidths=[28 * mm, 63 * mm, 28 * mm, 63 * mm])
        table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#334155")),
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f0fdf4")),
                    ("BACKGROUND", (2, 0), (2, -2), colors.HexColor("#f0fdf4")),
                    ("SPAN", (1, 2), (3, 2)),
                    ("GRID", (0, 0), (-1, -1), 0.6, colors.HexColor("#dcfce7")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]
            )
        )
        return table

    def _score_chart(self, plan: GaokaoPlan, details: dict[str, Any], control_lines: list[dict[str, Any]]) -> Drawing:
        width = 180 * mm
        height = 34 * mm
        drawing = Drawing(width, height)
        drawing.add(Rect(0, 0, width, height, fillColor=colors.HexColor("#f8fff9"), strokeColor=colors.HexColor("#dcfce7")))

        score = self._safe_int(plan.score)
        line_scores = [self._safe_int(item.get("score")) for item in control_lines if item.get("score") is not None]
        max_value = max([score, *line_scores, 600]) if score else max([*line_scores, 600])

        y = 22 * mm
        drawing.add(Rect(10, y, width - 20, 6, fillColor=colors.HexColor("#dcfce7"), strokeColor=None))

        def x_for(value: int) -> float:
            return 10 + ((width - 20) * value / max_value)

        for item in control_lines:
            line_type = str(item.get("line_type") or "")
            label = LINE_LABELS.get(line_type, line_type)
            line_score = self._safe_int(item.get("score"))
            x = x_for(line_score)
            drawing.add(Rect(x - 1, y - 4, 2, 14, fillColor=colors.HexColor("#16a34a"), strokeColor=None))
            drawing.add(String(x - 10, 8, f"{label} {line_score}", fontName="STSong-Light", fontSize=8, fillColor=colors.HexColor("#166534")))

        score_x = x_for(score)
        drawing.add(Rect(score_x - 2, y - 6, 4, 18, fillColor=colors.HexColor("#2563eb"), strokeColor=None))
        drawing.add(String(score_x - 12, y + 12, f"你的分数 {score}", fontName="STSong-Light", fontSize=8.5, fillColor=colors.HexColor("#1d4ed8")))
        return drawing

    def _major_profile_flowables(self, profile: dict[str, Any]) -> list[Any]:
        flowables: list[Any] = []
        base_rows = [
            ["专业名称", profile.get("major_name") or "未命中", "学科门类", profile.get("discipline") or "未标注"],
            ["专业类别", profile.get("major_category") or "未标注", "学制/学位", self._join_lines([profile.get("duration") or "", profile.get("degree") or ""]).replace(" · ", " / ") or "未标注"],
            ["文理比例", profile.get("science_ratio") or "未标注", "五年月薪", profile.get("salary_after_5y") or "公开样本不足"],
            ["就业率", profile.get("employment_rate") or "公开样本不足", "薪酬排名", profile.get("salary_rank") or "公开样本不足"],
        ]
        table = Table(base_rows, colWidths=[28 * mm, 63 * mm, 28 * mm, 63 * mm])
        table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f0fdf4")),
                    ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#f0fdf4")),
                    ("GRID", (0, 0), (-1, -1), 0.6, colors.HexColor("#dcfce7")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]
            )
        )
        flowables.append(table)
        flowables.append(Spacer(1, 8))

        if profile.get("overview") or profile.get("training_goal"):
            flowables.append(self._info_card("专业概览", profile.get("overview") or profile.get("training_goal") or ""))
            flowables.append(Spacer(1, 8))
        if profile.get("postgraduate_paths"):
            flowables.append(self._info_card("考研与深造", "、".join(profile.get("postgraduate_paths") or [])))
            flowables.append(Spacer(1, 8))
        if profile.get("top_jobs"):
            flowables.append(self._info_card("典型岗位", "、".join(profile.get("top_jobs") or [])))
            flowables.append(Spacer(1, 8))
        if profile.get("similar_majors"):
            flowables.append(self._info_card("相似专业", "、".join(profile.get("similar_majors") or [])))
            flowables.append(Spacer(1, 8))

        analysis = Table(
            [[
                self._bullet_card("优势分析", profile.get("strengths") or [], colors.HexColor("#16a34a")),
                self._bullet_card("风险与短板", profile.get("weaknesses") or [], colors.HexColor("#ea580c")),
            ]],
            colWidths=[88 * mm, 88 * mm],
        )
        analysis.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
        flowables.append(analysis)
        return flowables

    def _cards_from_items(self, items: list[dict[str, Any]]) -> Table:
        rows = []
        for item in items:
            title = str(item.get("title") or "").strip()
            content = str(item.get("content") or "").strip()
            rows.append([self._info_card(title, content)])
            rows.append([Spacer(1, 6)])
        if not rows:
            rows.append([Paragraph("暂无", self.styles["body"])])
        return Table(rows[:-1] if len(rows) > 1 else rows, colWidths=[182 * mm], style=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))

    def _info_card(self, title: str, content: str) -> Table:
        card = Table(
            [[Paragraph(escape(title), self.styles["card_title"])], [Paragraph(self._paragraphize(content), self.styles["body"])]],
            colWidths=[182 * mm],
        )
        card.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fff9")),
                    ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#dcfce7")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 12),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                    ("TOPPADDING", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ]
            )
        )
        return card

    def _bullet_card(self, title: str, items: list[str], accent: colors.Color) -> Table:
        rows = [[Paragraph(escape(title), self.styles["card_title"])]]
        bullet_items = items[:4] if items else ["暂无"]
        for item in bullet_items:
            rows.append([Paragraph(f"· {escape(str(item))}", self.styles["body"])])
        card = Table(rows, colWidths=[84 * mm])
        card.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                    ("BOX", (0, 0), (-1, -1), 1, accent),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        return card

    def _recommendation_table(self, recommendations: list[dict[str, Any]]) -> Table:
        rows: list[list[Any]] = [[
            Paragraph("学校 / 专业", self.styles["card_title"]),
            Paragraph("档位", self.styles["card_title"]),
            Paragraph("推荐依据", self.styles["card_title"]),
        ]]
        for item in recommendations[:12]:
            school_major = self._join_lines(
                [
                    f"{item.get('school', '')} / {item.get('major', '')}",
                    f"{item.get('city') or '-'} / {item.get('school_level') or '-'}",
                    f"最低分 {item.get('min_score') or '-'} / 最低位次 {item.get('min_rank') or '-'}",
                ]
            )
            bucket = BUCKET_LABELS.get(str(item.get("bucket")), str(item.get("bucket")))
            bucket_meta = self._join_lines(
                [
                    bucket,
                    f"计划 {item.get('plan_count') or '-'} 人",
                    f"覆盖 {item.get('year_span') or '-'}",
                ]
            )
            reason = self._join_lines(
                [
                    str(item.get("reason") or ""),
                    str(item.get("major_comment") or ""),
                ]
            )
            rows.append([
                Paragraph(self._paragraphize(school_major), self.styles["small"]),
                Paragraph(self._paragraphize(bucket_meta), self.styles["small"]),
                Paragraph(self._paragraphize(reason), self.styles["small"]),
            ])
        table = Table(rows, colWidths=[54 * mm, 32 * mm, 96 * mm], repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0fdf4")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#166534")),
                    ("FONTSIZE", (0, 0), (-1, -1), 9.2),
                    ("LEADING", (0, 0), (-1, -1), 13),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dcfce7")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]
            )
        )
        return table

    def _extended_pool_table(self, extended_pool: list[dict[str, Any]]) -> Table:
        rows: list[list[Any]] = [[
            Paragraph("学校 / 专业", self.styles["card_title"]),
            Paragraph("扩展类型", self.styles["card_title"]),
            Paragraph("补充说明", self.styles["card_title"]),
        ]]
        for item in extended_pool[:12]:
            school_major = self._join_lines(
                [
                    f"{item.get('school', '')} / {item.get('major', '')}",
                    f"{item.get('city') or '-'} / {item.get('school_level') or '-'}",
                ]
            )
            evidence = self._join_lines(
                [
                    str(item.get("fit_label") or item.get("group") or "-"),
                    str(item.get("evidence_label") or "公开信息"),
                    f"参考分 {item.get('reference_score') or '-'}",
                ]
            )
            rows.append([
                Paragraph(self._paragraphize(school_major), self.styles["small"]),
                Paragraph(self._paragraphize(evidence), self.styles["small"]),
                Paragraph(self._paragraphize(str(item.get("reason") or "")), self.styles["small"]),
            ])
        table = Table(rows, colWidths=[56 * mm, 34 * mm, 92 * mm], repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0fdfa")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#155e75")),
                    ("FONTSIZE", (0, 0), (-1, -1), 9.2),
                    ("LEADING", (0, 0), (-1, -1), 13),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1fae5")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]
            )
        )
        return table

    def _section(self, title: str, flowables: list[Any]) -> list[Any]:
        section: list[Any] = [Paragraph(escape(title), self.styles["section"])]
        section.extend(flowables)
        section.append(Spacer(1, 10))
        return section

    def _bullet_paragraph(self, items: list[Any]) -> Paragraph:
        rows = [f"· {escape(str(item))}" for item in items if str(item).strip()]
        if not rows:
            rows = ["· 暂无"]
        return Paragraph("<br/>".join(rows), self.styles["body"])

    def _paragraph(self, text: str) -> Paragraph:
        return Paragraph(self._paragraphize(text), self.styles["body"])

    def _paragraphize(self, text: str) -> str:
        return escape(text or "").replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br/>")

    def _join_lines(self, lines: list[str]) -> str:
        return " · ".join(str(line).strip() for line in lines if str(line).strip())

    def _safe_int(self, value: Any) -> int:
        try:
            return int(str(value).strip())
        except Exception:
            return 0
