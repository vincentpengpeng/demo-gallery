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
    """
    params = {"engine": "google", "q": query, "num": count,
              "api_key": settings.serpapi_api_key}
    if gl:
        params["gl"] = gl
    if hl:
        params["hl"] = hl
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
    """多语种检索：SerpAPI Google 主通道 + 火山/DDG 兜底（并行、快速失败）。

    中英关键词并行查询，且主动追加『中方官方信源定向检索』，
    确保证据采集包含中方立场/回应，避免单方叙事（反驳证据主动检索，防确认偏误）。
    type 字段区分『搜索结果』（可溯源）与『AI检索综述』（需人工核实）；
    视角标注 origin：cn_official（中国官方）/ cn_media（中国媒体）/ 其他。
    """
    queries = []
    if keywords.get("zh"):
        queries.append(keywords["zh"])
    if keywords.get("en"):
        queries.append(keywords["en"])

    # 主动追加中方立场定向检索（官方信源优先）
    cn_official_queries = []
    if keywords.get("zh"):
        cn_official_queries.append(
            f'{keywords["zh"].split("、")[0]} 外交部 国防部 发言人 回应')
    if keywords.get("en"):
        cn_official_queries.append(
            f'{keywords["en"].split(",")[0].strip()} China MFA MOD spokesperson response')
    cn_media_queries = []
    if keywords.get("zh"):
        cn_media_queries.append(
            f'{keywords["zh"].split("、")[0]} 新华社 OR 人民日报 OR 环球时报 报道')
    if keywords.get("en"):
        cn_media_queries.append(
            f'{keywords["en"].split(",")[0].strip()} Xinhua OR CGTN OR China Daily report')

    if not queries and not cn_official_queries and not cn_media_queries:
        return []

    async def _query(q: str, n: int, gl: str = "", hl: str = "", official: bool = False) -> list:
        # 优先级：SerpAPI Google → Brave → DDG → 火山 Web Search
        if settings.serpapi_api_key:
            try:
                if official:
                    # 官方信源定向：用机构+回应措辞（Google 对 site: 多域名支持不稳定）
                    q = f"中国国防部 回应 {q}"
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

    # 组装检索任务：zh/en 主查询各 4 条，官方/媒体定向各 2 条
    tasks = []
    if keywords.get("zh"):
        tasks.append(_query(keywords["zh"], 4, gl="cn", hl="zh-CN"))
    if keywords.get("en"):
        tasks.append(_query(keywords["en"], 4))
    for oq in cn_official_queries:
        tasks.append(_query(oq, 2, gl="cn", hl="zh-CN", official=True))
    for mq in cn_media_queries:
        tasks.append(_query(mq, 2, gl="cn", hl="zh-CN"))

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

    # 视角标注：识别中国官方/媒体信源 + 外媒官方喉舌（政府出资外宣媒体）
    CN_OFFICIAL_DOMAINS = ["gov.cn", "mod.gov.cn", "fmprc.gov.cn", "12371.cn", "cctv.com"]
    CN_MEDIA_DOMAINS = ["news.cn", "xinhuanet.com", "people.com.cn", "chinadaily.com.cn",
                        "cgtn.com", "ecns.cn", "gmw.cn", "huanqiu.com", "globaltimes.cn",
                        "china.com.cn", "cri.cn", "caixin.com", "yicai.com", "thepaper.cn",
                        "hxny.com"]
    CN_OFFICIAL_KEYWORDS = ["国防部", "外交部", "国务院", "国防部发言人", "外交部发言人", "中国海警"]
    CN_MEDIA_KEYWORDS = ["新华社", "人民日报", "央视", "中国日报", "环球时报", "环球网",
                         "光明网", "中国新闻网", "观察者", "澎湃", "中国网", "CGTN", "Global Times",
                         "Xinhua", "People's Daily", "China Daily", "huanqiu"]
    # 外媒官方喉舌：外国政府出资的对华外宣媒体（涉华报道常带对抗性框架，需特别标注）
    FOREIGN_STATE_DOMAINS = ["voanews.com", "voachinese.com", "rfa.org", "dw.com", "rfi.fr",
                             "rt.com", "voatibetan.com", "voacantonese.com", "radionz.co.nz",
                             "cna.com.tw"]
    FOREIGN_STATE_KEYWORDS = ["美国之音", "自由亚洲电台", "德国之声", "法国国际广播", "今日俄罗斯",
                              "Voice of America", "Radio Free Asia", "Deutsche Welle",
                              "Radio France Internationale", "Russia Today", "VOA", "RFA", "DW", "RT"]
    for item in uniq:
        url = item.get("url", "").lower()
        src = item.get("source", "")
        title = item.get("title", "")
        text_low = (src + " " + title).lower()
        if any(d in url for d in CN_OFFICIAL_DOMAINS) or \
           any(k in text_low for k in CN_OFFICIAL_KEYWORDS):
            item["origin"] = "cn_official"
        elif any(d in url for d in CN_MEDIA_DOMAINS) or \
             any(k.lower() in text_low for k in CN_MEDIA_KEYWORDS):
            item["origin"] = "cn_media"
        elif any(d in url for d in FOREIGN_STATE_DOMAINS) or \
             any(k.lower() in text_low for k in FOREIGN_STATE_KEYWORDS):
            item["origin"] = "foreign_state_media"
        else:
            item["origin"] = "other"

    # 排序：中方官方 → 中方媒体 → 普通外媒/外媒官方喉舌（中方立场证据前置）
    uniq.sort(key=lambda x: 0 if x.get("origin") == "cn_official" else
              (1 if x.get("origin") == "cn_media" else 2))
    return uniq[:count]
