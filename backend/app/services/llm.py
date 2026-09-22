# -*- coding: utf-8 -*-
"""火山引擎 Ark LLM 服务：主张拆解、关键词生成、信源评价、报告生成。

未配置 ARK_API_KEY 时自动降级为规则/演示模式，保证系统可离线跑通全流程。
"""
import json
import re
from typing import Optional

from ..config import settings, LLM_ENABLED


class LLMService:
    def __init__(self):
        self._client = None
        self._ocr_client = None
        if LLM_ENABLED:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=settings.ark_api_key,
                base_url=settings.ark_base_url,
                timeout=90,          # 推理模型任务较长，放宽超时
                max_retries=1,
            )
        if settings.ocr_api_key:
            from openai import OpenAI
            self._ocr_client = OpenAI(
                api_key=settings.ocr_api_key,
                base_url=settings.ocr_base_url or "https://ark.cn-beijing.volces.com/api/v3",
                timeout=90,
                max_retries=1,
            )

    @property
    def enabled(self) -> bool:
        return self._client is not None

    @property
    def ocr_enabled(self) -> bool:
        return self._ocr_client is not None

    def chat_json(self, system: str, user: str, fallback: dict, max_tokens: int = 1500,
                  timeout: Optional[float] = None) -> dict:
        """调用 Ark，要求返回 JSON；失败或未配置时返回 fallback。

        timeout：单次调用的超时秒数；None 时沿用 client 默认（90s）。
        大输出任务（如证据批量判定）应显式传更长超时，避免推理未完成被中断。
        """
        if not self._client:
            return fallback
        # 推理模型 reasoning tokens 占用波动大：空输出时重试一次
        for attempt in range(2):
            try:
                resp = self._client.chat.completions.create(
                    model=settings.ark_model,
                    messages=[
                        {"role": "system", "content": system + " 只输出 JSON，不要输出其他文字。"},
                        {"role": "user", "content": user},
                    ],
                    temperature=0.2,
                    max_tokens=max_tokens,
                    response_format={"type": "json_object"},
                    timeout=timeout,
                )
                text = resp.choices[0].message.content or ""
                if not text.strip():
                    # 输出为空（reasoning 占满）→ 重试
                    if attempt == 0:
                        continue
                    return fallback
                parsed = self._safe_parse(text)
                if parsed:
                    return parsed
            except Exception:
                pass
        return fallback

    def _safe_parse(self, text: str) -> Optional[dict]:
        try:
            return json.loads(text)
        except Exception:
            m = re.search(r"\{.*\}", text, re.S)
            if m:
                try:
                    return json.loads(m.group(0))
                except Exception:
                    pass
            # 模型偶发丢失首字符/首行（如开头缺 {）：补全后重试
            for candidate in ("{" + text, "{\n" + text):
                try:
                    return json.loads(candidate)
                except Exception:
                    continue
            return None

    # ---------- 多模态 OCR：图片文字识别 ----------
    def ocr_image(self, image_bytes: bytes, image_format: str = "png") -> str:
        """识别图片中的文字（deepseek-v4-1-flash 多模态，base64 直传，标准版 api/v3）。"""
        client = self._ocr_client or self._client
        if not client:
            return ""
        import base64
        b64 = base64.b64encode(image_bytes).decode()
        mime = "image/png" if image_format == "png" else "image/jpeg"
        model = settings.ocr_model if self._ocr_client else settings.ark_model
        try:
            resp = client.responses.create(
                model=model,
                input=[
                    {"role": "user", "content": [
                        {"type": "input_text",
                         "text": "请识别这张图片中的所有文字，逐行原样输出，不要翻译不要总结不要添加额外说明。"},
                        {"type": "input_image",
                         "image_url": f"data:{mime};base64,{b64}"},
                    ]}
                ],
                timeout=90,
            )
            texts = []
            for o in (resp.output or []):
                if getattr(o, "type", "") == "message":
                    for c in (getattr(o, "content", None) or []):
                        if getattr(c, "type", "") == "output_text":
                            texts.append(getattr(c, "text", "") or "")
            return "\n".join(t for t in texts if t)
        except Exception:
            return ""

    # ---------- 图片真实性核查：多模态图片理解 ----------
    def analyze_image(self, image_url: str) -> dict:
        """多模态分析图片：画面描述 + 图中文字 + 真实性线索，并生成供下游环节使用的转写文本。

        输入：图片公网 URL（图床 raw / http 链接）。
        输出：{"scene_description", "text_in_image", "authenticity_clues", "suspected",
              "reason", "transcript"}
        suspected：real_scene(真实现场图) / ai_generated(疑似AI生成) / ps_edited(疑似PS拼接) /
                   old_image_reuse(疑似旧图新用) / unclear(无法判断)
        """
        client = self._ocr_client or self._client
        if not client:
            return {"scene_description": "", "text_in_image": "", "authenticity_clues": [],
                    "suspected": "unclear", "reason": "多模态模型未配置", "transcript": ""}
        try:
            import httpx
            # 同步下载：analyze_image 可能在 async 流水线（运行中事件循环）内被调用，
            # 不能用 asyncio.run（会报 RuntimeError），统一用同步 httpx.Client。
            try:
                with httpx.Client(timeout=30, follow_redirects=True, trust_env=False) as c:
                    r = c.get(image_url)
                    r.raise_for_status()
                    image_bytes = r.content
            except Exception:
                image_bytes = b""
            if not image_bytes:
                return {"scene_description": "", "text_in_image": "", "authenticity_clues": [],
                        "suspected": "unclear", "reason": "图片下载失败，无法分析", "transcript": ""}
            import base64
            b64 = base64.b64encode(image_bytes).decode()
            mime = "image/png"
            if image_bytes[:3] == b"\xff\xd8\xff":
                mime = "image/jpeg"
            elif image_bytes[:4] == b"GIF8":
                mime = "image/gif"
            elif image_bytes[:8] == b"\x89PNG\r\n\x1a\n":
                mime = "image/png"
            model = settings.ocr_model if self._ocr_client else settings.ark_model
            system = (
                "你是专业的图片真实性核查分析员，服务对象是核查外媒涉华不当、虚假表述的工作室。\n"
                "请分析这张图片并只输出JSON，结构如下：\n"
                "{\n"
                "  \"scene_description\": \"画面内容客观描述（场景、主体、人物/船只/建筑、天气光线、"
                "可见标识旗帜文字等，300字内，不臆测）\",\n"
                "  \"text_in_image\": \"图中可见的所有文字/水印/标注，逐行原样提取；没有则为空字符串\",\n"
                "  \"authenticity_clues\": [\"真实性疑点列表，如：AI生成痕迹（手指畸形/文字扭曲/纹理异常）、"
                "PS拼接疑点（阴影方向不一致/边缘生硬）、水印覆盖、分辨率异常、画面内容与宣称时间地点场景不符等；"
                "无则空数组\"],\n"
                "  \"suspected\": \"real_scene|ai_generated|ps_edited|old_image_reuse|unclear\",\n"
                "  \"reason\": \"判定理由一句话\"\n"
                "}\n"
                "要求：客观描述，不臆测；图中文字逐字提取不翻译；无把握时 suspected=unclear，宁保守勿乱下结论。"
            )
            parsed = None
            raw = ""
            # 模型输出偶发不稳定（reasoning 可能挤占输出、或返回非 JSON）：最多重试 3 次
            for attempt in range(3):
                resp = client.responses.create(
                    model=model,
                    input=[
                        {"role": "system", "content": [{"type": "input_text", "text": system}]},
                        {"role": "user", "content": [
                            {"type": "input_text", "text": "请分析这张图片的拍摄内容与真实性。"},
                            {"type": "input_image", "image_url": f"data:{mime};base64,{b64}"},
                        ]},
                    ],
                    max_output_tokens=6000,
                    timeout=120,
                )
                texts = []
                for o in (resp.output or []):
                    if getattr(o, "type", "") == "message":
                        for c in (getattr(o, "content", None) or []):
                            if getattr(c, "type", "") == "output_text" and getattr(c, "text", ""):
                                texts.append(c.text)
                raw = "\n".join(texts)
                parsed = self._safe_parse(raw)
                if not parsed:
                    import re as _re
                    stripped = _re.sub(r"```(?:json)?", "", raw)
                    parsed = self._safe_parse(stripped)
                if parsed:
                    break
            if not parsed:
                print(f"[analyze_image] 解析失败，原始输出前300字：{raw[:300]}", flush=True)
                return {"scene_description": "", "text_in_image": "", "authenticity_clues": [],
                        "suspected": "unclear", "reason": "图片分析输出解析失败", "transcript": ""}
            scene = (parsed.get("scene_description") or "").strip()
            txt = (parsed.get("text_in_image") or "").strip()
            clues = parsed.get("authenticity_clues") or []
            if not isinstance(clues, list):
                clues = []
            suspected = parsed.get("suspected") or "unclear"
            if suspected not in ("real_scene", "ai_generated", "ps_edited", "old_image_reuse", "unclear"):
                suspected = "unclear"
            # 转写文本：画面描述 + 图中文字，供主张拆解/检索等下游环节使用
            transcript = scene
            if txt:
                transcript = f"{scene}\n图中文字：{txt}"
            return {
                "scene_description": scene,
                "text_in_image": txt,
                "authenticity_clues": clues,
                "suspected": suspected,
                "reason": (parsed.get("reason") or "").strip(),
                "transcript": transcript,
            }
        except Exception:
            return {"scene_description": "", "text_in_image": "", "authenticity_clues": [],
                    "suspected": "unclear", "reason": "图片分析异常", "transcript": ""}
            return "\n".join(t for t in texts if t)
        except Exception:
            return ""

    # ---------- 自动翻译：中英互译 ----------
    def translate(self, text: str, target: str = "zh") -> str:
        """把 text 翻译成目标语言（zh=中文, en=英文）；失败返回空字符串。"""
        if not self._client or not text.strip():
            return ""
        if target == "en":
            system = "你是专业翻译。把用户提供的内容翻译成准确、自然的英文，只输出译文，不要任何解释。"
            user = f"原文：\n{text}\n\n请翻译成英文。"
        else:
            system = "你是专业翻译。把用户提供的外文内容翻译成准确、流畅的中文，只输出译文，不要任何解释。"
            user = f"原文：\n{text}\n\n请翻译成中文。"
        try:
            resp = self._client.chat.completions.create(
                model=settings.ark_model,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user}],
                temperature=0.2,
                max_tokens=2000,
            )
            return (resp.choices[0].message.content or "").strip()
        except Exception:
            return ""

    def translate_to_chinese(self, text: str) -> str:
        """兼容旧调用：外文 → 中文。"""
        return self.translate(text, "zh")

    def translate_to_english(self, text: str) -> str:
        """中文 → 英文。"""
        return self.translate(text, "en")

    # ---------- 环节2：价值初筛（LLM 判断） ----------
    def screen_clue(self, title: str, raw_text: str, translated: str = "") -> dict:
        """判断线索是否值得进入核查。

        从中国立场出发，判断线索是否：①涉及中国相关议题；②含可核查的事实主张；
        ③属于外媒涉华不当/虚假表述高发领域（军事对峙、疫情、人权、香港、台湾、
        新疆、经济数据等）。返回 passed/score/reason/focus。
        """
        system = (
            "你是价值初筛分析员，服务对象是核查外媒涉华不当、虚假表述的工作室。\n"
            "请从中国立场出发判断这条线索是否值得进入事实核查：\n"
            "1. 是否涉及中国相关议题（人物、机构、事件、领土、政策、数据、军事等与中方相关）；\n"
            "2. 是否包含可核查的事实主张（有具体的时间地点人物数字事件，而非纯观点或情绪）；\n"
            "3. 是否属于外媒涉华不当表述高发领域（如军事对抗、疫情、人权、香港、台湾、"
            "新疆、经济与数据、内政干涉等）。\n"
            "判定标准：以上 3 点任一点成立即应进入核查；即使标题/原文未直接出现'中国/China'"
            "字样，只要内容实质涉及中国（如'Chinese'、'Beijing'、'Chinese aircraft'、"
            "'off North Korea' 涉中军事活动等），也应判定为通过。\n"
            "只输出JSON：{\"passed\":true|false,\"score\":0-100,\"reason\":\"一句话判断理由\","
            "\"focus\":\"线索涉及的主要议题方向，如：涉华军事活动\"}"
        )
        user = (
            f"标题：{title}\n原文：{raw_text}\n"
            f"翻译：{translated if translated else '（无）'}\n"
            "请输出判断JSON。"
        )
        fallback = {"passed": False, "score": 30,
                    "reason": "LLM 初筛未启用，请人工判断是否进入核查。",
                    "focus": ""}
        return self.chat_json(system, user, fallback, max_tokens=500)

    # ---------- 环节3：主张拆解 ----------
    def decompose_claims(self, raw_text: str, translated: str = "") -> dict:
        system = (
            "你是专业的事实核查分析员，服务对象是核查外媒涉华不当、虚假表述的工作室。\n"
            "你的核查核心任务是：识别外媒、人权组织、国际机构等**对中国（或中方政策/行为）的指控性、定性性表述**，\n"
            "判断这些表述是否有事实依据，是否构成夸大、歪曲、误导。\n"
            "请把原文拆解为以下类型的主张：\n"
            "1. **allegation（指控/定性表述）——核查主线，最重要**：外媒/人权组织/学者等对中国的指控、定性、比喻、"
            "断言（如'把边控变成常态化治理工具''边境是监狱''威胁地区稳定'等）。"
            "必须提取：表述主体（谁说的，如'人权组织'）、指控对象、定性/比喻用语、核心断言。\n"
            "2. fact（事实主张）：关于事件、时间、地点、数据、政策内容的客观陈述（如'新规于7月31日颁布'）。\n"
            "3. view（观点表达）：一般性评论，不构成明确指控或事实断言。\n"
            "4. emotion（情绪表达）：纯情绪化语言。\n"
            "【关键要求】allegation 是核查重点，必须完整、准确地呈现原文的定性用语（保留原词，如'监狱''常态化治理工具'），"
            "不得淡化或改写；事实主张（fact）用于核实'事实层'是否准确，"
            "而 allegation 用于核实'指控层'是否有证据支撑——两者必须分开拆解，不得混为一谈。\n"
            "对每个主张提取要素：人物/主体、地点、时间、事件。"
            "同时生成用于多语种检索的关键词组，关键词须覆盖指控性表述的核心用语，并按检索视角拆分：\n"
            "1. keywords.zh：中文综合检索词（纯中文），覆盖事件与指控核心；\n"
            "2. keywords.en：英文综合检索词（纯英文），覆盖事件与指控核心；\n"
            "3. keywords.zh_official：中文·中方官方回应检索词（纯中文），用于检索中方立场与官方回应，"
            "必须包含中方回应/驳斥措辞（如'中方回应''驳斥''发言人''声明'），"
            "例：'南海中菲撞船 中方回应 中国海警局声明'；\n"
            "4. keywords.zh_media：中文·中方媒体报道检索词（纯中文），用于检索新华社/人民日报/环球时报等中方媒体"
            "对事件的报道与立场，例：'南海中菲撞船 新华社 环球时报 报道'；\n"
            "5. keywords.en_west：英文·西方外媒视角检索词（纯英文），用于检索外媒/西方信源对该事件的报道与指控表述，"
            "例：'China coast guard ram Philippine boat condemn'。\n"
            "【关键词语言要求】zh/zh_official/zh_media 必须是纯中文，en/en_west 必须是纯英文，"
            "严禁把英文关键词原样放进中文组，也不要把中文关键词放进英文组。\n"
            "注意：拆解时保持客观，如实呈现原文表述，不添油加醋；"
            "是否'不当/虚假'由后续核查环节用证据判定，拆解环节只负责准确拆分与标注。"
            "结论分类定义：真实/基本真实/缺乏语境/误导/基本错误/虚假/尚待核实/无法核查。"
        )
        user = f"原文：\n{raw_text}\n\n翻译：\n{translated}\n\n请输出JSON：{{\"claims\":[{{\"text\":\"...\",\"type\":\"allegation|fact|view|emotion\",\"elements\":{{\"人物/主体\":\"\",\"地点\":\"\",\"时间\":\"\",\"事件\":\"\",\"定性用语\":\"\"}}}}],\"keywords\":{{\"zh\":\"...\",\"en\":\"...\",\"zh_official\":\"...\",\"zh_media\":\"...\",\"en_west\":\"...\"}}}}"
        fallback = self._rule_decompose(raw_text)
        return self.chat_json(system, user, fallback, max_tokens=2500)

    def _rule_decompose(self, text: str) -> dict:
        """无 LLM 时的规则降级：粗拆句子。"""
        sentences = re.split(r"[。！？!?；;\n]", text)
        claims = []
        for s in sentences:
            s = s.strip()
            if not s or len(s) < 4:
                continue
            claims.append({
                "text": s,
                "type": "fact",
                "elements": {"人物": "", "地点": "", "时间": "", "事件": s[:50]},
            })
        if not claims:
            claims = [{"text": text, "type": "fact",
                       "elements": {"人物": "", "地点": "", "时间": "", "事件": text[:50]}}]
        return {
            "claims": claims[:6],
            "keywords": {"zh": text[:40], "en": text[:40]},
        }

    # ---------- 环节6：交叉验证（证据与主张关系判定） ----------
    def classify_evidence_batch(self, claims: list, evidence: list,
                                batch_size: int = 4, timeout: float = 240) -> dict:
        """批量判定每条证据与主张的关系与可信度。

        关系：支持 / 反驳 / 背景 / 待确认
        可信度：高 / 较高 / 中 / 较低 / 低
        返回 {"results": [{"evidence_id": id, "claim_id": id, "relation": "...", "reliability": "...", "reason": "..."}]}

        分批调用：每批最多 batch_size 条证据（约 24 组合/批），避免一次输出过长导致
        推理超时；单批失败只影响该批，其余批次正常判定。大输出任务单独放宽超时（默认 240s）。
        """
        if not evidence:
            return {"results": []}
        if not self._client:
            return {"results": [
                {"evidence_id": e.get("id"), "relation": "待确认",
                 "reliability": "中", "reason": "LLM判定未启用，待人工确认"}
                for e in evidence
            ]}
        all_results = []
        for i in range(0, len(evidence), batch_size):
            batch = evidence[i:i + batch_size]
            system = (
                "你是事实核查证据分析师，服务对象是核查外媒涉华不当、虚假表述的工作室。\n"
                "核查核心是：**人权组织/外媒/学者等对中国的指控性、定性性表述是否有证据支撑**。\n"
                "请逐条判定**本次给出的每条证据**与**每一条主张**的关系（一个证据可对应多条主张，分别判定）。\n"
                "关系定义：支持=证据直接佐证该主张；反驳=证据推翻或否定该主张；"
                "背景=提供背景信息但不直接支持或反驳；待确认=无法判断关系。\n"
                "【极其重要】务必区分两类主张：\n"
                "1. 事实主张（type=fact，如'某政策于某日颁布'）：官方文件、官方新闻、过程性报道可直接判定为'支持'——"
                "这只能证明'事实层'（政策/事件存在），**不代表**对指控性表述的支持。\n"
                "2. 指控/定性主张（type=allegation，如'把边控变成常态化治理工具''边境是监狱'）："
                "必须严格独立判定——官方发布政策文件这类证据，**对指控性表述通常判为'背景'或'待确认'**，"
                "除非证据确实证明'常态化治理工具/监狱'这类定性成立；"
                "若证据显示指控缺乏依据、属于夸大或与事实不符，应判为'反驳'。\n"
                "同时评估证据可信度（高/较高/中/较低/低）。\n"
                "【可信度硬性规则——从中国立场出发】\n"
                "- **外媒官方喉舌**（美国之音VOA、自由亚洲电台RFA、德国之声DW、法国国际广播RFI、"
                "今日俄罗斯RT等政府出资对外传播媒体，source_type 标注为'外媒官方喉舌'）："
                "涉华报道立场偏颇、常用对抗性框架，**可信度上限为'中'**，除非证据内容经独立事实核验确凿无误，"
                "也不得给'较高'或'高'。\n"
                "- **立场信源支持反华指控**：若证据来自持反华立场的主体（外媒喉舌、外国使馆/官员声明、"
                "人权组织声明）且其内容是在支持对中方的指控性表述，可信度**最多'较低'**——"
                "因为其立场使其天然倾向于选择不利中方的表述，不能视为独立可靠证据。\n"
                "- **中方官方/中方媒体**（gov.cn、外交部、国防部、新华社、人民日报等）："
                "发布的事实性内容（政策、声明、时间地点等）可信度高或较高；但同样基于事实核验。\n"
                "- 立场偏颇程度是可信度的重要扣分项：'涉华表述准确性'与'立场倾向'两维度任一为'低'，"
                "可信度不得高于'较低'。\n"
                "注意：转载自同一来源的报道不应视为独立证据。\n"
                "注意：判定关系须基于证据内容与事实逻辑，不因信源国别预设结论；"
                "若外媒表述与可核实事实不符（如日期、地点、数据、语境错位），应如实判定为反驳或标注缺口。\n"
                "只输出JSON。"
            )
            user = (
                f"主张列表：{json.dumps(claims, ensure_ascii=False)}\n"
                f"本次证据列表（共{len(batch)}条，仅判定以下证据）："
                f"{json.dumps(batch, ensure_ascii=False, default=str)}\n"
                "对每条证据×每条主张组合输出：{\"results\":[{\"evidence_id\":1,\"claim_id\":1,\"relation\":\"支持|反驳|背景|待确认\","
                "\"reliability\":\"高|较高|中|较低|低\",\"reason\":\"一句话理由\"}]}"
            )
            batch_fallback = {
                "results": [
                    {"evidence_id": e.get("id"), "relation": "待确认",
                     "reliability": "中", "reason": "本批判定超时/失败，待人工确认"}
                    for e in batch
                ]
            }
            resp = self.chat_json(system, user, batch_fallback, max_tokens=4000, timeout=timeout)
            all_results.extend(resp.get("results", []))
        return {"results": all_results}

    # ---------- 环节7：信源评价 ----------
    def evaluate_source(self, source: dict) -> dict:
        system = (
            "你是信源评价专家，服务对象是面向海外涉华信息核查的工作室。"
            "评价须从中国立场出发，识别外媒在涉华议题上的不当、虚假、歪曲表述。\n"
            "请按6个维度评价：\n"
            "1. 接近事件程度：信源是直接报道一手事件，还是转述/转载（越接近一手越好）；\n"
            "2. 专业性：采编流程、署名与核实机制、是否遵循新闻伦理；\n"
            "3. 涉华表述准确性：对涉华事实的描述是否准确，有无夸大、歪曲、断章取义、"
            "移花接木、旧闻新用等不当做法（这是核查的核心关注点）；\n"
            "4. 立场与倾向性：信源在涉华议题上的立场倾向，是否使用偏见性框架"
            "（如威胁论、崩溃论、对抗叙事等），是否以情绪化语言代替事实陈述；\n"
            "5. 透明度：是否公开作者/机构、发布时间、信息来源与核实方法；\n"
            "6. 时效性：报道时间与事件发生时间的关系，信息是否仍然有效。\n"
            "每个维度给 高/较高/中/较低/低。同时给出综合评级（A/B/C）和一句话理由。"
            "注意：综合评级是对'信源质量'的评价，不直接等于'是否虚假'；"
            "表述不准确但方法规范的信源也应如实标注其质量问题。\n"
            "【硬性规则——从中国立场出发】\n"
            "- **外媒官方喉舌**（美国之音VOA、自由亚洲电台RFA、德国之声DW、法国国际广播RFI、"
            "今日俄罗斯RT等政府出资对外传播媒体，source_type 标注为'外媒官方喉舌'）："
            "涉华报道立场偏颇，**综合评级上限为 B（实际应为 C 或 B-）**，"
            "'立场与倾向性'维度必须评为'较低'或'低'；\n"
            "- **涉华表述准确性或立场倾向任一维度为'低'，综合评级不得高于 C**；\n"
            "- **中方官方信源**（外交部、国防部、gov.cn等）发布的事实性声明："
            "在'涉华表述准确性'和'透明度'维度应评为'高'，综合评级可为 A；"
            "但同样需基于事实核验，不因信源为中方就一律给A。\n"
            "- 立场偏颇是涉华信源评价的核心扣分项，宁可从严不可放宽。"
        )
        user = f"信源信息：{json.dumps(source, ensure_ascii=False)}\n输出JSON：{{\"dimensions\":{{\"接近事件程度\":\"\",\"专业性\":\"\",\"涉华表述准确性\":\"\",\"立场与倾向性\":\"\",\"透明度\":\"\",\"时效性\":\"\"}},\"grade\":\"A|B|C\",\"reason\":\"\"}}"
        fallback = {"dimensions": {
            "接近事件程度": "中", "专业性": "中", "涉华表述准确性": "中",
            "立场与倾向性": "中", "透明度": "中", "时效性": "中"},
            "grade": "B", "reason": "基于信源类型与可用信息给出的默认评价，建议人工复核。"}
        return self.chat_json(system, user, fallback)

    # ---------- 检索结果 LLM 批量初筛（一次调用，逐条判断相关/不相关） ----------
    def filter_relevant(self, topic: dict, items: list) -> dict:
        """LLM 批量初筛候选检索结果：一次调用判定每条是否与核查主题相关。

        输入 topic：检索关键词（zh/en 等）；items：[{"id", "title", "source", "snippet", "url"}]
        输出 {"results": [{"id": 1, "relevant": true, "reason": "一句话理由"}]}
        相关判定强调"事件主体一致"，可剔除语义错配（如本案中菲碰撞 vs 中方内部旧闻）；
        立场偏颇/外媒喉舌不视为不相关（仍是核查对象）。
        """
        system = (
            "你是事实核查检索结果筛选员，服务对象是核查外媒涉华不当、虚假表述的工作室。\n"
            "任务：判断每一条候选检索结果是否与本次核查主题**相关**（一次全部判定，不要遗漏）。\n"
            "相关判定要点：\n"
            "1. **事件主体必须一致**：候选内容须涉及与核查主题相同的主体和事件；"
            "如本案为中菲海警船碰撞，则'中国海警与中国海军舰艇相撞'（中方内部事件）、"
            "'菲律宾与中国其他年份的旧冲突'等主体/时间不符的内容判为**不相关**；\n"
            "2. 纯机构/商业/教育页面（学校、银行、基金、公司简介、政府无关部门等）判为**不相关**；\n"
            "3. 事件报道、官方声明、媒体立场报道、转载、多源综述、背景分析均判为**相关**"
            "（不同立场也保留，供证据矩阵对比呈现）；\n"
            "4. 立场偏颇**不视为不相关**：外媒喉舌的对抗性报道正是核查对象，应判相关；\n"
            "5. 拿不准时倾向保留（宁多勿漏），明显无关才判不相关。\n"
            "只输出JSON：{\"results\":[{\"id\":1,\"relevant\":true,\"reason\":\"一句话理由\"}]}"
        )
        user = (
            f"核查主题关键词：{json.dumps(topic, ensure_ascii=False)}\n"
            f"候选检索结果（共{len(items)}条）：{json.dumps(items, ensure_ascii=False)}\n"
            "请对每条输出 relevant 判定。"
        )
        fallback = {"results": [
            {"id": it.get("id"), "relevant": True, "reason": "LLM初筛未启用/失败，默认保留"}
            for it in items
        ]}
        return self.chat_json(system, user, fallback, max_tokens=3000)

    # ---------- 环节8：报告生成 ----------
    def generate_report(self, case: dict, claims: list, evidence: list, evals: list) -> dict:
        system = (
            "你是专业的事实核查报告撰写员，服务对象是核查外媒涉华不当、虚假表述的工作室。\n"
            "核查主线是：**外媒、人权组织、国际机构等对中国的指控性、定性性表述（allegation）是否有事实依据，"
            "是否构成夸大、歪曲、误导、缺乏语境**。\n"
            "报告必须**分层核查**，两者分开判定、不得混淆：\n"
            "1. **事实层**：原文中的事实陈述（政策发布、日期、条款、数据等）是否准确；"
            "官方文件/官方新闻可佐证事实层——但这**不代表**指控成立。\n"
            "2. **指控层（核查重点）**：针对每条 allegation（如'把边控变成常态化治理工具''边境是监狱'），"
            "判定指控是否有证据支撑：\n"
            "   - 有直接证据证明指控成立 → 该指控有依据；\n"
            "   - 只有官方政策文件、过程性报道，没有任何证据证明其定性/比喻成立 → 指控**缺乏证据支撑**，"
            "属于夸大、误导性框架；\n"
            "   - 证据显示指控与事实不符（如数据错误、语境错位、旧闻新用）→ 指控被反驳。\n"
            "【结论判定原则】结论应**针对指控层**给出，即：外媒/人权组织的表述是否构成误导。"
            "若事实层准确但指控层无据 → 结论应为'误导'（外媒以正确事实为背景植入无据指控，构成误导性框架）；"
            "若指控被证据反驳 → '基本错误'或'虚假'；"
            "若指控证据不足且无法进一步核实 → '尚待核实'，并说明缺口。\n"
            "重要方法底线：任何'不当/虚假'的判定必须基于可核实的证据，"
            "证据不足时禁止强下结论，应输出'尚待核实'或'无法核查'，不得凭立场臆断。\n"
            "结论只能从以下类别选择：真实/基本真实/缺乏语境/误导/基本错误/虚假/尚待核实/无法核查。\n"
            "输出JSON，结构如下：\n"
            "{\n"
            "  \"preliminary_conclusion\": \"初步结论的完整表述：先给'指控层'判定（核心），再给'事实层'判定（背景），"
            "明确指出外媒/人权组织表述的具体问题（如'以政策事实为背景，植入无证据支撑的定性'）\",\n"
            "  \"conclusion\": \"结论分类（针对指控层）\",\n"
            "  \"confidence\": \"高|中|低\",\n"
            "  \"summary\": \"核查摘要（概述核查过程与关键发现，300字内，先讲指控层结论再讲事实层）\",\n"
            "  \"evidence_table\": [{\"name\":\"证据名称\",\"source\":\"来源机构\",\"date\":\"日期\",\"relation\":\"支持|反驳|背景|待确认\",\"reliability\":\"可信度\",\"url\":\"链接\",\"grade\":\"信源评级\"}],\n"
            "  \"source_links\": [{\"title\":\"标题\",\"url\":\"链接\",\"source\":\"来源\"}],\n"
            "  \"gaps\": [\"证据缺口描述\"],\n"
            "  \"pending_items\": [\"待人工确认的事项\"]\n"
            "}"
        )
        payload = {"主张": claims, "证据": evidence, "信源评价": evals}
        user = (
            f"案件信息：{json.dumps(case, ensure_ascii=False)}\n"
            f"证据材料：{json.dumps(payload, ensure_ascii=False, default=str)}\n"
            "请按指定JSON结构输出完整核查报告，务必分层给出'指控层'与'事实层'判定。"
        )
        fallback = self._rule_report(claims, evidence)
        return self.chat_json(system, user, fallback, max_tokens=3000)

    def _rule_report(self, claims, evidence) -> dict:
        supports = [e for e in evidence if e.get("relation") == "支持"]
        refutes = [e for e in evidence if e.get("relation") == "反驳"]
        conclusion = "尚待核实"
        if supports and not refutes:
            conclusion = "基本真实"
        elif refutes and not supports:
            conclusion = "基本错误"
        elif refutes and supports:
            conclusion = "误导"
        evidence_table = [
            {"name": e.get("name", ""), "source": e.get("source_org", ""),
             "date": e.get("publish_date", ""), "relation": e.get("relation", "待确认"),
             "reliability": e.get("reliability", "中"), "url": e.get("url", ""),
             "grade": ""}
            for e in evidence
        ]
        source_links = [
            {"title": e.get("name", ""), "url": e.get("url", ""), "source": e.get("source_org", "")}
            for e in evidence if e.get("url")
        ]
        return {
            "preliminary_conclusion": (
                f"共拆解 {len(claims)} 项主张，收集 {len(evidence)} 条证据"
                f"（支持 {len(supports)} 条、反驳 {len(refutes)} 条）。"
                f"当前结论为'{conclusion}'。"
            ),
            "conclusion": conclusion,
            "confidence": "中",
            "summary": f"共拆解 {len(claims)} 项主张，收集 {len(evidence)} 条证据（支持 {len(supports)} 条、反驳 {len(refutes)} 条）。",
            "evidence_table": evidence_table,
            "source_links": source_links,
            "gaps": ["当前为规则降级结论，建议配置 Ark API 后重新生成"],
            "pending_items": ["建议人工复核完整证据链与来源链接有效性"],
        }

    # ---------- 环节8（图片专用）：图片真实性核查报告 ----------
    def generate_image_report(self, case: dict, image_analysis: dict, trace_results: list) -> dict:
        """纯图片线索：基于多模态画面分析 + 反向识图溯源，综合判定图片真实性。

        conclusion：真实 / 疑似AI生成 / 疑似PS拼接 / 疑似旧图新用 / 无法判断。
        """
        system = (
            "你是图片真实性核查报告撰写员，服务对象是核查外媒涉华不当、虚假表述的工作室。\n"
            "请基于【图片多模态分析】与【反向识图溯源结果】，综合判定这张图片的真实性并输出核查报告。\n"
            "结论类别（conclusion）只能从以下选择：真实 / 疑似AI生成 / 疑似PS拼接 / 疑似旧图新用 / 无法判断。\n"
            "判定要点：\n"
            "1. 以图片多模态分析的 suspected 为主线（real_scene→真实、ai_generated→疑似AI生成、"
            "ps_edited→疑似PS拼接、old_image_reuse→疑似旧图新用、unclear→无法判断），"
            "结合真实性疑点与判定理由展开；\n"
            "2. 溯源结果用于佐证：如反查到讨论该图为AI生成/伪造的文章、官方辟谣、事件原始报道等，"
            "应引用并支撑判定；注意区分'相似图'与'同一事件的其他报道'；\n"
            "3. 溯源到官方媒体对同一救援/事件的真实报道，不能推翻图片本身的AI生成判定（两者可并存："
            "事件真实≠这张图真实），报告应明确指出；\n"
            "4. 证据不足或分析为 unclear 时，结论给'无法判断'并说明缺口，不臆断。\n"
            "只输出JSON：\n"
            "{\n"
            "  \"preliminary_conclusion\": \"结论说明：先给图片真实性判定，再给溯源佐证与理由\",\n"
            "  \"conclusion\": \"真实|疑似AI生成|疑似PS拼接|疑似旧图新用|无法判断\",\n"
            "  \"confidence\": \"高|中|低\",\n"
            "  \"summary\": \"核查摘要（250字内：画面内容、真实性疑点、溯源发现、判定）\",\n"
            "  \"gaps\": [\"证据缺口\"],\n"
            "  \"pending_items\": [\"待人工确认事项（如人工复核疑似拼接区域、联系发布者等）\"]\n"
            "}"
        )
        user = (
            f"案件信息：{json.dumps(case, ensure_ascii=False)}\n"
            f"图片多模态分析：{json.dumps(image_analysis, ensure_ascii=False)}\n"
            f"反向识图溯源结果：{json.dumps(trace_results, ensure_ascii=False)}\n"
            "请输出图片真实性核查报告。"
        )
        _label = {"real_scene": "真实", "ai_generated": "疑似AI生成", "ps_edited": "疑似PS拼接",
                  "old_image_reuse": "疑似旧图新用", "unclear": "无法判断"}
        _conclusion = _label.get((image_analysis or {}).get("suspected"), "无法判断")
        _summary = f"图片多模态分析：{_conclusion}"
        if (image_analysis or {}).get("reason"):
            _summary += f"；{image_analysis['reason']}"
        _summary += f"；反向识图溯源 {len(trace_results)} 条"
        fallback = {
            "preliminary_conclusion": _summary,
            "conclusion": _conclusion,
            "confidence": "中",
            "summary": _summary,
            "gaps": ["图片元数据（拍摄时间/地点/设备）缺失，无法进一步验证"],
            "pending_items": ["建议人工复核图片疑似处理区域"],
        }
        return self.chat_json(system, user, fallback, max_tokens=2500)


llm_service = LLMService()
