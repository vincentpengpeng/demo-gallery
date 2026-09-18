// API 地址：部署时通过环境变量 VITE_API_BASE 指定后端地址（如 https://zhen-tan.onrender.com）
// 本地开发默认走 vite proxy（/api → localhost:8000）
const API_BASE = (import.meta.env.VITE_API_BASE || '').replace(/\/$/, '') || '/api'

export function mediaUrl(path) {
  if (!path) return ''
  // 完整 URL（如 GitHub 图床 raw 地址 / http 链接）直接使用
  if (/^https?:\/\//i.test(path)) return path
  // 已带 /uploads 前缀的相对路径：本地开发走 vite proxy；部署拼后端地址
  const base = API_BASE === '/api' ? '' : API_BASE.replace(/\/api$/, '')
  return `${base}${path}`
}

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, options)
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`请求失败 ${res.status}: ${text.slice(0, 200)}`)
  }
  const ct = res.headers.get('content-type') || ''
  return ct.includes('application/json') ? res.json() : res.text()
}

export const api = {
  // 线索
  createClue: (formData) => request('/clues', { method: 'POST', body: formData }),
  listClues: () => request('/clues'),

  // 案件
  listCases: () => request('/cases'),
  getCase: (id) => request(`/cases/${id}`),
  deleteCase: (id) => request(`/cases/${id}`, { method: 'DELETE' }),

  // 9 环节
  screening: (id) => request(`/cases/${id}/screening`, { method: 'POST' }),
  decompose: (id) => request(`/cases/${id}/decompose`, { method: 'POST' }),
  search: (id) => request(`/cases/${id}/search`, { method: 'POST' }),
  trace: (id) => request(`/cases/${id}/trace`, { method: 'POST' }),
  verify: (id) => request(`/cases/${id}/verify`, { method: 'POST' }),
  evaluate: (id) => request(`/cases/${id}/evaluate`, { method: 'POST' }),
  report: (id) => request(`/cases/${id}/report`, { method: 'POST' }),
  review: (id, payload) => request(`/cases/${id}/review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }),
  advance: (id) => request(`/cases/${id}/advance`, { method: 'POST' }),
  auto: (id) => request(`/cases/${id}/auto`, { method: 'POST' }),

  // 健康检查
  health: () => request('/health'),

  // 多模态 OCR + 自动翻译
  ocr: (file) => {
    const fd = new FormData()
    fd.append('media', file)
    return request('/ocr', { method: 'POST', body: fd })
  },
  translate: (text) => request('/translate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: `text=${encodeURIComponent(text)}`,
  }),
}

export const STAGES = [
  { id: 1, name: '线索接收' },
  { id: 2, name: '价值初筛' },
  { id: 3, name: '主张拆解' },
  { id: 4, name: '多语种检索' },
  { id: 5, name: '出处追踪' },
  { id: 6, name: '交叉验证' },
  { id: 7, name: '信源评价' },
  { id: 8, name: '报告生成' },
  { id: 9, name: '人工审核' },
]
