# -*- coding: utf-8 -*-
"""联网检索服务：多通道真实搜索。

主通道：SerpAPI Google 网页搜索（结构化标题/URL/摘要/日期，可进证据矩阵，与识图共用 key）。
备选：火山方舟 Web Search（官方 API 稳定，返回多源综述）。
兜底：DuckDuckGo HTML。
"""
import asyncio
import re
import urllib.parse
from html import unescape

import httpx

from ..config import settings, SEARCH_ENABLED
from .llm import llm_service

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")


def _parse_ddg(html_text: str) -> list:
    """解析 DDG html 端点结果 → 结构化列表。"""
    results = []
    blocks = re.split(r'class="result results_links', html_text)[1:]
    for b in blocks:
        m_title = re.search(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', b, re.S)
        m_snippet = re.search(r'class="result__snippet"[^>]*>(.*?)</a>', b, re.S)
        if not m_title:
            continue
        title = re.sub(r"<[^>]+>", "", m_title.group(2))
        snippet = re.sub(r"<[^>]+>", "", m_snippet.group(1)) if m_snippet else ""
        url = m_title.group(1)
        if "duckduckgo.com/l/?uddg=" in url:
            url = urllib.parse.unquote(url.split("uddg=")[1].split("&")[0])
        results.append({
            "title": unescape(title).strip(),
            "url": url,
            "snippet": unescape(snippet).strip(),
            "source": urllib.parse.urlparse(url).netloc,
            "date": "",
            "type": "搜索结果",
        })
    return results


async def _search_serpapi_google(query: str, count: int = 5, gl: str = "", hl: str = "") -> list:
    """SerpAPI Google 网页搜索（主通道，与识图共用 key）。

    gl/hl：地域与语言参数（中文查询传 cn/zh-CN，保证中文结果质量）。
    支持多 key 轮换：配置多个 key（逗号分隔）时，额度用尽的 key 自动跳过换下一个。
    """
    keys = settings.serpapi_keys
    if not keys:
        raise RuntimeError("SerpAPI 未配置 api_key")
    last_err = None
    for key in keys:
        params = {"engine": "google", "q": query, "num": count,
                  "api_key": key}
        if gl:
            params["gl"] = gl
        if hl:
            params["hl"] = hl
        try:
            async with httpx.AsyncClient(timeout=25, trust_env=False) as client:
                r = await client.get("https://serpapi.com/search.json", params=params)
                r.raise_for_status()
                data = r.json()
            if "error" in data:
                raise RuntimeError(data["error"])
            results = []
            for item in data.get("organic_results", [])[:count]:
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("link", ""),
                    "snippet": item.get("snippet", ""),
                    "source": item.get("source", ""),
                    "date": item.get("date", ""),
                    "type": "搜索结果",
                })
            return results
        except Exception as e:
            last_err = e
            print(f"[search] SerpAPI key({key[:8]}...) 调用失败：{e}，尝试下一个 key", flush=True)
            continue
    raise RuntimeError(f"SerpAPI 所有 key 均调用失败：{last_err}")


async def _search_ddg(query: str, count: int = 5) -> list:
    """DuckDuckGo 免key搜索（兜底，快速失败）。"""
    async with httpx.AsyncClient(timeout=8, follow_redirects=True, trust_env=False) as client:
        r = await client.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query},
            headers={"User-Agent": UA},
        )
        r.raise_for_status()
        return _parse_ddg(r.text)[:count]


async def _search_ark_web(query: str, count: int = 5) -> list:
    """火山方舟 Web Search（备选通道）：返回多源整合综述。"""
    if not settings.ark_api_key:
        return []
    payload = {
        "model": settings.ark_model,
        "tools": [{"type": "web_search"}],
        "input": query,
    }
    async with httpx.AsyncClient(timeout=50, trust_env=False) as client:
        r = await client.post(
            settings.ark_base_url + "/responses",
            headers={"Authorization": f"Bearer {settings.ark_api_key}",
                     "Content-Type": "application/json"},
            json=payload,
        )
        r.raise_for_status()
        data = r.json()

    texts = []
    for o in data.get("output", []):
        if o.get("type") == "message":
            for c in o.get("content", []):
                if c.get("type") == "output_text" and c.get("text"):
                    texts.append(c["text"])
    if not texts:
        return []

    return [{
        "title": f"火山方舟 Web Search 检索综述：{query[:40]}",
        "url": "",
        "snippet": texts[0][:500],
        "source": "火山方舟 Web Search",
        "date": "",
        "type": "AI检索综述",
        "note": "由火山 Web Search 多源整合生成，无独立来源URL，需人工核实后再作为证据。",
    }]


async def _search_brave(query: str, count: int = 5) -> list:
    """Brave Search API（可选，需 key）。"""
    results = []
    async with httpx.AsyncClient(timeout=20, trust_env=False) as client:
        r = await client.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": count, "country": "all"},
            headers={"X-Subscription-Token": settings.brave_api_key},
        )
        r.raise_for_status()
        for item in r.json().get("web", {}).get("results", [])[:count]:
            results.append({
                "title": item.get("title", ""),
                "source": item.get("source", ""),
                "date": item.get("age", ""),
                "url": item.get("url", ""),
                "snippet": item.get("description", ""),
                "type": "搜索结果",
            })
    return results


