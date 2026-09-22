# -*- coding: utf-8 -*-
"""9 环节核查流水线编排：驱动案件状态机。"""
from datetime import datetime

from sqlalchemy.orm import Session

from .. import models
from .llm import llm_service
from .search import search_multilingual
from .reverse_image import trace_image

# 9 环节定义（环节名 → 状态值 → 阶段序号）
STAGES = [
    ("线索接收", "received", 1),
    ("价值初筛", "screening", 2),
    ("主张拆解", "decomposing", 3),
    ("多语种检索", "searching", 4),
    ("出处追踪", "tracing", 5),
    ("交叉验证", "verifying", 6),
    ("信源评价", "evaluating", 7),
    ("报告生成", "reporting", 8),
    ("人工审核", "reviewing", 9),
]
DONE_STATUS = "done"
STAGE_NAME = {s: n for n, s, _ in STAGES}

# 可信度层级（数字越大越可信），供交叉验证与信源评价共用
REL_LEVEL = {"高": 5, "较高": 4, "中": 3, "较低": 2, "低": 1}
REL_LABEL = {5: "高", 4: "较高", 3: "中", 2: "较低", 1: "低"}
# 信源评级（A/B/C）→ 可信度层级（A=高、B=中、C=较低）
GRADE_TO_REL = {"A": 5, "B": 3, "C": 2}


# ---------- 环节2：价值初筛 ----------
SCREENING_KEYWORDS = ["中国", "China", "Chinese", "Beijing", "冲突", "抗议", "clash", "protest", "军演",
                      "演习", "威胁", "疫情", "政治", "government", "attack", "警方", "香港", "台湾", "新疆",
                      "西藏", "Hong Kong", "Taiwan", "Xinjiang", "Tibet", "military", "surveillance",
                      "plane", "aircraft", "navy", "warship", "drone", "sanction", "human rights", "Uyghur"]


def run_screening(case: models.Case, clue: models.Clue) -> dict:
    # 图片线索：多模态理解——画面描述 + 图中文字 + 真实性线索。
    # 触发不依赖 raw_text 是否为空（前端可能已填 OCR 文字或占位文本）；
    # 仅当原文为空时用生成的转写文本补全，让主张拆解/检索等下游环节可正常跑。
    image_analysis = None
    if clue.content_type == "image":
        img_url = (clue.image_url or "").strip() or (clue.media_path or "").strip()
        if img_url:
            image_analysis = llm_service.analyze_image(img_url)
            transcript = (image_analysis.get("transcript") or "").strip()
            if transcript and not (clue.raw_text or "").strip():
                clue.raw_text = transcript
                print(f"[run_screening] 图片线索已生成转写文本（{len(transcript)}字）", flush=True)

    text = (clue.raw_text or "") + " " + (clue.title or "")

    # LLM 判断优先（能识别未直接出现关键词但实质涉华的信息）
    llm_result = llm_service.screen_clue(clue.title or "", clue.raw_text or "", clue.translated_text or "")
    if llm_result.get("passed") is not None:
        passed = bool(llm_result.get("passed"))
        score = int(llm_result.get("score", 30))
        reason = llm_result.get("reason", "")
        focus = llm_result.get("focus", "")
        # 兜底：LLM 判暂缓但命中强关键词时，提示人工复核（不直接推翻 LLM）
        hits = [kw for kw in SCREENING_KEYWORDS if kw.lower() in text.lower()]
        result = {
            "passed": passed,
            "score": score,
            "hit_keywords": hits[:8],
            "reason": reason,
            "focus": focus,
            "method": "llm",
            "checked_at": datetime.utcnow().isoformat(),
        }
        if image_analysis:
            result["image_analysis"] = image_analysis
        if not passed and hits:
            result["reason"] = f"{reason}（命中关键词：{hits[:5]}，建议人工复核）"
            result["method"] = "llm+keyword"
        case.screening_result = result
        case.stage = 2
        case.status = "screening"
        return result

    # LLM 不可用时的关键词兜底
    hits = [kw for kw in SCREENING_KEYWORDS if kw.lower() in text.lower()]
    score = min(100, 30 + len(hits) * 15)
    passed = len(hits) >= 1
    result = {
        "passed": passed,
        "score": score,
        "hit_keywords": hits[:8],
        "reason": (
            f"命中核查关键词 {len(hits)} 个（{hits[:5]}），涉及涉华议题，建议进入核查。"
            if passed else "未命中核查关键词，可暂缓处理。"
        ),
        "focus": "",
        "method": "keyword",
        "checked_at": datetime.utcnow().isoformat(),
    }
    if image_analysis:
        result["image_analysis"] = image_analysis
    case.screening_result = result
    case.stage = 2
    case.status = "screening"
    return result


