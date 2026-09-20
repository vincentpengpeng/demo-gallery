// 构建后处理：复制 index.html 为 404.html
// GitHub Pages 对未匹配路径返回 404.html（内容仍被浏览器正常渲染），
// 使 BrowserRouter 的深层路径（如 /cases/3）刷新时不白屏/404。
import { copyFileSync, existsSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const dist = join(root, 'dist')
const index = join(dist, 'index.html')
const notFound = join(dist, '404.html')

if (!existsSync(index)) {
  console.error('[copy-404] dist/index.html 不存在，跳过')
  process.exit(0)
}
copyFileSync(index, notFound)
console.log('[copy-404] 已生成 dist/404.html（SPA 深层路由刷新兜底）')
