import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 本地开发时后端在 8000 端口
// 部署时：
//   - GitHub Pages 子路径部署：base='/zhen-tan-platform/'，VITE_API_BASE=https://<render域名>/api
//   - Cloudflare Pages 等根路径部署：base='/' 即可
const base = process.env.VITE_BASE_PATH || '/'

export default defineConfig({
  base,
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/uploads': 'http://127.0.0.1:8000',
    },
  },
})