# ---------- 环节3：主张拆解 ----------
def run_decompose(case: models.Case, clue: models.Clue, db: Session) -> dict:
    raw = clue.raw_text or ""
    translated = clue.translated_text or ""

    # 未提供中文翻译时，自动调用 LLM 翻译
    if not translated and raw.strip():
        auto_translated = llm_service.translate_to_chinese(raw)
        if auto_translated:
            clue.translated_text = auto_translated
            translated = auto_translated

    result = llm_service.decompose_claims(raw, translated)

    # 关键词语言校验兜底（双向）：
    #   zh 必须含中文字符（不含中文 → 不是中文关键词）
    #   en 必须不含中文字符（含汉字 → 不是英文关键词，即使带 SDD/AI 等英文缩写）
    keywords = result.get("keywords", {}) or {}
    zh_kw = (keywords.get("zh") or "").strip()
    en_kw = (keywords.get("en") or "").strip()
    import re as _re
    has_cn = bool(_re.search(r"[\u4e00-\u9fff]", zh_kw))
    is_en_pure = bool(en_kw) and not bool(_re.search(r"[\u4e00-\u9fff]", en_kw))

    # zh 不是中文 → 把 en（若为纯英文）或 raw 翻译成中文补全
    if not has_cn:
        src = en_kw if is_en_pure else raw
        zh_fixed = llm_service.translate_to_chinese(src[:150])
        if zh_fixed:
            keywords["zh"] = zh_fixed
    # en 含中文 → 把 zh（若为中文）或 raw 翻译成英文补全
    if not is_en_pure:
        src = zh_kw if has_cn else raw
        en_fixed = llm_service.translate_to_english(src[:150])
        if en_fixed:
            keywords["en"] = en_fixed

    # 视角检索词退化补全（LLM 未输出/为空时，基于 zh/en 拼默认检索词）
    zh_head = (keywords.get("zh") or "").split("、")[0].strip()
    en_head = (keywords.get("en") or "").split(",")[0].strip()
    if not (keywords.get("zh_official") or "").strip():
        keywords["zh_official"] = (f"{zh_head} 中方回应 外交部 发言人 声明" if zh_head else "")
    if not (keywords.get("zh_media") or "").strip():
        keywords["zh_media"] = (f"{zh_head} 新华社 人民日报 环球时报 报道" if zh_head else "")
    if not (keywords.get("en_west") or "").strip():
        keywords["en_west"] = (keywords.get("en") or "")
    # 语言校验：zh_official/zh_media 必须含中文，en_west 必须纯英文；不合法则回退
    if not _re.search(r"[\u4e00-\u9fff]", keywords.get("zh_official") or ""):
        keywords["zh_official"] = (f"{zh_head} 中方回应 外交部 发言人 声明" if zh_head else "")
    if not _re.search(r"[\u4e00-\u9fff]", keywords.get("zh_media") or ""):
        keywords["zh_media"] = (f"{zh_head} 新华社 人民日报 环球时报 报道" if zh_head else "")
    if _re.search(r"[\u4e00-\u9fff]", keywords.get("en_west") or ""):
        keywords["en_west"] = (keywords.get("en") or "")
    result["keywords"] = keywords

    # 清掉旧主张，写入新主张
    for old in case.claims:
        db.delete(old)
    db.flush()
    for c in result.get("claims", []):
        ctype = c.get("type", "fact")
        # 核查主线：allegation（指控/定性表述）与 fact（事实主张）都参与检索
        searchable = 1 if ctype in ("fact", "allegation") else 0
        db.add(models.Claim(
            case_id=case.id,
            text=c.get("text", ""),
            claim_type=ctype,
            elements=c.get("elements", {}),
            searchable=searchable,
        ))
    case.keywords = result.get("keywords", {"zh": "", "en": ""})
    case.stage = 3
    case.status = "decomposing"
    db.commit()
    return result


