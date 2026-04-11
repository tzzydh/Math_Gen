import os
import tempfile
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

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
    "chong": "冲",
    "wen": "稳",
    "bao": "保",
}


def ensure_cjk_font_registered() -> None:
    try:
        pdfmetrics.getFont("STSong-Light")
    except KeyError:
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))


class GaokaoReportService:
    def build_pdf_bytes(self, plan: GaokaoPlan) -> bytes:
        ensure_cjk_font_registered()
        details = plan.details_json or {}
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "ReportTitle",
            parent=styles["Title"],
            fontName="STSong-Light",
            fontSize=22,
            leading=28,
            textColor=colors.HexColor("#111827"),
            alignment=TA_LEFT,
        )
        heading_style = ParagraphStyle(
            "ReportHeading",
            parent=styles["Heading2"],
            fontName="STSong-Light",
            fontSize=16,
            leading=22,
            textColor=colors.HexColor("#14532d"),
            spaceAfter=8,
        )
        body_style = ParagraphStyle(
            "ReportBody",
            parent=styles["BodyText"],
            fontName="STSong-Light",
            fontSize=11,
            leading=18,
            textColor=colors.HexColor("#334155"),
        )
        meta_style = ParagraphStyle(
            "ReportMeta",
            parent=styles["BodyText"],
            fontName="STSong-Light",
            fontSize=10.5,
            leading=16,
            textColor=colors.HexColor("#475569"),
        )

        fd, temp_path = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)

        doc = SimpleDocTemplate(
            temp_path,
            pagesize=A4,
            topMargin=18 * mm,
            bottomMargin=18 * mm,
            leftMargin=16 * mm,
            rightMargin=16 * mm,
        )

        target = plan.target_json or {}
        control_lines = details.get("control_lines", [])
        recommendations = details.get("recommendations", [])

        story: list[Any] = [
            Paragraph("AI 高考志愿顾问报告", title_style),
            Spacer(1, 6),
            Paragraph(
                self._join_lines(
                    [
                        f"省份：{escape(plan.province)}",
                        f"科类：{escape(TRACK_LABELS.get(str(details.get('track', 'physics')), str(details.get('track', 'physics'))))}",
                        f"分数：{escape(plan.score)}",
                        f"位次：{escape(str(details.get('calculated_rank', plan.rank or '-')))}",
                        f"选科组合：{escape(plan.subject_combination)}",
                    ]
                ),
                meta_style,
            ),
            Spacer(1, 10),
            Paragraph("一、顾问结论", heading_style),
            Paragraph(self._paragraphize(plan.summary), body_style),
            Spacer(1, 10),
            Paragraph("二、基础画像", heading_style),
            Paragraph(
                self._join_lines(
                    [
                        f"意向专业：{escape(target.get('preferred_majors') or '未填写')}",
                        f"意向城市：{escape(target.get('preferred_cities') or '未填写')}",
                        f"职业倾向：{escape(target.get('career_preferences') or '未填写')}",
                        f"家庭预算：{escape(target.get('family_budget') or '未填写')}",
                        f"补充说明：{escape(target.get('notes') or '未填写')}",
                    ]
                ),
                body_style,
            ),
            Spacer(1, 10),
            Paragraph("三、张雪峰式判断", heading_style),
            Paragraph(self._bullet_lines(details.get("advisor_takeaways", [])), body_style),
            Spacer(1, 10),
            Paragraph("四、方向与择校逻辑", heading_style),
            Paragraph(self._bullet_lines(details.get("direction_advice", [])), body_style),
            Spacer(1, 4),
            Paragraph(self._bullet_lines(details.get("school_choice_logic", [])), body_style),
            Spacer(1, 10),
            Paragraph("五、专业提醒", heading_style),
            Paragraph(self._bullet_lines(details.get("major_observations", [])), body_style),
            Spacer(1, 10),
            Paragraph("六、填报策略与风险", heading_style),
            Paragraph(self._bullet_lines(details.get("strategy", [])), body_style),
            Spacer(1, 4),
            Paragraph(self._bullet_lines(details.get("risk_notes", [])), body_style),
            Spacer(1, 10),
            Paragraph("七、执行清单", heading_style),
            Paragraph(self._bullet_lines(details.get("execution_checklist", [])), body_style),
            Spacer(1, 10),
            Paragraph("八、关键分数线", heading_style),
            Paragraph(
                self._bullet_lines(
                    [
                        f"{LINE_LABELS.get(str(item.get('line_type')), str(item.get('line_type')))}：{item.get('score')}分"
                        for item in control_lines
                        if isinstance(item, dict)
                    ]
                ),
                body_style,
            ),
            Spacer(1, 10),
            Paragraph("九、推荐院校与专业", heading_style),
        ]

        for index, item in enumerate(recommendations, start=1):
            if not isinstance(item, dict):
                continue
            story.extend(
                [
                    Paragraph(
                        f"{index}. {escape(item.get('school', ''))} · {escape(item.get('major', ''))} · "
                        f"{escape(BUCKET_LABELS.get(str(item.get('bucket')), str(item.get('bucket'))))}档",
                        heading_style,
                    ),
                    Paragraph(
                        self._join_lines(
                            [
                                f"城市：{escape(item.get('city') or '-')}",
                                f"院校层级：{escape(item.get('school_level') or '-')}",
                                f"最低分：{escape(str(item.get('min_score') or '-'))}分",
                                f"最低位次：{escape(str(item.get('min_rank') or '-'))}",
                            ]
                        ),
                        meta_style,
                    ),
                    Paragraph(self._paragraphize(item.get("reason") or ""), body_style),
                    Paragraph(self._paragraphize(item.get("major_comment") or ""), body_style),
                    Spacer(1, 8),
                ]
            )

        doc.build(story)
        try:
            with open(temp_path, "rb") as handle:
                return handle.read()
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def _paragraphize(self, text: str) -> str:
        return escape(text or "").replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br/>")

    def _join_lines(self, lines: list[str]) -> str:
        return "<br/>".join(line for line in lines if line)

    def _bullet_lines(self, items: list[Any]) -> str:
        normalized = [escape(str(item)) for item in items if str(item).strip()]
        if not normalized:
            normalized = ["暂无"]
        return "<br/>".join([f"• {item}" for item in normalized])
