import React, { useEffect, useState } from 'react'
import { api } from '../api/client.js'

export default function Statistics() {
  const [cases, setCases] = useState([])
  useEffect(() => { api.listCases().then(setCases).catch(() => {}) }, [])

  const done = cases.filter((c) => c.status === 'done')
  const byConclusion = {}
  cases.forEach((c) => {
    const k = c.final_conclusion || '未出结论'
    byConclusion[k] = (byConclusion[k] || 0) + 1
  })

  const stats = [
    { label: '案件总数', value: cases.length },
    { label: '进行中', value: cases.length - done.length },
    { label: '已结案', value: done.length },
    { label: '结案率', value: cases.length ? Math.round((done.length / cases.length) * 100) + '%' : '0%' },
  ]

  return (
    <div>
      <h2 style={{ fontSize: 20, marginBottom: 4 }}>数据统计</h2>
      <p style={{ color: '#6b7280', fontSize: 13, marginBottom: 20 }}>核查工作概况与结论分布</p>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 24 }}>
        {stats.map((s) => (
          <div key={s.label} style={{ background: '#fff', borderRadius: 12, padding: 20, border: '1px solid #e5e7eb' }}>
            <div style={{ fontSize: 28, fontWeight: 700, color: '#2563eb' }}>{s.value}</div>
            <div style={{ fontSize: 13, color: '#6b7280', marginTop: 4 }}>{s.label}</div>
          </div>
        ))}
      </div>

      <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #e5e7eb', padding: 18 }}>
        <div style={{ fontWeight: 600, marginBottom: 12 }}>结论分布</div>
        {Object.entries(byConclusion).map(([k, v]) => (
          <div key={k} style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
            <span style={{ fontSize: 13, width: 90 }}>{k}</span>
            <div style={{ flex: 1, background: '#f3f4f6', borderRadius: 6, height: 16, overflow: 'hidden' }}>
              <div style={{
                width: `${cases.length ? (v / cases.length) * 100 : 0}%`, height: '100%',
                background: '#2563eb', borderRadius: 6,
              }} />
            </div>
            <span style={{ fontSize: 12, color: '#6b7280', width: 30 }}>{v}</span>
          </div>
        ))}
        {cases.length === 0 && <div style={{ color: '#9ca3af', fontSize: 13 }}>暂无数据</div>}
      </div>
    </div>
  )
}
