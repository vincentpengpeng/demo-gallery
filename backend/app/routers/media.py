# -*- coding: utf-8 -*-
"""多模态 OCR 与自动翻译路由。"""
from fastapi import APIRouter, UploadFile, File, Form

from ..services.llm import llm_service

router = APIRouter(prefix="/api", tags=["media"])


@router.post("/ocr")
async def ocr_image(media: UploadFile = File(...)):
    """图片文字识别：接收上传图片 → 多模态识别 → 返回文字。"""
    data = await media.read()
    ext = (media.filename or "").rsplit(".", 1)[-1].lower() if media.filename else "png"
    fmt = "png" if ext == "png" else "jpg"
    text = llm_service.ocr_image(data, fmt)
    if not text:
        return {"ok": False, "text": "", "msg": "OCR 识别失败，请检查图片清晰度或稍后重试"}
    return {"ok": True, "text": text}


@router.post("/translate")
async def translate(text: str = Form("")):
    """外文 → 中文 自动翻译。"""
    result = llm_service.translate_to_chinese(text)
    return {"ok": bool(result), "translated": result}
