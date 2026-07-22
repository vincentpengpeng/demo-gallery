# 部署指南

## 方案一：Cloudflare Pages（推荐）

1. 将本仓库推送到 GitHub
2. 登录 [Cloudflare Dashboard](https://dash.cloudflare.com/)
3. 进入 **Workers & Pages** → **Pages** → **连接到 Git**
4. 选择本仓库，构建配置保持默认：
   - **框架预设**: 无
   - **构建命令**: 留空
   - **构建输出目录**: `/`
5. 部署完成后，在 Pages 项目设置中绑定自定义域名：
   - 设置 → 域名 → 添加自定义域名
   - 输入你申请的免费域名（如 `demo.xxx.xyz`）
   - Cloudflare 会自动配置 DNS

## 方案二：GitHub Pages

1. 将本仓库推送到 GitHub
2. 进入仓库 **Settings** → **Pages**
3. 在 **Source** 中选择 `main` 分支，根目录 `/`
4. 等待几分钟，访问 `https://<你的用户名>.github.io/<仓库名>/`
5. 如需绑定自定义域名，在 Pages 设置中填入域名，并在 Cloudflare 添加 CNAME 记录

## 新增 Demo 流程

```
1. 将 Demo 独立部署到 Cloudflare Pages / Vercel
2. 截取 Demo 首屏，保存到 assets/screenshots/ 目录
3. 编辑 demos.json，在 "demos" 数组中新增一条
4. git add → git commit → git push
5. 自动部署，集合页即刻更新
```

## demos.json 字段说明

```json
{
  "id": "唯一标识（英文短横线）",
  "title": "Demo 名称",
  "category": "所属分类（education / culture-tourism / foundation）",
  "description": "一句话描述（建议 30-60 字）",
  "url": "Demo 部署后的公网链接",
  "screenshot": "截图路径，如 assets/screenshots/xxx.png",
  "tags": ["标签1", "标签2"],
  "status": "online / offline",
  "created": "创建时间，如 2026-06"
}
```