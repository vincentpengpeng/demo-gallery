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


# ---------- 环节2：价值初筛 ----------
SCREENING_KEYWORDS = ["中国", "China", "Chinese", "Beijing", "冲突", "抗议", "clash", "protest", "军演",
                      "演习", "威胁", "疫情", "政治", "government", "attack", "警方", "香港", "台湾", "新疆",
                      "西藏", "Hong Kong", "Taiwan", "Xinjiang", "Tibet", "military", "surveillance",
                      "plane", "aircraft", "navy", "warship", "drone", "sanction", "human rights", "Uyghur"]


def run_screening(case: models.Case, clue: models.Clue) -> dict:
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
    result["keywords"] = keywords

    # 清掉旧主张，写入新主张
    for old in case.claims:
        db.delete(old)
    db.flush()
    for c in result.get("claims", []):
        db.add(models.Claim(
            case_id=case.id,
            text=c.get("text", ""),
            claim_type=c.get("type", "fact"),
            elements=c.get("elements", {}),
            searchable=1 if c.get("type") == "fact" else 0,
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
        # 未配置或失败：记录提示信息，不落演示数据
        warning = str(e)
        case.trace_results = []
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

    for i, s in enumerate(case.search_results or []):
        origin = s.get("origin", "")
        origin_label = {"cn_official": "·中方官方", "cn_media": "·中方媒体",
                        "foreign_state_media": "·外媒官方喉舌"}.get(origin, "")
        ev = models.Evidence(
            case_id=case.id,
            name=s.get("title", f"证据{i+1}"),
            source_org=s.get("source", ""),
            source_type=f"{s.get('type', '搜索结果')}{origin_label}",
            publish_date=s.get("date", ""),
            url=s.get("url", ""),
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
            name=t.get("matched_title", f"溯源结果{i+1}"),
            source_org=t.get("matched_site", ""),
            source_type="出处追踪",
            publish_date=t.get("published_date", ""),
            url=t.get("url", ""),
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
    if evidence_items:
        claims_payload = [{"text": c.text, "type": c.claim_type} for c in claims]
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
        rel_map = {}
        for item in classify.get("results", []):
            eid = item.get("evidence_id")
            if eid is not None:
                try:
                    rel_map[int(eid)] = item
                except (TypeError, ValueError):
                    pass
        for ev in evidence_items:
            info = rel_map.get(ev.id, {})
            ev.relation = info.get("relation", "待确认")
            ev.reliability = info.get("reliability", "中")
            if info.get("reason") and info.get("reason") != "LLM判定未启用，待人工确认":
                ev.note = f"{ev.note} | 判定理由：{info['reason']}" if ev.note else f"判定理由：{info['reason']}"
    db.commit()

    # 计算独立信源数与关系统计
    independent = sum(1 for e in evidence_items if e.is_independent)
    rel_counts = {}
    for e in evidence_items:
        rel_counts[e.relation] = rel_counts.get(e.relation, 0) + 1
    result = {
        "claim_count": len(claim_texts),
        "evidence_count": len(evidence_items),
        "independent_count": independent,
        "relation_stats": rel_counts,
        "warning": (
            "目前仅发现一个独立来源，暂不建议形成确定结论。"
            if independent < 2 else "已发现多个独立来源，可进入信源评价。"
        ),
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
    report.evidence_table = result.get("evidence_table", [])
    report.source_links = result.get("source_links", [])
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

        # 环节2：价值初筛
        r = run_screening(case, clue)
        case.running_log = log + [{"stage": 2, "name": "价值初筛", "ok": True, "detail": f"得分{r.get('score', 0)}，{'通过' if r.get('passed') else '暂缓'}"}]
        db.commit(); db.refresh(case)
        log.append({"stage": 2, "name": "价值初筛", "ok": True,
                    "detail": f"得分{r.get('score', 0)}，{'通过' if r.get('passed') else '暂缓'}"})

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