# ---------- 环节4：多语种检索 ----------
async def run_search(case: models.Case) -> dict:
    keywords = case.keywords or {"zh": "", "en": ""}
    results = await search_multilingual(keywords)
    case.search_results = results
    case.stage = 4
    case.status = "searching"
    return {"keywords": keywords, "results": results}


# ---------- 环节5：出处追踪 ----------
async def run_trace(case: models.Case, clue: models.Clue) -> dict:
    try:
        result = await trace_image(clue.media_path or "", clue.source_link or "", clue.image_url or "")
        case.trace_results = result.get("results", [])
        case.stage = 5
        case.status = "tracing"
        return result
    except Exception as e:
        # 未配置或失败：保留失败原因供前端可见（不静默返回 0 条，便于排查额度/配置问题）
        warning = str(e)
        case.trace_results = [{
            "matched_title": "反向识图未执行",
            "matched_site": "系统提示",
            "url": "",
            "note": f"{warning}（请检查 SERPAPI_API_KEY 额度/配置后重试）",
            "warning": True,
        }]
        case.stage = 5
        case.status = "tracing"
        return {"results": [], "mode": "error", "warning": warning}


# ---------- 环节6：交叉验证 ----------
def run_verify(case: models.Case, db: Session) -> dict:
    """把检索结果 + 出处追踪结果整合为证据矩阵，并用 LLM 判定与主张的关系。"""
    # 清旧证据
    for old in case.evidence:
        db.delete(old)
    db.flush()

    claims = case.claims
    claim_texts = [c.text for c in claims if c.searchable]
    evidence_items = []

    def _cut(v: str, n: int) -> str:
        """截断超长字段，防止 PostgreSQL VARCHAR 长度限制导致整环节回滚（如超长 Facebook/社媒链接）。"""
        return (v or "")[:n]

    for i, s in enumerate(case.search_results or []):
        origin = s.get("origin", "")
        origin_label = {"cn_official": "·中方官方", "cn_media": "·中方媒体",
                        "foreign_state_media": "·外媒官方喉舌"}.get(origin, "")
        ev = models.Evidence(
            case_id=case.id,
            name=_cut(s.get("title", f"证据{i+1}"), 200),
            source_org=_cut(s.get("source", ""), 100),
            source_type=_cut(f"{s.get('type', '搜索结果')}{origin_label}", 30),
            publish_date=_cut(s.get("date", ""), 40),
            url=_cut(s.get("url", ""), 500),
            relation="待确认",
            reliability="中",
            note=s.get("snippet", ""),
            is_independent=1 if "转载" not in s.get("snippet", "") else 0,
        )
        db.add(ev)
        evidence_items.append(ev)

    for i, t in enumerate(case.trace_results or []):
        ev = models.Evidence(
            case_id=case.id,
            name=_cut(t.get("matched_title", f"溯源结果{i+1}"), 200),
            source_org=_cut(t.get("matched_site", ""), 100),
            source_type="出处追踪",
            publish_date=_cut(t.get("published_date", ""), 40),
            url=_cut(t.get("url", ""), 500),
            relation="待确认",
            reliability="中",
            note=t.get("note", ""),
            is_independent=1,
        )
        db.add(ev)
        evidence_items.append(ev)

    # 先提交拿到 evidence_id
    db.commit()
    for ev in evidence_items:
        db.refresh(ev)

    # LLM 批量判定每条证据与主张的关系（支持/反驳/背景/待确认）
    classify_judged = 0
    if evidence_items:
        claims_payload = [{"id": c.id, "text": c.text, "type": c.claim_type} for c in claims]
        evidence_payload = [
            {"id": ev.id, "name": ev.name, "source_org": ev.source_org,
             "source_type": ev.source_type, "snippet": (ev.note or "")[:200]}
            for ev in evidence_items
        ]
        try:
            classify = llm_service.classify_evidence_batch(claims_payload, evidence_payload)
        except Exception as _e:
            classify = {"results": []}
            print(f"[run_verify] LLM classify error: {_e}", flush=True)
        # 统计实际被判定的证据数（判定未完成时在 warning 中透明提示，避免"全待确认"被误读为正常结果）
        judged_ids = set()
        for _item in classify.get("results", []):
            _eid = _item.get("evidence_id")
            if _eid is not None:
                try:
                    judged_ids.add(int(_eid))
                except (TypeError, ValueError):
                    pass
        classify_judged = len(judged_ids)
        # 汇总：按证据分组，分别记录 对指控性主张(allegation)的关系 和 对事实主张(fact)的关系
        claim_text_by_id = {c.id: c.text for c in claims}
        ev_map: dict[int, dict] = {ev.id: {"allegation": [], "fact": [], "other": []}
                                   for ev in evidence_items}
        for item in classify.get("results", []):
            eid = item.get("evidence_id")
            if eid is None:
                continue
            try:
                eid = int(eid)
            except (TypeError, ValueError):
                continue
            if eid not in ev_map:
                continue
            cid = item.get("claim_id")
            ctype = "other"
            for c in claims:
                if c.id == cid:
                    ctype = c.claim_type
                    break
            item["claim_text"] = claim_text_by_id.get(cid, "")
            bucket = "allegation" if ctype == "allegation" else ("fact" if ctype == "fact" else "other")
            ev_map[eid][bucket].append(item)
        for ev in evidence_items:
            buckets = ev_map[ev.id]
            # 核查主线：优先取对指控性主张的关系；无指控关系时取对事实主张的关系
            primary = buckets["allegation"] or buckets["fact"] or buckets["other"]
            if primary:
                # 若同一主张类型有多条判定，取更明确的（反驳 > 支持 > 背景 > 待确认）
                order = {"反驳": 0, "支持": 1, "背景": 2, "待确认": 3}
                primary.sort(key=lambda x: order.get(x.get("relation", "待确认"), 4))
                info = primary[0]
                ev.relation = info.get("relation", "待确认")
                rel = info.get("reliability", "中")
                # 规则级硬性降级（中国立场）：外媒官方喉舌涉华证据可信度从严
                if ev.source_type and "外媒官方喉舌" in ev.source_type:
                    # 外媒喉舌：可信度上限"中"（不得给较高/高）
                    cap = 3  # 中
                    if buckets["allegation"] and any(
                            r.get("relation") == "支持" for r in buckets["allegation"]):
                        cap = 2  # 喉舌支持反华指控 → 上限"较低"
                    if REL_LEVEL.get(rel, 3) > cap:
                        rel = REL_LABEL[cap]
                elif buckets["allegation"] and any(
                        r.get("relation") == "支持" for r in buckets["allegation"]):
                    # 任何信源支持反华指控性表述，可信度最多"中"（立场偏颇扣分）
                    if REL_LEVEL.get(rel, 3) > 3:
                        rel = "中"
                ev.reliability = rel
                parts = []
                if buckets["allegation"]:
                    rels = "、".join(f"指控「{r.get('claim_text', '')[:30] or '见主张'}」:{r.get('relation')}"
                                     for r in buckets["allegation"][:3])
                    parts.append(f"指控层面——{rels}")
                if buckets["fact"]:
                    rels = "、".join(f"事实「{r.get('claim_text', '')[:30] or '见主张'}」:{r.get('relation')}"
                                     for r in buckets["fact"][:3])
                    parts.append(f"事实层面——{rels}")
                if parts:
                    ev.note = f"{ev.note} | { '；'.join(parts) }" if ev.note else "；".join(parts)
            else:
                ev.relation = "待确认"
                ev.reliability = "中"
    db.commit()

    # 计算独立信源数与关系统计
    independent = sum(1 for e in evidence_items if e.is_independent)
    rel_counts = {}
    for e in evidence_items:
        rel_counts[e.relation] = rel_counts.get(e.relation, 0) + 1
    # 组装提示：判定未完成 + 独立来源数量提示
    _warn_parts = []
    if classify_judged < len(evidence_items):
        _warn_parts.append(
            f"证据关系判定部分未完成（{len(evidence_items) - classify_judged}/{len(evidence_items)} 条未判定，"
            "LLM 超时或失败），相关证据关系暂为'待确认'，建议人工补判后再定结论。"
        )
    _warn_parts.append(
        "目前仅发现一个独立来源，暂不建议形成确定结论。"
        if independent < 2 else "已发现多个独立来源，可进入信源评价。"
    )
    result = {
        "claim_count": len(claim_texts),
        "evidence_count": len(evidence_items),
        "independent_count": independent,
        "relation_stats": rel_counts,
        "warning": "；".join(_warn_parts),
    }
    case.verification_results = result
    case.stage = 6
    case.status = "verifying"
    db.commit()
    return result


