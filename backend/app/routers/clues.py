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
        from ..services.github_image import upload_image_to_github, GitHubImageHostError
        # 先存临时文件，再上传 GitHub 图床（公开可访问 URL），避免依赖本地磁盘（重启丢失）
        upload_dir = BASE_DIR / "uploads"
        upload_dir.mkdir(exist_ok=True)
        ext = os.path.splitext(media.filename)[1] or ".bin"
        tmp_path = upload_dir / f"tmp_{datetime.now().strftime('%Y%m%d%H%M%S%f')}{ext}"
        with open(tmp_path, "wb") as f:
            f.write(await media.read())
        try:
            # 上传 GitHub 图床，返回 raw URL；失败时回退本地路径并标记（前端可显示错误）
            media_path = await upload_image_to_github(str(tmp_path))
        except GitHubImageHostError as e:
            media_path = f"/uploads/{tmp_path.name}"
            print(f"[create_clue] GitHub 图床上传失败，回退本地：{e}", flush=True)
        finally:
            # 清理临时文件（图床已持有内容，本地不再保留）
            if tmp_path.exists():
                tmp_path.unlink()

    # 线索编号：取当天已用最大序号 + 1（避免删除数据后 count() 与既有编号冲突）
    today = datetime.now().strftime('%Y%m%d')
    clue_prefix = f"CLUE-{today}-"
    clue_max = db.query(models.Clue).filter(
        models.Clue.clue_no.like(f"{clue_prefix}%")
    ).order_by(models.Clue.clue_no.desc()).first()
    clue_seq = int(clue_max.clue_no.rsplit('-', 1)[-1]) + 1 if clue_max else 1
    clue_no = f"{clue_prefix}{clue_seq:03d}"
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

    # 案件编号：取当年已用最大序号 + 1（同样避免删除后冲突）
    year = datetime.now().strftime('%Y')
    case_prefix = f"ZT-{year}-"
    case_max = db.query(models.Case).filter(
        models.Case.case_no.like(f"{case_prefix}%")
    ).order_by(models.Case.case_no.desc()).first()
    case_seq = int(case_max.case_no.rsplit('-', 1)[-1]) + 1 if case_max else 1
    case_no = f"{case_prefix}{case_seq:04d}"
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
