# -*- coding: utf-8 -*-
"""案件详情全环节核查结果导出 PDF（reportlab + CID 内建中文字体 STSong-Light，无需字体文件）。

覆盖环节：案件信息 / 线索 / 价值初筛 / 主张拆解 / 多语种检索 / 出处追踪 /
证据矩阵 / 信源评价 / 核查报告 / 人工审核记录。
"""
from io import BytesIO
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
_FONT = "STSong-Light"
_BLUE = colors.HexColor("#0f4c81")
_GREY = colors.HexColor("#888888")
_LIGHT = colors.HexColor("#f2f6fa")


def _st(name, **kw):
    base = dict(fontName=_FONT, fontSize=9, leading=13, textColor=colors.black)
    base.update(kw)
    return ParagraphStyle(name, **base)


ST_TITLE = _st("title", fontSize=17, leading=24, alignment=1)
ST_SUB = _st("sub", fontSize=9, leading=13, alignment=1, textColor=_GREY)
ST_SECTION = _st("section", fontSize=12, leading=16, textColor=_BLUE, spaceBefore=12, spaceAfter=4)
ST_BODY = _st("body", fontSize=9, leading=14, spaceAfter=2)
ST_SMALL = _st("small", fontSize=8, leading=11, textColor=_GREY)
ST_CELL = ParagraphStyle("cell", parent=_st("c"), fontSize=8, leading=11)
ST_CELL_H = ParagraphStyle("cellh", parent=ST_CELL, textColor=colors.white)


def _esc(v) -> str:
    """转义 XML 特殊字符，避免 reportlab Paragraph 解析错误。"""
    return (str(v or "")).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _p(v, style=ST_CELL):
    return Paragraph(_esc(v), style)


def _sec(title):
    return [Paragraph(title, ST_SECTION)]


def _table(header, rows, col_widths, header_bg=_BLUE):
    data = [[Paragraph(h, ST_CELL_H) for h in header]]
    for r in rows:
        data.append([_p(c) if not isinstance(c, Paragraph) else c for c in r])
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), _FONT),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("BACKGROUND", (0, 0), (-1, 0), header_bg),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def _kv_table(rows):
    t = Table([[Paragraph(f"<b>{_esc(k)}</b>", ST_CELL), Paragraph(_esc(v or ""), ST_CELL)]
               for k, v in rows], colWidths=[36 * mm, 144 * mm])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), _FONT),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dddddd")),
        ("BACKGROUND", (0, 0), (0, -1), _LIGHT),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


_TYPE_LABEL = {"allegation": "指控表述 ★", "fact": "事实主张",
               "view": "观点表达", "emotion": "情绪表达"}