# ---------- 环节7：信源评价 ----------
def run_evaluate(case: models.Case) -> dict:
    evals = []
    for e in case.evidence:
        source = {"名称": e.name, "机构": e.source_org, "类型": e.source_type,
                  "日期": e.publish_date, "URL": e.url}
        result = llm_service.evaluate_source(source)
        # 规则级硬性降级（中国立场）：外媒官方喉舌评级上限 B，表述/立场任一差则上限 C
        grade = result.get("grade", "B")
        dims = result.get("dimensions", {})
        is_state_media = bool(e.source_type and "外媒官方喉舌" in e.source_type)
        # 火山方舟 Web Search：国内通道多源整合综述，非官方媒体但为中方立场信源，固定评级 B
        is_volcano = bool(e.source_org and "火山方舟" in e.source_org)
        if is_state_media:
            if grade == "A":
                grade = "B"
            dims["立场与倾向性"] = dims.get("立场与倾向性", "中") in ("高", "较高") and "较低" or dims.get("立场与倾向性", "中")
        if dims.get("涉华表述准确性") in ("低", "较低") or dims.get("立场与倾向性") in ("低", "较低"):
            if grade == "A":
                grade = "B"
        if is_volcano:
            # 火山方舟 Web Search：国内检索通道的多源整合综述，虽非官媒但为中方立场，评级固定 B
            grade = "B"
            dims["立场与倾向性"] = dims.get("立场与倾向性", "中")
        result["grade"] = grade
        result["dimensions"] = dims
        # 反向更新证据矩阵：信源评级 → 可信度层级（与交叉验证判定取更严一档，只降不升）
        grade_level = GRADE_TO_REL.get(grade, 3)
        cur_level = REL_LEVEL.get(e.reliability, 3)
        if grade_level < cur_level:
            e.reliability = REL_LABEL[grade_level]
        if is_volcano:
            # 火山综述：B 级对应可信度"中"，与交叉验证判定归一（高降低升）
            e.reliability = "中"
        if grade:
            e.note = f"{e.note} | 信源评级：{grade}" if e.note else f"信源评级：{grade}"
        evals.append({
            "evidence_id": e.id,
            "name": e.name,
            "source_org": e.source_org,
            **result,
        })
    case.source_evals = evals
    case.stage = 7
    case.status = "evaluating"
    return evals


