# 真探 · 海外涉华信息智能核查平台

面向"真探工作室"的海外涉华信息智能核查工具（文本+图片 MVP），实现 9 环节核查主流程：

**线索接收 → 价值初筛 → 主张拆解 → 多语种检索 → 出处追踪 → 交叉验证 → 信源评价 → 报告生成 → 人工审核**

## 技术栈

| 层 | 技术 | 说明 |
|---|---|---|
| 前端 | React 18 + Vite 5 | 工作台 / 线索中心 / 核查任务 / 案件详情 / 证据库 / 历史案例 / 知识库 / 统计 |
| 后端 | Python FastAPI + SQLite | 9 环节流水线编排、REST API |
| AI | 火山引擎 Ark（豆包） | 主张拆解、关键词生成、信源评价、报告生成 |
| 搜索 | Brave Search API（可选） | 多语种联网检索 |
| 识图 | 百度识图 / TinEye（可选） | 图片出处追踪 |

## 快速启动

```bash
# 1. 配置（可选，不配置则以演示模式运行）
cd backend
copy .env.example .env    # Windows
# 编辑 .env，填入 ARK_API_KEY（火山引擎方舟）等

# 2. 一键启动（后端 8000 + 前端 5173）
start.bat
```

浏览器打开 http://localhost:5173

## 配置说明

| 环境变量 | 作用 | 不配置时 |
|---|---|---|
| `ARK_API_KEY` | LLM 主张拆解/评价/报告 | 规则降级：按句子拆分+默认评价 |
| `BRAVE_API_KEY` | 多语种联网检索 | 返回演示检索结果 |
| `BAIDU_SEARCH_*` | 反向搜图（以图搜图） | 返回演示溯源结果 |

## 9 环节说明

| # | 环节 | 实现 |
|---|---|---|
| 1 | 线索接收 | 线索中心提交文字/链接/图片，自动创建核查任务 |
| 2 | 价值初筛 | 涉华关键词命中 + 评分，决定是否进入核查 |
| 3 | 主张拆解 | LLM 拆分为事实主张/观点/情绪，提取人物/地点/时间/事件要素，生成中英关键词 |
| 4 | 多语种检索 | 中英关键词检索，返回结构化结果 |
| 5 | 出处追踪 | 反向搜图 + 链接溯源（百度识图/TinEye） |
| 6 | 交叉验证 | 整合证据矩阵，标注支持/反驳/背景，识别转载信源 |
| 7 | 信源评价 | 六维度评估 + A/B/C 评级 |
| 8 | 报告生成 | 结构化报告 + 8 类结论 + 证据缺口 |
| 9 | 人工审核 | 审核人通过/修改/退回，人工确认点勾选，留痕归档 |

## 演示数据

```bash
cd backend
python -m app.seed_demo   # 用"美日加军演"案例跑通全部 9 环节
```

## API 摘要

- `POST /api/clues` — 提交线索（multipart）
- `GET  /api/cases` — 案件列表
- `GET  /api/cases/{id}` — 案件详情
- `POST /api/cases/{id}/screening|decompose|search|trace|verify|evaluate|report|review` — 9 环节驱动
- `GET  /api/health` — 能力状态

## 目录结构

```
zhen-tan-platform/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI 入口
│   │   ├── models.py          # 数据模型（线索/案件/主张/证据/报告/审核）
│   │   ├── schemas.py         # API 序列化
│   │   ├── config.py          # 配置读取
│   │   ├── seed_demo.py       # 演示数据（9环节全流程）
│   │   ├── services/
│   │   │   ├── llm.py         # Ark LLM（含规则降级）
│   │   │   ├── search.py      # 多语种检索
│   │   │   ├── reverse_image.py  # 反向搜图
│   │   │   └── pipeline.py    # 9 环节编排
│   │   └── routers/           # API 路由
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── pages/             # 8 个页面
│       └── api/client.js      # API 客户端
└── start.bat                  # 一键启动
```
