# -*- coding: utf-8 -*-
"""Pydantic 模型与序列化辅助。"""
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from . import models
from .services.pipeline import case_stage_name


# ---------- 请求模型 ----------
class ReviewIn(BaseModel):
    reviewer: str = ""
    action: str = "approved"            # approved / revised / returned
    comment: str = ""
    check_items: list = []


# ---------- 序列化 ----------
class ClueOut(BaseModel):
    id: int
    clue_no: str
    case_id: int
    case_no: str
    title: str
    content_type: str
    raw_text: str
    media_path: str = ""
    image_url: str = ""
    status: str

    class Config:
        from_attributes = True


class ClueListItem(BaseModel):
    id: int
    clue_no: str
    title: str
    content_type: str
    source_platform: str
    submitted_by: str
    submitted_at: Optional[str]
    case_id: Optional[int]
    case_status: str
    case_stage: int
    stage_name: str

    class Config:
        from_attributes = True


class CaseListItem(BaseModel):
    id: int
    case_no: str
    title: str
    status: str
    stage: int
    stage_name: str
    priority: str
    assignee: str
    final_conclusion: str
    created_at: Optional[str]

    class Config:
        from_attributes = True


class CaseDetail(BaseModel):
    id: int
    case_no: str
    title: str
    status: str
    stage: int
    stage_name: str
    priority: str
    assignee: str
    final_conclusion: str
    screening_result: dict
    keywords: dict
    search_results: list
    trace_results: list
    verification_results: dict
    source_evals: list
    running_log: list = []
    clue: dict
    claims: list
    evidence: list
    report: Optional[dict]
    reviews: list

    class Config:
        from_attributes = True


# ---------- 组装函数 ----------
def clue_to_out(clue: models.Clue, case: models.Case) -> ClueOut:
    return ClueOut(
        id=clue.id, clue_no=clue.clue_no, case_id=case.id, case_no=case.case_no,
        title=clue.title, content_type=clue.content_type,
        raw_text=clue.raw_text, status=clue.status,
    )


def clue_to_list_item(c: models.Clue, case: Optional[models.Case]) -> ClueListItem:
    return ClueListItem(
        id=c.id, clue_no=c.clue_no, title=c.title, content_type=c.content_type,
        source_platform=c.source_platform, submitted_by=c.submitted_by,
        submitted_at=c.submitted_at.isoformat() if c.submitted_at else None,
        case_id=case.id if case else None,
        case_status=case.status if case else "",
        case_stage=case.stage if case else 0,
        stage_name=case_stage_name(case) if case else "",
    )


def case_to_list_item(c: models.Case) -> CaseListItem:
    return CaseListItem(
        id=c.id, case_no=c.case_no, title=c.title, status=c.status,
        stage=c.stage, stage_name=case_stage_name(c),
        priority=c.priority, assignee=c.assignee,
        final_conclusion=c.final_conclusion,
        created_at=c.created_at.isoformat() if c.created_at else None,
    )


def case_to_detail(case: models.Case, db: Session) -> CaseDetail:
    clue = db.query(models.Clue).filter_by(id=case.clue_id).first()
    claims = [{"id": x.id, "text": x.text, "type": x.claim_type, "elements": x.elements}
              for x in case.claims]
    evidence = [{"id": e.id, "name": e.name, "source_org": e.source_org,
                 "source_type": e.source_type, "publish_date": e.publish_date,
                 "url": e.url, "relation": e.relation, "reliability": e.reliability,
                 "note": e.note, "is_independent": e.is_independent}
                for e in case.evidence]
    report = None
    if case.report:
        r = case.report
        report = {"id": r.id,
                  "preliminary_conclusion": r.preliminary_conclusion,
                  "summary": r.summary,
                  "conclusion": r.conclusion,
                  "confidence": r.confidence,
                  "evidence_table": r.evidence_table or [],
                  "source_links": r.source_links or [],
                  "gaps": r.gaps or [],
                  "pending_items": r.pending_items or [],
                  "generated_at": r.generated_at.isoformat() if r.generated_at else None}
    reviews = [{"id": x.id, "reviewer": x.reviewer, "action": x.action,
                "comment": x.comment, "check_items": x.check_items,
                "reviewed_at": x.reviewed_at.isoformat() if x.reviewed_at else None}
               for x in case.reviews]
    return CaseDetail(
        id=case.id, case_no=case.case_no, title=case.title, status=case.status,
        stage=case.stage, stage_name=case_stage_name(case),
        priority=case.priority, assignee=case.assignee,
        final_conclusion=case.final_conclusion,
        screening_result=case.screening_result or {},
        keywords=case.keywords or {},
        search_results=case.search_results or [],
        trace_results=case.trace_results or [],
        verification_results=case.verification_results or {},
        source_evals=case.source_evals or [],
        running_log=case.running_log or [],
        clue={
            "id": clue.id, "clue_no": clue.clue_no, "title": clue.title,
            "content_type": clue.content_type, "raw_text": clue.raw_text,
            "translated_text": clue.translated_text,
            "source_platform": clue.source_platform,
            "source_account": clue.source_account,
            "source_link": clue.source_link,
            "published_at": clue.published_at, "submitted_by": clue.submitted_by,
            "media_path": clue.media_path, "image_url": clue.image_url,
        } if clue else {},
        claims=claims, evidence=evidence, report=report, reviews=reviews,
    )