# ---------- 环节8：报告生成 ----------
def run_report(case: models.Case, db: Session) -> dict:
    claims = [{"text": c.text, "type": c.claim_type, "elements": c.elements}
              for c in case.claims]
    evidence = [{"name": e.name, "source_org": e.source_org, "source_type": e.source_type,
                 "publish_date": e.publish_date, "url": e.url, "relation": e.relation,
                 "reliability": e.reliability, "note": e.note}
                for e in case.evidence]
    evals = case.source_evals or []

    result = llm_service.generate_report(
        {"case_no": case.case_no, "title": case.title},
        claims, evidence, evals,
    )

    # 持久化报告（结构化字段）
    report = db.query(models.Report).filter_by(case_id=case.id).first()
    if not report:
        report = models.Report(case_id=case.id)
        db.add(report)
    report.preliminary_conclusion = result.get("preliminary_conclusion", "")
    report.conclusion = result.get("conclusion", "尚待核实")
    report.confidence = result.get("confidence", "中")
    report.summary = result.get("summary", "")
    # 报告证据表与证据矩阵对齐：relation/reliability 以数据库判定（含信源评价反写）为准，
    # 避免 LLM 生成的 evidence_table 与证据矩阵环节展示不一致；数据库有而表内缺的条目自动补全。
    db_ev = {e.name: e for e in case.evidence}
    aligned, seen = [], set()
    for row in (result.get("evidence_table") or []):
        name = row.get("name", "")
        m = db_ev.get(name)
        if m:
            row["relation"] = m.relation
            row["reliability"] = m.reliability
        aligned.append(row)
        if name:
            seen.add(name)
    for e in case.evidence:
        if e.name not in seen:
            aligned.append({
                "name": e.name, "source": e.source_org, "date": e.publish_date,
                "relation": e.relation, "reliability": e.reliability,
                "url": e.url, "grade": "",
            })
    report.evidence_table = aligned
    report.source_links = result.get("source_links", [])
    report.gaps = result.get("gaps", [])
    report.pending_items = result.get("pending_items", [])

    case.final_conclusion = report.conclusion
    case.stage = 8
    case.status = "reporting"
    db.commit()
    return result