def build_case_pdf(detail: dict) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, topMargin=18 * mm, bottomMargin=16 * mm,
        leftMargin=15 * mm, rightMargin=15 * mm,
        title=f"核查报告 {detail.get('case_no', '')}",
        author="真探·海外涉华信息智能核查平台",
    )
    story = []
    story.append(Paragraph("真探 · 海外涉华信息智能核查平台", ST_SUB))
    story.append(Paragraph("案件核查报告（全环节核查结果）", ST_TITLE))
    story.append(Paragraph(
        f"案件编号：{_esc(detail.get('case_no', ''))}　"
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        ST_SUB))
    story.append(Spacer(1, 6))

    # ===== 案件信息 =====
    story += _sec("案件信息")
    story.append(_kv_table([
        ("案件编号", detail.get("case_no")),
        ("案件标题", detail.get("title")),
        ("当前状态", f"{detail.get('stage_name', '')}（阶段 {detail.get('stage', '')}）"),
        ("优先级", detail.get("priority")),
        ("负责人", detail.get("assignee") or "-"),
        ("最终结论", detail.get("final_conclusion") or "-"),
    ]))

    # ===== 一、线索信息 =====
    clue = detail.get("clue") or {}
    story += _sec("一、线索信息")
    story.append(_kv_table([
        ("线索编号", clue.get("clue_no")),
        ("来源平台", clue.get("source_platform") or "-"),
        ("来源账号", clue.get("source_account") or "-"),
        ("来源链接", clue.get("source_link") or "-"),
        ("发布时间", clue.get("published_at") or "-"),
        ("提交人", clue.get("submitted_by") or "-"),
        ("内容类型", clue.get("content_type") or "-"),
    ]))
    if clue.get("raw_text"):
        story.append(Paragraph(f"<b>原文：</b>{_esc(clue['raw_text'])}", ST_BODY))
    if clue.get("translated_text"):
        story.append(Paragraph(f"<b>中文翻译：</b>{_esc(clue['translated_text'])}", ST_BODY))

    # ===== 二、价值初筛 =====
    scr = detail.get("screening_result") or {}
    story += _sec("二、价值初筛")
    story.append(_kv_table([
        ("初筛得分", f"{scr.get('score', '-')} / 100"),
        ("是否通过", "通过" if scr.get("passed") else "暂缓"),
        ("命中关键词", "、".join(scr.get("hit_keywords") or []) or "-"),
        ("议题方向", scr.get("focus") or "-"),
        ("判定方式", scr.get("method") or "-"),
        ("判定理由", scr.get("reason") or "-"),
    ]))

    # ===== 二.五、图片真实性核查（纯图片线索） =====
    ia = scr.get("image_analysis") or {}
    if ia:
        badge = {"real_scene": "真实现场图", "ai_generated": "疑似AI生成",
                 "ps_edited": "疑似PS拼接", "old_image_reuse": "疑似旧图新用",
                 "unclear": "无法判断"}.get(ia.get("suspected"), "无法判断")
        story += _sec("图片真实性核查")
        story.append(_kv_table([
            ("判定", badge),
            ("判定理由", ia.get("reason") or "-"),
            ("画面内容", ia.get("scene_description") or "-"),
            ("图中文字", ia.get("text_in_image") or "-"),
        ]))
        clues = ia.get("authenticity_clues") or []
        if clues:
            story.append(Paragraph("<b>真实性疑点：</b>", ST_BODY))
            for i, cl in enumerate(clues, 1):
                story.append(Paragraph(f"{i}. {_esc(cl)}", ST_SMALL))

    # ===== 三、主张拆解 =====
    story += _sec("三、主张拆解")
    claims = detail.get("claims") or []
    if not claims:
        story.append(Paragraph("（无主张拆解记录）", ST_SMALL))
    for i, c in enumerate(claims, 1):
        label = _TYPE_LABEL.get(c.get("type"), c.get("type", ""))
        story.append(Paragraph(f"<b>{i}. [{label}]</b> {_esc(c.get('text', ''))}", ST_BODY))
        els = c.get("elements") or {}
        parts = [f"{k}:{v}" for k, v in els.items() if v]
        if parts:
            story.append(Paragraph("要素：" + " ｜ ".join(parts), ST_SMALL))
    kw = detail.get("keywords") or {}
    if kw:
        story.append(Spacer(1, 3))
        story.append(Paragraph("<b>多语种检索关键词：</b>", ST_BODY))
        for k, v in kw.items():
            if v:
                story.append(Paragraph(f"　{k}：{_esc(str(v))}", ST_SMALL))

    # ===== 四、出处追踪 =====
    story += _sec("四、出处追踪")
    trace = detail.get("trace_results") or []
    if not trace:
        story.append(Paragraph("（无溯源匹配结果）", ST_SMALL))
    else:
        story.append(_table(
            ["匹配标题", "来源站点", "链接", "备注"],
            [[t.get("matched_title", ""), t.get("matched_site", ""),
              t.get("url", ""), t.get("note", "")] for t in trace],
            [62 * mm, 30 * mm, 52 * mm, 36 * mm],
        ))

    # ===== 五、证据矩阵 =====
    story += _sec("五、证据矩阵")
    evs = detail.get("evidence") or []
    if not evs:
        story.append(Paragraph("（无证据记录）", ST_SMALL))
    else:
        story.append(_table(
            ["证据名称", "来源", "日期", "关系", "可信度", "信源类型", "摘要/备注"],
            [[e.get("name", ""), e.get("source_org", ""), e.get("publish_date", ""),
              e.get("relation", ""), e.get("reliability", ""), e.get("source_type", ""),
              (e.get("note") or "")[:160]] for e in evs],
            [40 * mm, 24 * mm, 16 * mm, 13 * mm, 13 * mm, 24 * mm, 50 * mm],
        ))

    # ===== 六、信源评价 =====
    story += _sec("六、信源评价")
    evals = detail.get("source_evals") or []
    if not evals:
        story.append(Paragraph("（无信源评价记录）", ST_SMALL))
    else:
        story.append(_table(
            ["信源", "评级", "六维评价", "理由"],
            [[e.get("name", ""), f"评级 {e.get('grade', '')}",
              " ｜ ".join(f"{k}:{v}" for k, v in (e.get("dimensions") or {}).items()),
              e.get("reason", "")] for e in evals],
            [52 * mm, 16 * mm, 66 * mm, 46 * mm],
        ))

    # ===== 七、核查报告 =====
    rep = detail.get("report")
    story += _sec("七、核查报告")
    if not rep:
        story.append(Paragraph("（报告未生成）", ST_SMALL))
    else:
        story.append(_kv_table([
            ("初步结论", rep.get("conclusion")),
            ("置信度", rep.get("confidence")),
            ("生成时间", rep.get("generated_at")),
        ]))
        if rep.get("preliminary_conclusion"):
            story.append(Paragraph(f"<b>结论说明：</b>{_esc(rep['preliminary_conclusion'])}", ST_BODY))
        if rep.get("summary"):
            story.append(Paragraph(f"<b>核查摘要：</b>{_esc(rep['summary'])}", ST_BODY))
        et = rep.get("evidence_table") or []
        if et:
            story.append(Paragraph("<b>报告证据表：</b>", ST_BODY))
            story.append(_table(
                ["证据", "来源", "日期", "关系", "可信度"],
                [[r.get("name", ""), r.get("source", "") or r.get("grade", ""),
                  r.get("date", ""), r.get("relation", ""), r.get("reliability", "")]
                 for r in et],
                [62 * mm, 40 * mm, 24 * mm, 28 * mm, 26 * mm],
            ))
        links = rep.get("source_links") or []
        if links:
            story.append(Paragraph("<b>来源链接：</b>", ST_BODY))
            for i, lk in enumerate(links, 1):
                story.append(Paragraph(f"{i}. {_esc(lk.get('title', ''))} — {_esc(lk.get('url', ''))}（{_esc(lk.get('source', ''))}）", ST_SMALL))
        for label, key in (("证据缺口", "gaps"), ("待确认事项", "pending_items")):
            vals = rep.get(key) or []
            if vals:
                story.append(Paragraph(f"<b>{label}：</b>", ST_BODY))
                for i, v in enumerate(vals, 1):
                    story.append(Paragraph(f"{i}. {_esc(v)}", ST_SMALL))

    # ===== 八、人工审核记录 =====
    story += _sec("八、人工审核记录")
    reviews = detail.get("reviews") or []
    if not reviews:
        story.append(Paragraph("（无审核记录）", ST_SMALL))
    else:
        story.append(_table(
            ["审核人", "动作", "意见", "时间"],
            [[r.get("reviewer", ""),
              {"approved": "通过", "returned": "退回", "revised": "修订"}.get(r.get("action"), r.get("action", "")),
              r.get("comment", ""), (r.get("reviewed_at") or "")[:19]] for r in reviews],
            [28 * mm, 18 * mm, 104 * mm, 30 * mm],
        ))

    story.append(Spacer(1, 8))
    story.append(Paragraph("— 本报告由真探·海外涉华信息智能核查平台自动生成，结论基于证据，供人工复核参考 —", ST_SMALL))
    doc.build(story)
    return buf.getvalue()
