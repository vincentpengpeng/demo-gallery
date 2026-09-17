# -*- coding: utf-8 -*-
"""API 路由：线索接收、核查任务、主张、证据、报告、审核。"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from datetime import datetime

from ..database import get_db
from .. import models, schemas
from ..services import pipeline

router = APIRouter(prefix="/api", tags=["clues"])


@router.post("/clues", response_model=schemas.ClueOut)
async def create_clue(
    title: str = Form(""),
    content_type: str = Form("text"),
    raw_text: str = Form(""),
    translated_text: str = Form(""),
    source_platform: str = Form(""),
    source_account: str = Form(""),
    source_link: str = Form(""),
    published_at: str = Form(""),
    image_url: str = Form(""),
    submitted_by: str = Form(""),
    media: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    """环节1：线索接收。创建线索并自动创建核查任务，进入环节2。"""
    media_path = ""
    if media and media.filename:
        import os
        from ..config import BASE_DIR
        upload_dir = BASE_DIR / "uploads"
        upload_dir.mkdir(exist_ok=True)
        ext = os.path.splitext(media.filename)[1] or ".bin"
        media_path = str(upload_dir / f"{datetime.now().strftime('%Y%m%d%H%M%S')}{ext}")
        with open(media_path, "wb") as f:
            f.write(await media.read())

    # 线索编号
    clue_no = f"CLUE-{datetime.now().strftime('%Y%m%d')}-{db.query(models.Clue).count() + 1:03d}"
    clue = models.Clue(
        clue_no=clue_no, title=title, content_type=content_type,
        raw_text=raw_text, translated_text=translated_text,
        source_platform=source_platform, source_account=source_account,
        source_link=source_link, published_at=published_at,
        media_path=media_path, image_url=image_url, submitted_by=submitted_by,
        status="received",
    )
    db.add(clue)
    db.flush()

    case_no = f"ZT-{datetime.now().strftime('%Y')}-{db.query(models.Case).count() + 1:04d}"
    case = models.Case(
        case_no=case_no, clue_id=clue.id,
        title=title or raw_text[:50] or f"线索{clue_no}",
        status="received", stage=1, assignee=submitted_by,
    )
    db.add(case)
    db.commit()
    db.refresh(clue)
    db.refresh(case)
    return schemas.clue_to_out(clue, case)


@router.get("/clues", response_model=list[schemas.ClueListItem])
def list_clues(db: Session = Depends(get_db)):
    clues = db.query(models.Clue).order_by(models.Clue.id.desc()).limit(50).all()
    out = []
    for c in clues:
        case = db.query(models.Case).filter_by(clue_id=c.id).first()
        out.append(schemas.clue_to_list_item(c, case))
    return out
