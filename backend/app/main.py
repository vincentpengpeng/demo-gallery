# -*- coding: utf-8 -*-
"""真探·海外涉华信息智能核查平台 - 后端入口。"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .database import Base, engine
from .routers import clues, cases, media

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="真探·海外涉华信息智能核查平台",
    description="面向真探工作室的海外涉华信息多模态核查工具（文本+图片 MVP）",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # 本地开发放开；部署时收敛
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(clues.router)
app.include_router(cases.router)
app.include_router(media.router)


@app.get("/api/health")
def health():
    from .config import settings
    from .services.llm import llm_service
    # PDF 导出依赖探针：确认 reportlab 是否安装及版本
    pdf_status = "missing"
    try:
        import reportlab
        pdf_status = reportlab.Version
    except Exception:
        pdf_status = "missing"
    return {
        "status": "ok",
        "llm_ark": llm_service.enabled,
        "llm_model": settings.ark_model,
        "search_google": bool(settings.serpapi_api_key),
        "reverse_image": bool(settings.serpapi_api_key),
        "image_host_github": bool(settings.github_token and settings.github_repo),
        "ocr_multimodal": llm_service.ocr_enabled,
        "ocr_model": settings.ocr_model,
        "pdf_reportlab": pdf_status,
        "note": "全部能力均为真实数据；未配置的能力会在对应环节明确报错提示，不会返回演示数据。",
    }


from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
uploads_dir = BASE_DIR / "uploads"
uploads_dir.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")