async def search_multilingual(keywords: dict, count: int = 8) -> list:
    """多语种检索：中方视角与西方视角双通道（并行、快速失败）。

    视角分流（解决"中方主张搜不出"）：
    - 中方视角（zh_official 官方回应 / zh_media 媒体报道 / zh 主查询）：
      火山方舟 Web Search（国内通道，中文/中方信源覆盖好）与 SerpAPI Google(cn) **并行**取并集；
    - 西方视角（en_west 外媒指控 / en 主查询）：SerpAPI Google 优先，命中外媒/西方信源。

    关键词缺失时自动退化（zh/en 兜底）；type 区分『搜索结果』与『AI检索综述』；
    视角标注 origin：cn_official（中国官方）/ cn_media（中国媒体）/ 其他。
    """
    zh = (keywords.get("zh") or "").strip()
    en = (keywords.get("en") or "").strip()
    zh_official = (keywords.get("zh_official") or "").strip()
    zh_media = (keywords.get("zh_media") or "").strip()
    en_west = (keywords.get("en_west") or "").strip()

    if not (zh or en or zh_official or zh_media or en_west):
        return []

    async def _serpapi_or_fallback(q: str, n: int, gl: str = "", hl: str = "") -> list:
        # 优先级：SerpAPI Google → Brave → DDG → 火山 Web Search
        if settings.serpapi_api_key:
            try:
                return await _search_serpapi_google(q, n, gl=gl, hl=hl)
            except Exception:
                pass
        if SEARCH_ENABLED and settings.brave_api_key:
            try:
                return await _search_brave(q, n)
            except Exception:
                pass
        try:
            return await _search_ddg(q, n)
        except Exception:
            try:
                return await _search_ark_web(q, n)
            except Exception:
                return []

    async def _safe_ark(q: str, n: int) -> list:
        """火山方舟 Web Search 安全包裹：失败返回空，不影响 Google 通道（双通道任一可用即可）。"""
        try:
            return await _search_ark_web(q, n)
        except Exception as _e:
            print(f"[search] 火山 Web Search 失败：{_e}，仅使用 Google(cn) 结果", flush=True)
            return []

    async def _query_cn(q: str, n: int) -> list:
        """中方视角双通道：火山方舟 Web Search（国内通道）+ SerpAPI Google(cn) 并行取并集。"""
        ark_res, goog_res = await asyncio.gather(
            _safe_ark(q, n),
            _serpapi_or_fallback(q, n, gl="cn", hl="zh-CN"),
        )
        return list(ark_res) + list(goog_res)

    # 组装检索任务：中方视角 3 组（官方/媒体走双通道，主查询走 Google(cn)），西方视角 2 组（Google 优先）
    tasks = []
    if zh_official:
        tasks.append(_query_cn(zh_official, 3))
    if zh_media:
        tasks.append(_query_cn(zh_media, 3))
    if zh:
        tasks.append(_serpapi_or_fallback(zh, 4, gl="cn", hl="zh-CN"))
    if en_west:
        tasks.append(_serpapi_or_fallback(en_west, 4))
    if en and en != en_west:
        tasks.append(_serpapi_or_fallback(en, 3))

    results_lists = await asyncio.gather(*tasks)

    results = []
    for lst in results_lists:
        results.extend(lst)

    # 去重（按 URL 或标题）
    seen = set()
    uniq = []
    for item in results:
        key = item.get("url") or item.get("title", "")
        if key and key not in seen:
            seen.add(key)
            uniq.append(item)

    # 视角标注：外媒官方喉舌 / 中方官方 / 中方媒体（用完整名称+域名精确匹配，禁止短缩写）
    # —— 外媒官方喉舌：外国政府出资的对华外宣媒体，涉华报道常带对抗性框架，需特别标注
    FOREIGN_STATE_MEDIA = {
        "美国之音": ["voanews.com", "voachinese.com", "voatibetan.com", "voacantonese.com",
                      "voaindonesia.com", "voice of america"],
        "自由亚洲电台": ["rfa.org", "radio free asia"],
        "德国之声": ["dw.com", "deutsche welle"],
        "法国国际广播": ["rfi.fr", "radio france internationale", "rfi chinese"],
        "今日俄罗斯": ["rt.com", "russia today", "今日俄罗斯"],
        "自由欧洲电台": ["rferl.org", "radio free europe", "自由欧洲电台"],
        "新西兰广播电台": ["radionz.co.nz", "新西兰广播电台"],
        "台湾中央社": ["cna.com.tw", "中央社"],
        "美国之音中文网": ["voachinese.com", "美国之音"],
    }
    CN_OFFICIAL_MEDIA = {
        "中国国务院": ["gov.cn", "www.gov.cn"],
        "国防部": ["mod.gov.cn"],
        "外交部": ["fmprc.gov.cn"],
        "中共中央": ["12371.cn"],
        "中央广电": ["cctv.com", "china central television"],
    }
    CN_MEDIA_LIST = {
        "新华社": ["news.cn", "xinhuanet.com", "xinhua"],
        "人民日报": ["people.com.cn", "people's daily", "people daily"],
        "中国日报": ["chinadaily.com.cn", "china daily"],
        "央视": ["cctv.com", "cgtn.com", "china global television network"],
        "中国网": ["china.com.cn", "ecns.cn"],
        "光明网": ["gmw.cn", "guangming"],
        "环球时报": ["huanqiu.com", "globaltimes.com.cn", "global times"],
        "中新网": ["chinanews.com.cn", "中国新闻网"],
        "澎湃": ["thepaper.cn"],
        "观察者": ["guancha.cn"],
        "财新": ["caixin.com"],
        "第一财经": ["yicai.com"],
        "红星新闻": ["hxny.com"],
        "参考消息": ["cankaoxiaoxi.com"],
        "CGTN": ["cgtn.com"],
    }
    CN_OFFICIAL_NAMES = ["国防部", "外交部", "国务院", "发言人", "中国海警"]
    CN_MEDIA_NAMES = ["新华社", "人民日报", "央视", "中国日报", "环球时报", "环球网",
                      "光明网", "中国新闻网", "观察者", "澎湃", "中国网", "CGTN",
                      "环球网", "参考消息", "财新", "第一财经"]
    # title 中仅认这些强官方信号词（避免标题含"中国海警"等对象词的外媒/百科被误判为中方官方）
    CN_OFFICIAL_TITLE_STRONG = ["外交部", "国防部", "国务院"]

    for item in uniq:
        url = item.get("url", "").lower()
        src = item.get("source", "")
        title = item.get("title", "")
        # 名称匹配只认 source（机构名），title 不作为信源归属依据（防止标题含"中国海警/外交部"的外媒被误判）
        src_low = src.lower()
        title_low = title.lower()
        origin = None
        # 1) 外媒官方喉舌（域名精确匹配，优先级最高，不受标题内容影响）
        for name, keys in FOREIGN_STATE_MEDIA.items():
            if any(k in url for k in keys):
                origin = "foreign_state_media"
                break
        # 2) 中方官方（域名匹配）
        if origin is None:
            for name, keys in CN_OFFICIAL_MEDIA.items():
                if any(k in url for k in keys):
                    origin = "cn_official"
                    break
        # 3) 中方媒体（域名匹配）
        if origin is None:
            for name, keys in CN_MEDIA_LIST.items():
                if any(k in url for k in keys):
                    origin = "cn_media"
                    break
        # 4) 外媒喉舌机构名（source 含中文全称/英文名/域名后缀，先于中方名称，避免中文名被后续误配）
        if origin is None:
            for name, keys in FOREIGN_STATE_MEDIA.items():
                if any(k in src_low for k in keys):
                    origin = "foreign_state_media"
                    break
        # 5) 中方官方机构名（source）
        if origin is None:
            if any(k.lower() in src_low for k in CN_OFFICIAL_NAMES):
                origin = "cn_official"
        # 6) 中方媒体机构名（source）
        if origin is None:
            if any(k.lower() in src_low for k in CN_MEDIA_NAMES):
                origin = "cn_media"
        # 7) title 强官方信号（仅"外交部/国防部/国务院"等机构名，不作泛词匹配）
        if origin is None:
            if any(k in title_low for k in CN_OFFICIAL_TITLE_STRONG):
                origin = "cn_official"
        item["origin"] = origin or "other"

    # LLM 批量初筛：一次调用判定每条候选是否与核查主题相关（替代纯关键词规则过滤，
    # 可识别"事件主体不符"等语义错配，如本案中菲碰撞 vs 中方内部旧闻）。
    # LLM 未启用/失败/判定为空时保留全部（宁多勿漏，交下游环节处理）。
    if uniq:
        _items = [
            {"id": i, "title": (it.get("title") or "")[:150],
             "source": (it.get("source") or "")[:60],
             "snippet": (it.get("snippet") or "")[:200],
             "url": (it.get("url") or "")[:200]}
            for i, it in enumerate(uniq)
        ]
        try:
            _rel = llm_service.filter_relevant(
                {"zh": keywords.get("zh", ""), "en": keywords.get("en", "")}, _items)
            _keep = set()
            for _r in (_rel.get("results") or []):
                _rid = _r.get("id")
                try:
                    _rid = int(_rid)
                except (TypeError, ValueError):
                    continue
                if _r.get("relevant") is True:
                    _keep.add(_rid)
            if _keep:
                uniq = [it for i, it in enumerate(uniq) if i in _keep]
        except Exception as _e:
            print(f"[search] LLM 初筛失败，保留全部：{_e}", flush=True)

    # 排序：中方官方 → 中方媒体 → 普通外媒/外媒官方喉舌（中方立场证据前置），同级保持召回顺序
    uniq.sort(key=lambda x: 0 if x.get("origin") == "cn_official" else
              (1 if x.get("origin") == "cn_media" else 2))
    return uniq[:count]
