# -*- coding: utf-8 -*-
"""GitHub 图床服务：本地图片上传到公开仓库，返回可公开访问的 URL。

用途：SerpAPI Google 识图需要可公开访问的图片地址，
本地上传的图片先推到 GitHub 仓库（公开），再拿 raw URL 调识图。
"""
import base64
import uuid
from datetime import datetime

import httpx

from ..config import settings


class GitHubImageHostError(Exception):
    pass


async def upload_image_to_github(local_path: str) -> str:
    """上传本地图片到 GitHub 公开仓库，返回 raw URL。

    配置要求（backend/.env）：
      GITHUB_TOKEN=你的 Personal Access Token（需要 repo 写权限）
      GITHUB_REPO=owner/repo（公开仓库）
    """
    if not settings.github_token or not settings.github_repo:
        raise GitHubImageHostError(
            "GitHub 图床未配置：请在 backend/.env 填入 GITHUB_TOKEN 和 GITHUB_REPO "
            "（token 在 https://github.com/settings/tokens 生成，需勾选 repo 权限）。"
        )

    # 读取图片并 base64
    with open(local_path, "rb") as f:
        content = base64.b64encode(f.read()).decode("utf-8")

    # 远程路径：zhen-tan/{yyyy}/{mm}/{uuid}.{ext}
    ext = local_path.rsplit(".", 1)[-1].lower() if "." in local_path else "jpg"
    if ext not in ("jpg", "jpeg", "png", "gif", "webp"):
        ext = "jpg"
    now = datetime.now()
    remote_path = f"zhen-tan/{now.strftime('%Y/%m')}/{uuid.uuid4().hex[:12]}.{ext}"

    url = f"https://api.github.com/repos/{settings.github_repo}/contents/{remote_path}"
    headers = {
        "Authorization": f"Bearer {settings.github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "zhen-tan-platform",
    }
    payload = {
        "message": f"[zhen-tan] upload image {now.isoformat()}",
        "content": content,
        "branch": settings.github_branch,
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.put(url, headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()
    except httpx.HTTPStatusError as e:
        detail = e.response.text[:300] if e.response else ""
        raise GitHubImageHostError(
            f"GitHub 上传失败（{e.response.status_code if e.response else '未知'}）：{detail}"
        ) from e
    except httpx.HTTPError as e:
        raise GitHubImageHostError(f"GitHub 上传网络错误：{e}") from e

    raw_url = data.get("content", {}).get("download_url", "")
    if not raw_url:
        raise GitHubImageHostError("GitHub 上传成功但未返回下载 URL，请检查仓库是否为公开仓库。")
    return raw_url
