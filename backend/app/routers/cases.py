# -*- coding: utf-8 -*-
"""核查任务路由：9 环节驱动。"""
import threading
import asyncio
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, schemas
from ..services import pipeline
from ..services.pipeline import DONE_STATUS

router = APIRouter(prefix="/api/cases", tags=["cases"])


@router.get("", response_model=list[schemas.CaseListItem])
def list_cases(db: Session = Depends(get_db)):
    cases = db.query(models.Case).order_by(models.Case.id.desc()).limit(100).all()
    return [schemas.case_to_list_item(c) for c in cases]


@router.get("/{case_id}", response_model=schemas.CaseDetail)
def get_case(case_id: int, db: Session = Depends(get_db)):
    case = db.query(models.Case).filter_by(id=case_id).first()
    if not case:
        raise HTTPException(404, "案件不存在")
    return schemas.case_to_detail(case, db)


@router.delete("/{case_id}")
def delete_case(case_id: int, db: Session = Depends(get_db)):
    """删除核查任务及其关联的线索、主张、证据、报告、审核记录。

    注意：运行中的自动流水线（status=running）不允许删除，避免后台线程写入已删除数据。
    """
    case = db.query(models.Case).filter_by(id=case_id).first()
    if not case:
        raise HTTPException(404, "案件不存在")
    if case.status == "running":
        raise HTTPException(409, "该案件正在自动核查中，请等待完成后删除")

    clue = db.query(models.Clue).filter_by(id=case.clue_id).first()

    # 报告（uselist=False，无 cascade）需手动删除
    if case.report:
        db.delete(case.report)
    # claims/evidence/reviews 由 cascade="all, delete-orphan" 自动删除
    db.delete(case)
    if clue:
        db.delete(clue)
    db.commit()
    return {"ok": True, "msg": f"案件 {case.case_no} 已删除"}


@router.get("/{case_id}/export-pdf")
def export_case_pdf(case_id: int, db: Session = Depends(get_db)):
    """导出案件详情全环节核查结果为 PDF 报告。

    内容覆盖：案件信息、线索、价值初筛、主张拆解、多语种检索关键词、出处追踪、
    证据矩阵、信源评价、核查报告、人工审核记录。
    """
    case = db.query(models.Case).filter_by(id=case_id).first()
    if not case:
        raise HTTPException(404, "案件不存在")
    detail = schemas.case_to_detail(case, db)
    from fastapi.responses import Response
    from ..services.pdf_report import build_case_pdf
    import urllib.parse
    pdf_bytes = build_case_pdf(detail.model_dump())
    filename = f"核查报告_{case.case_no or case_id}.pdf"
    # Content-Disposition 头必须 Latin-1：filename* 的值需按 RFC 5987 做百分号编码，否则中文文件名报 UnicodeEncodeError
    encoded = urllib.parse.quote(filename)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=\"report.pdf\"; filename*=UTF-8''{encoded}"},
    )


@router.post("/{case_id}/screening")
def do_screening(case_id: int, db: Session = Depends(get_db)):
    """环节2：价值初筛。"""
    case = db.query(models.Case).filter_by(id=case_id).first()
    if not case:
        raise HTTPException(404, "案件不存在")
    clue = db.query(models.Clue).filter_by(id=case.clue_id).first()
    result = pipeline.run_screening(case, clue)
    db.commit()
    db.refresh(case)
    return result


@router.post("/{case_id}/decompose")
def do_decompose(case_id: int, db: Session = Depends(get_db)):
    """环节3：主张拆解。"""
    case = db.query(models.Case).filter_by(id=case_id).first()
    if not case:
        raise HTTPException(404, "案件不存在")
    clue = db.query(models.Clue).filter_by(id=case.clue_id).first()
    return pipeline.run_decompose(case, clue, db)


@router.post("/{case_id}/search")
async def do_search(case_id: int, db: Session = Depends(get_db)):
    """环节4：多语种检索。"""
    case = db.query(models.Case).filter_by(id=case_id).first()
    if not case:
        raise HTTPException(404, "案件不存在")
    result = await pipeline.run_search(case)
    db.commit()
    db.refresh(case)
    return result


@router.post("/{case_id}/trace")
async def do_trace(case_id: int, db: Session = Depends(get_db)):
    """环节5：出处追踪。"""
    case = db.query(models.Case).filter_by(id=case_id).first()
    if not case:
        raise HTTPException(404, "案件不存在")
    clue = db.query(models.Clue).filter_by(id=case.clue_id).first()
    result = await pipeline.run_trace(case, clue)
    db.commit()
    db.refresh(case)
    return result


@router.post("/{case_id}/verify")
def do_verify(case_id: int, db: Session = Depends(get_db)):
    """环节6：交叉验证。"""
    case = db.query(models.Case).filter_by(id=case_id).first()
    if not case:
        raise HTTPException(404, "案件不存在")
    return pipeline.run_verify(case, db)


@router.post("/{case_id}/evaluate")
def do_evaluate(case_id: int, db: Session = Depends(get_db)):
    """环节7：信源评价。"""
    case = db.query(models.Case).filter_by(id=case_id).first()
    if not case:
        raise HTTPException(404, "案件不存在")
    result = pipeline.run_evaluate(case)
    db.commit()
    db.refresh(case)
    return result


@router.post("/{case_id}/report")
def do_report(case_id: int, db: Session = Depends(get_db)):
    """环节8：报告生成。"""
    case = db.query(models.Case).filter_by(id=case_id).first()
    if not case:
        raise HTTPException(404, "案件不存在")
    return pipeline.run_report(case, db)


@router.post("/{case_id}/review")
def do_review(case_id: int, payload: schemas.ReviewIn, db: Session = Depends(get_db)):
    """环节9：人工审核。"""
    case = db.query(models.Case).filter_by(id=case_id).first()
    if not case:
        raise HTTPException(404, "案件不存在")
    return pipeline.run_review(
        case, db,
        reviewer=payload.reviewer,
        action=payload.action,
        comment=payload.comment,
        check_items=payload.check_items,
    )


@router.post("/{case_id}/auto")
def auto_pipeline(case_id: int, db: Session = Depends(get_db)):
    """一键自动核查：后台串行执行环节2→8，停在人工审核。

    用独立线程跑流水线（内部含 LLM/搜索等阻塞调用），不阻塞 API 事件循环；
    前端轮询案件详情查看进度。
    """
    case = db.query(models.Case).filter_by(id=case_id).first()
    if not case:
        raise HTTPException(404, "案件不存在")
    if case.status == "running":
        raise HTTPException(409, "该案件正在自动核查中，请等待完成")
    if case.status == DONE_STATUS:
        raise HTTPException(409, "该案件已结案")
    if case.status == "reviewing":
        raise HTTPException(409, "该案件已生成报告，等待人工审核")

    case.status = "running"
    case.running_log = []
    db.commit()

    def _worker():
        from ..services.pipeline import run_auto_pipeline
        asyncio.run(run_auto_pipeline(case_id))

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    return {"ok": True, "case_id": case_id, "msg": "自动核查已启动，请稍后刷新查看进度"}


@router.post("/{case_id}/advance")
def advance(case_id: int, db: Session = Depends(get_db)):
    """一键推进到下一环节（用于演示/测试逐环节流转）。"""
    case = db.query(models.Case).filter_by(id=case_id).first()
    if not case:
        raise HTTPException(404, "案件不存在")
    if case.stage >= 9:
        return {"stage": 9, "status": case.status, "msg": "已到最后环节"}
    case.stage += 1
    db.commit()
    return {"stage": case.stage, "status": case.status, "msg": "已推进"}