# ---------- 环节8（图片专用）：图片真实性核查报告 ----------
def run_image_report(case: models.Case, db: Session) -> dict:
    """纯图片线索：基于 多模态画面分析（screening_result.image_analysis）+ 反向识图溯源 综合判定图片真实性。

    结论类别：真实 / 疑似AI生成 / 疑似PS拼接 / 疑似旧图新用 / 无法判断。
    """
    clue = db.query(models.Clue).filter_by(id=case.clue_id).first()
    ia = (case.screening_result or {}).get("image_analysis") or {}
    trace = case.trace_results or []
    result = llm_service.generate_image_report(
        {"case_no": case.case_no, "title": case.title,
         "clue_title": (clue.title if clue else "")},
        ia, trace,
    )
    # 持久化报告（复用 Report 表字段；结论存图片真实性判定）
    report = db.query(models.Report).filter_by(case_id=case.id).first()
    if not report:
        report = models.Report(case_id=case.id)
        db.add(report)
    report.preliminary_conclusion = result.get("preliminary_conclusion", "")
    report.conclusion = result.get("conclusion", "无法判断")
    report.confidence = result.get("confidence", "中")
    report.summary = result.get("summary", "")
    report.evidence_table = [
        {"name": t.get("matched_title", ""), "source": t.get("matched_site", ""),
         "date": "", "relation": "溯源", "reliability": "", "url": t.get("url", ""),
         "note": t.get("note", "")}
        for t in trace if not t.get("warning")
    ]
    report.source_links = [
        {"title": t.get("matched_title", ""), "url": t.get("url", ""),
         "source": t.get("matched_site", "")}
        for t in trace if t.get("url") and not t.get("warning")
    ]
    report.gaps = result.get("gaps", [])
    report.pending_items = result.get("pending_items", [])

    case.final_conclusion = report.conclusion
    case.stage = 8
    case.status = "reporting"
    db.commit()
    return result


