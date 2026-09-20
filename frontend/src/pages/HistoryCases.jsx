import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client.js'
import ConclusionBadge from '../components/ConclusionBadge.jsx'

export default function HistoryCases() {
  const [cases, setCases] = useState([])
  const navigate = useNavigate()
  useEffect(() => { api.listCases().then(setCases).catch(() => {}) }, [])

  const done = cases.filter((c) => c.status === 'done')

  return (
    <div>
      <h2 style={{ fontSize: 20, marginBottom: 4 }}>历史案例</h2>
      <p style={{ color: '#6b7280', fontSize: 13, marginBottom: 20 }}>
        已结案案例，共 {done.length} 个，可沉淀为知识库教学案例
      </p>
      {done.length === 0 && (
        <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: 24, color: '#9ca3af', fontSize: 13 }}>
          暂无已结案案例。完成人工审核的案件会自动归档到这里。
        </div>
      )}
      {done.map((c) => (
        <div key={c.id} onClick={() => navigate(`/cases/${c.id}`)}
          style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: 16, marginBottom: 12, cursor: 'pointer' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: 14, fontWeight: 600 }}>{c.case_no} · {c.title}</span>
            {c.final_conclusion
              ? <ConclusionBadge conclusion={c.final_conclusion} compact />
              : <span style={{ fontSize: 12, color: '#059669', background: '#ecfdf5', padding: '3px 12px', borderRadius: 10 }}>已结案</span>}
          </div>
          <div style={{ fontSize: 12, color: '#6b7280', marginTop: 6 }}>
            负责人 {c.assignee || '-'} · 创建时间 {c.created_at ? c.created_at.slice(0, 10) : '-'}
          </div>
        </div>
      ))}
    </div>
  )
}
