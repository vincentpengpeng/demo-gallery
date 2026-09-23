# -*- coding: utf-8 -*-
"""出处追踪 / 反向搜图服务。

链路：本地图片 → GitHub 图床（公开URL）→ SerpAPI Google Reverse Image。
未配置 SerpAPI key 或 GitHub 图床时：明确报错提示配置，不返回演示数据。
"""
import httpx

from ..config import settings, REVERSE_IMAGE_ENABLED
from .github_image import upload_image_to_github, GitHubImageHostError


class ReverseImageNotConfigured(Exception):
    pass


async def trace_image(media_path: str = "", source_link: str = "", image_url: str = "") -> dict:
    """图片出处追踪。

    优先用 image_url（已可公开访问）；
    否则若 media_path 为本地文件，先经 GitHub 图床上传拿公开 URL；
    再调 SerpAPI Google 识图。
    返回 {results, mode, image_url, warning}。
    """
    if not REVERSE_IMAGE_ENABLED:
        raise ReverseImageNotConfigured(
            "反向搜图未配置：请在 backend/.env 填入 SERPAPI_API_KEY "
            "（https://serpapi.com/ 注册，免费 100 次/月），重启后端后生效。"
        )

    # 1) 确定可公开访问的图片 URL
    public_url = image_url
    upload_note = ""
    if not public_url and media_path:
        if media_path.startswith(("http://", "https://")):
            # media_path 已是公网 URL（如 GitHub 图床 raw），直接使用，不再重复上传
            public_url = media_path
        else:
            try:
                public_url = await upload_image_to_github(media_path)
                upload_note = f"（已自动上传图床：{public_url[:60]}...）"
            except GitHubImageHostError as e:
                raise ReverseImageNotConfigured(str(e)) from e
    if not public_url:
        raise ReverseImageNotConfigured(
            "缺少图片地址：请在 .env 配置 GitHub 图床（GITHUB_TOKEN/GITHUB_REPO）以自动上传本地图片，"
            "或在线索提交时填写图片公开链接。"
        )

    # 2) SerpAPI 反向识图（多引擎链 + 多 key 轮换）
    #    引擎链：google_lens 精确匹配 → google_lens 视觉匹配 → google_reverse_image 兜底。
    #    google_reverse_image 对部分图片会判定"无匹配"（而 Google 网页能搜到"外观匹配"），
    #    google_lens(exact_matches/visual_matches) 覆盖更全（2026-09 实测精确匹配返回更丰富）。
    keys = settings.serpapi_keys
    if not keys:
        raise ReverseImageNotConfigured(
            "SerpAPI 未配置 api_key，无法反向识图。")
    # (engine, 参数字典, 图片参数名)
    ENGINE_CHAIN = [
        ("google_lens", {"type": "exact_matches"}, "url"),
        ("google_lens", {"type": "visual_matches"}, "url"),
        ("google_reverse_image", {}, "image_url"),
    ]
    last_err = None
    for key in keys:
        for engine, extra, img_param in ENGINE_CHAIN:
            try:
                params = {"engine": engine, img_param: public_url, "api_key": key, **extra}
                async with httpx.AsyncClient(timeout=45, trust_env=False) as client:
                    r = await client.get(
                        "https://serpapi.com/search.json",
                        params=params,
                    )
                    r.raise_for_status()
                    data = r.json()
                if "error" in data:
                    _err = str(data["error"])
                    # 无匹配结果：不是故障，继续尝试下一个引擎
                    if ("hasn't returned any results" in _err or "no results" in _err.lower()):
                        print(f"[reverse_image] {engine}({extra.get('type','')}) 无匹配，尝试下一引擎", flush=True)
                        continue
                    raise RuntimeError(f"SerpAPI 返回错误：{_err}")
                items = (
                    data.get("exact_matches")
                    or data.get("visual_matches")
                    or data.get("image_results")
                    or data.get("inline_images")
                    or []
                )
                if not items:
                    continue  # 空结果 → 下一引擎
                results = []
                for item in items[:8]:
                    results.append({
                        "engine": f"SerpAPI {engine}" + (f"({extra.get('type','')})" if extra else ""),
                        "matched_site": item.get("source", ""),
                        "matched_title": item.get("title", ""),
                        "published_date": item.get("date", ""),
                        "url": item.get("link", item.get("original", "")),
                        "note": item.get("snippet", ""),
                    })
                return {
                    "results": results,
                    "mode": "serpapi",
                    "image_url": public_url,
                    "warning": upload_note,
                }
            except Exception as e:
                last_err = e
                print(f"[reverse_image] {engine}({extra.get('type','')}) key({key[:8]}...) 失败：{e}，尝试下一通道", flush=True)
                continue
    raise ReverseImageNotConfigured(f"SerpAPI 所有通道均未返回结果：{last_err}")
