# 真探·海外涉华信息智能核查平台 — 部署操作手册

> 代码已推送：`github.com/vincentpengpeng/demo-gallery` 分支 **`zhen-tan-platform`**
> 部署方式：后端 Render（免费）+ 前端 Cloudflare Pages（免费），无自定义域名

---

## 一、后端部署（Render）

### 1. 创建 Web Service
1. 登录 [render.com](https://render.com) → **New → Web Service**
2. 连接 GitHub → 选仓库 `vincentpengpeng/demo-gallery`
3. 配置：
   | 字段 | 值 |
   |---|---|
   | Branch | `zhen-tan-platform` |
   | Root Directory | `backend` |
   | Runtime | `Python 3` |
   | Build Command | `pip install -r requirements.txt` |
   | Start Command | `gunicorn app.main:app --workers 1 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT` |
   | Instance Type | Free |
4. 展开 **Advanced** → **Environment Variables**，逐项填写（值从本地 `backend/.env` 复制）：

   | Key | 值（示例） | 说明 |
   |---|---|---|
   | `ARK_API_KEY` | `ark-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx-xxxxx` | 火山方舟主 LLM key |
   | `ARK_BASE_URL` | `https://ark.cn-beijing.volces.com/api/plan/v3` | 主 LLM 地址 |
   | `ARK_MODEL` | `ark-code-latest` | 主 LLM 模型 |
   | `OCR_API_KEY` | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` | 多模态 OCR key |
   | `OCR_BASE_URL` | `https://ark.cn-beijing.volces.com/api/v3` | OCR 地址 |
   | `OCR_MODEL` | `deepseek-v4-1-flash-260910` | OCR 模型 |
   | `SERPAPI_API_KEY` | `xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` | SerpAPI 搜索+识图 |
   | `GITHUB_TOKEN` | `ghp_xxxxxxxxxxxxxxxxxxxx` | 图床上传用 |
   | `GITHUB_REPO` | `vincentpengpeng/demo-gallery` | 图床仓库 |
   | `GITHUB_BRANCH` | `master` | 图床分支 |

5. **Create Web Service**，等构建完成。
6. 记录分配的域名，形如 `https://zhen-tan-backend.onrender.com`

### 2. 验证后端
浏览器打开 `https://<你的域名>/api/health`，应看到：
```json
{"status":"ok","llm_ark":true,"search_google":true,"reverse_image":true,
 "image_host_github":true,"ocr_multimodal":true}
```

### ⚠️ 重要说明：数据持久化
- Render 免费层磁盘是**临时**的：每次重启/重新部署会清空 SQLite 数据（用户、案件、证据全丢）。
- 你已选择"接受 SQLite 丢数据"——适合演示/MVP。若要长期保存数据，后续可迁移 PostgreSQL（Render 提供免费 10GB Postgres）或付费持久磁盘（$7/月起）。
- 上传的图片走 GitHub 图床（不受影响），但线索的本地裁剪图会随重启丢失。

---

## 二、前端部署（Cloudflare Pages）

### 1. 创建 Pages 项目
1. 登录 [dash.cloudflare.com](https://dash.cloudflare.com) → **Workers & Pages → Create → Pages → Connect to Git**
2. 选仓库 `vincentpengpeng/demo-gallery`，Branch 选 `zhen-tan-platform`
3. 配置构建：
   | 字段 | 值 |
   |---|---|
   | Framework preset | `Vite` |
   | Build command | `npm run build` |
   | Build output directory | `dist` |
   | Root directory | `frontend` |
4. 展开 **Environment variables**（构建时注入）：
   | Key | 值 |
   |---|---|
   | `VITE_API_BASE` | `https://<你的后端域名>/api` |

   ⚠️ **必须带 `/api` 后缀**（后端路由全部是 `/api/*`）。例如：`https://zhen-tan-backend.onrender.com/api`

5. **Save and Deploy**，等构建完成。

### 2. 验证前端
- 打开分配的域名，如 `https://zhen-tan-platform.pages.dev`
- 工作台应显示"Ark LLM 已启用 / Google 联网搜索已启用 / GitHub 图床已配置"等绿色徽标
- 走一遍：线索中心 → 粘贴截图或外文 → 提交 → 观察 9 环节流水线

---

## 三、后续更新流程（你的协作工作流）

```bash
# 本地改代码 → 验证 → commit
git add -A
git commit -m "更新说明"
# 推送（需要凭据时用 .env 里的 GITHUB_TOKEN）
git push origin HEAD:refs/heads/zhen-tan-platform
```
推送后：Render 自动重新部署后端，Cloudflare Pages 自动重新构建前端。无需手动点 Redeploy（两者都配置了自动部署）。

---

## 四、本地开发（不受影响）

```bash
# 后端
cd backend && python -m uvicorn app.main:app --reload --port 8000
# 前端
cd frontend && npm run dev
```
本地开发无需设置 `VITE_API_BASE`（默认走 `/api` vite proxy 到 8000）。

---

## 五、已知限制
- SerpAPI 免费额度 **100 次/月**（网页搜索+识图共用），演示期请留意用量。
- 音视频线索当前按"转写后文字流程"处理（转写需自行完成）。
- 知识库页当前展示占位说明（结案归档知识库尚未落库）。
