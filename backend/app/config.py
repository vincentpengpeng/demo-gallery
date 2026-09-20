# -*- coding: utf-8 -*-
"""真探平台配置：从 .env 读取。"""
from pydantic_settings import BaseSettings
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # LLM - 火山引擎 Ark（主通道：Agent Plan）
    ark_api_key: str = ""
    ark_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    ark_model: str = "doubao-seed-1-6-250615"

    # 多模态 OCR - 标准版 api/v3（deepseek-v4-1-flash 支持图片输入）
    ocr_api_key: str = ""
    ocr_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    ocr_model: str = "deepseek-v4-1-flash-260910"

    # 反向搜图 - SerpAPI Google Reverse Image（支持逗号分隔多 key，额度用完自动轮换）
    serpapi_api_key: str = ""
    # 图床 - GitHub（本地图片先传 GitHub 拿公开 URL，再交给 SerpAPI 识图）
    github_token: str = ""
    github_repo: str = ""            # 形如 owner/repo，需为公开仓库
    github_branch: str = "main"
    # 反向搜图 - 备用（百度智能云图像搜索 / TinEye）
    baidu_search_app_id: str = ""
    baidu_search_api_key: str = ""
    baidu_search_secret_key: str = ""
    tineye_api_key: str = ""

    # 联网搜索 - Brave（可选，未配置时用 DuckDuckGo 免key）
    brave_api_key: str = ""

    # 数据库
    database_url: str = "sqlite:///./zhen_tan.db"

    backend_port: int = 8000

    @property
    def serpapi_keys(self) -> list[str]:
        """SerpAPI 多 key 列表（逗号分隔；剔除空值、去重）。"""
        keys = [k.strip() for k in (self.serpapi_api_key or "").split(",") if k.strip()]
        seen, out = set(), []
        for k in keys:
            if k not in seen:
                seen.add(k)
                out.append(k)
        return out

    class Config:
        env_file = BASE_DIR / ".env"
        env_file_encoding = "utf-8"


settings = Settings()

# 能力开关
LLM_ENABLED = bool(settings.ark_api_key)
SEARCH_ENABLED = bool(settings.brave_api_key)
REVERSE_IMAGE_ENABLED = bool(settings.serpapi_api_key)
