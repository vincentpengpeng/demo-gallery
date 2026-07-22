# 售前 Demo 展厅

一站式售前演示 Demo 集合页，用于整合所有产品能力演示，便于售前场景快速展示。

## 项目结构

```
├── index.html          # 集合页（展厅式卡片布局）
├── demos.json          # Demo 配置数据
├── DEPLOY.md           # 部署指南
└── assets/
    ├── screenshots/    # Demo 截图（按规范命名）
    └── icons/          # 图标资源
```

## 使用方式

1. 将 Demo 独立部署到公网
2. 截图并放入 `assets/screenshots/`
3. 编辑 `demos.json` 新增条目
4. 推送到 GitHub，自动部署上线

详见 [DEPLOY.md](./DEPLOY.md)。