# ---------- 环节9：人工审核 ----------
def run_review(case: models.Case, db: Session, reviewer: str, action: str, comment: str,
               check_items: list) -> dict:
    log = models.ReviewLog(
        case_id=case.id,
        reviewer=reviewer,
        action=action,
        comment=comment,
        check_items=check_items,
    )
    db.add(log)
    if action == "approved":
        case.status = DONE_STATUS
        case.stage = 9
    elif action == "returned":
        # 退回：回到信源评价阶段重做
        case.status = "evaluating"
        case.stage = 7
    # revised: 保持 reporting，待再次审核
    db.commit()
    return {"log_id": log.id, "case_status": case.status, "stage": case.stage}


def case_stage_name(case: models.Case) -> str:
    if case.status == DONE_STATUS:
        return "已结案"
    return STAGE_NAME.get(case.status, case.status)


# ---------- 自动流水线：环节2→8 串行执行，停在人工审核 ----------
async def run_auto_pipeline(case_id: int) -> dict:
    """自动核查流水线：价值初筛→主张拆解→多语种检索→出处追踪→交叉验证→信源评价→报告生成。

    在独立 Session 中执行（用于 BackgroundTasks），每环节完成后提交，
    任一步骤失败时记录错误并停在当前环节（不静默继续）。
    """
    from ..database import SessionLocal
    from .search import search_multilingual
    from .reverse_image import trace_image

    db = SessionLocal()
    log = []
    try:
        case = db.query(models.Case).filter_by(id=case_id).first()
        if not case:
            return {"ok": False, "msg": "案件不存在"}
        clue = db.query(models.Clue).filter_by(id=case.clue_id).first()
        # 纯图片线索走"图片真实性核查"专用流程：不做主张拆解/文本检索/证据矩阵，
        # 直接多模态画面分析（环节2 内完成）+ 反向识图出处追踪 + 图片核查报告
        is_image = bool(clue and clue.content_type == "image")

        # 环节2：价值初筛（纯图片线索：含多模态画面分析与真实性判定）
        r = run_screening(case, clue)
        case.running_log = log + [{"stage": 2, "name": "价值初筛", "ok": True, "detail": f"得分{r.get('score', 0)}，{'通过' if r.get('passed') else '暂缓'}"}]
        db.commit(); db.refresh(case)
        log.append({"stage": 2, "name": "价值初筛", "ok": True,
                    "detail": f"得分{r.get('score', 0)}，{'通过' if r.get('passed') else '暂缓'}"})

        if is_image:
            # 环节3/4：纯图片线索跳过主张拆解与多语种检索（无文本主张可拆、无需关键词搜索）
            skip = {"stage": 3, "name": "主张拆解", "ok": True, "detail": "纯图片线索：跳过文本主张拆解，聚焦图片真实性核查"}
            case.running_log = log + [skip, {"stage": 4, "name": "多语种检索", "ok": True, "detail": "纯图片线索：跳过文本检索"}]
            db.commit(); db.refresh(case)
            log.extend([skip, {"stage": 4, "name": "多语种检索", "ok": True, "detail": "纯图片线索：跳过文本检索"}])

            # 环节5：出处追踪（反向识图，纯图片核心环节）
            try:
                r = await run_trace(case, clue)
                case.running_log = log + [{"stage": 5, "name": "出处追踪", "ok": True, "detail": f"溯源 {len(r.get('results', []))} 条"}]
                db.commit(); db.refresh(case)
                log.append({"stage": 5, "name": "出处追踪", "ok": True,
                            "detail": f"溯源 {len(r.get('results', []))} 条"})
            except Exception as e:
                db.rollback(); db.refresh(case)
                case.running_log = log + [{"stage": 5, "name": "出处追踪", "ok": False, "detail": f"跳过：{str(e)[:80]}"}]
                db.commit()
                log.append({"stage": 5, "name": "出处追踪", "ok": False, "detail": f"跳过：{str(e)[:80]}"})

            # 环节6/7：跳过交叉验证与信源评价（无文本证据池）
            skip6 = {"stage": 6, "name": "交叉验证", "ok": True, "detail": "纯图片线索：跳过文本证据矩阵"}
            skip7 = {"stage": 7, "name": "信源评价", "ok": True, "detail": "纯图片线索：跳过文本信源评价"}
            case.running_log = log + [skip6, skip7]
            db.commit(); db.refresh(case)
            log.extend([skip6, skip7])

            # 环节8：图片真实性核查报告（画面分析 + 溯源佐证 综合判定）
            r = run_image_report(case, db)
            case.running_log = log + [{"stage": 8, "name": "报告生成", "ok": True, "detail": f"图片判定：{r.get('conclusion', '')}"}]
            db.commit(); db.refresh(case)
            log.append({"stage": 8, "name": "报告生成", "ok": True,
                        "detail": f"图片判定：{r.get('conclusion', '')}"})
            return {"ok": True, "case_id": case_id, "stage": case.stage,
                    "status": case.status, "log": log, "mode": "image"}

        # 环节3：主张拆解
        r = run_decompose(case, clue, db)
        case.running_log = log + [{"stage": 3, "name": "主张拆解", "ok": True, "detail": f"拆解 {len(r.get('claims', []))} 项主张"}]
        db.commit(); db.refresh(case)
        log.append({"stage": 3, "name": "主张拆解", "ok": True,
                    "detail": f"拆解 {len(r.get('claims', []))} 项主张"})

        # 环节4：多语种检索
        r = await run_search(case)
        case.running_log = log + [{"stage": 4, "name": "多语种检索", "ok": True, "detail": f"检索到 {len(r.get('results', []))} 条结果"}]
        db.commit(); db.refresh(case)
        log.append({"stage": 4, "name": "多语种检索", "ok": True,
                    "detail": f"检索到 {len(r.get('results', []))} 条结果"})

        # 环节5：出处追踪（图片/链接溯源，失败不中断整条流水线）
        try:
            r = await run_trace(case, clue)
            case.running_log = log + [{"stage": 5, "name": "出处追踪", "ok": True, "detail": f"溯源 {len(r.get('results', []))} 条"}]
            db.commit(); db.refresh(case)
            log.append({"stage": 5, "name": "出处追踪", "ok": True,
                        "detail": f"溯源 {len(r.get('results', []))} 条"})
        except Exception as e:
            db.rollback()
            db.refresh(case)
            case.running_log = log + [{"stage": 5, "name": "出处追踪", "ok": False, "detail": f"跳过：{str(e)[:80]}"}]
            db.commit()
            log.append({"stage": 5, "name": "出处追踪", "ok": False,
                        "detail": f"跳过：{str(e)[:80]}"})

        # 环节6：交叉验证
        r = run_verify(case, db)
        case.running_log = log + [{"stage": 6, "name": "交叉验证", "ok": True, "detail": f"证据 {r.get('evidence_count', 0)} 条，独立来源 {r.get('independent_count', 0)} 个"}]
        db.commit(); db.refresh(case)
        log.append({"stage": 6, "name": "交叉验证", "ok": True,
                    "detail": f"证据 {r.get('evidence_count', 0)} 条，独立来源 {r.get('independent_count', 0)} 个"})

        # 环节7：信源评价
        r = run_evaluate(case)
        case.running_log = log + [{"stage": 7, "name": "信源评价", "ok": True, "detail": f"评价 {len(r)} 个信源"}]
        db.commit(); db.refresh(case)
        log.append({"stage": 7, "name": "信源评价", "ok": True,
                    "detail": f"评价 {len(r)} 个信源"})

        # 环节8：报告生成
        r = run_report(case, db)
        case.running_log = log + [{"stage": 8, "name": "报告生成", "ok": True, "detail": f"结论：{r.get('conclusion', '')}"}]
        db.commit(); db.refresh(case)
        log.append({"stage": 8, "name": "报告生成", "ok": True,
                    "detail": f"结论：{r.get('conclusion', '')}"})

        return {"ok": True, "case_id": case_id, "stage": case.stage,
                "status": case.status, "log": log}
    except Exception as e:
        db.rollback()
        return {"ok": False, "case_id": case_id, "msg": str(e)[:200], "log": log}
    finally:
        db.close()
