import React, { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api, STAGES } from '../api/client.js'
import ConclusionBadge from '../components/ConclusionBadge.jsx'

export default function TaskList() {
  const [cases, setCases] = useState([])
  const [filter, setFilter] = useState('all')
  const [deleting, setDeleting] = useState(null)
  const [params] = useSearchParams()
  const navigate = useNavigate()

  const load = () => api.listCases().then(setCases).catch(() => {})
  useEffect(() => { load() }, [])

  const handleDelete = async (e, c) => {
    e.stopPropagation()
    if (!window.confirm(`确定删除案件 ${c.case_no}「${c.title.slice(0, 30)}」？\n将同时删除关联的线索、主张、证据、报告，且不可恢复。`)) return
    setDeleting(c.id)
    try {
      await api.deleteCase(c.id)
      await load()
    } catch (err) {
      alert(`删除失败：${err.message}`)
    } finally {
      setDeleting(null)
    }
  }

  const q = (params.get('q') || '').toLowerCase()
  let list = cases
  if (filter === 'active') list = list.filter((c) => c.status !== 'done')
  if (filter === 'done') list = list.filter((c) => c.status === 'done')
  if (q) list = list.filter((c) => (c.title + c.case_no).toLowerCase().includes(q))

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div>
          <h2 style={{ fontSize: 20, marginBottom: 4 }}>核查任务</h2>
          <p style={{ color: '#6b7280', fontSize: 13 }}>所有核查案件，按 9 环节进度推进</p>
        </div>
        <button onClick={() => navigate('/clues')}
          style={{ padding: '10px 18px', background: '#2563eb', color: '#fff', border: 'none', borderRadius: 8, fontSize: 13, cursor: 'pointer' }}>
          + 新建线索
        </button>
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        {[['all', '全部'], ['active', '进行中'], ['done', '已结案']].map(([k, label]) => (
          <button key={k} onClick={() => setFilter(k)}
            style={{
              padding: '6px 14px', borderRadius: 16, fontSize: 13, cursor: 'pointer',
              border: '1px solid #d1d5db', background: filter === k ? '#2563eb' : '#fff',
              color: filter === k ? '#fff' : '#374151',
            }}>{label}</button>
        ))}
      </div>

      <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #e5e7eb', overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr style={{ background: '#f9fafb', color: '#6b7280', textAlign: 'left' }}>
              <th style={{ padding: '12px 16px' }}>案件编号</th>
              <th style={{ padding: '12px 16px' }}>标题</th>
              <th style={{ padding: '12px 16px' }}>环节进度</th>
              <th style={{ padding: '12px 16px' }}>优先级</th>
              <th style={{ padding: '12px 16px' }}>负责人</th>
              <th style={{ padding: '12px 16px' }}>结论</th>
              <th style={{ padding: '12px 16px' }}>状态</th>
              <th style={{ padding: '12px 16px' }}>操作</th>
            </tr>
          </thead>
          <tbody>
            {list.map((c) => (
              <tr key={c.id} onClick={() => navigate(`/cases/${c.id}`)}
                style={{ borderTop: '1px solid #f3f4f6', cursor: 'pointer' }}>
                <td style={{ padding: '12px 16px', color: '#2563eb' }}>{c.case_no}</td>
                <td style={{ padding: '12px 16px', maxWidth: 320, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{c.title}</td>
                <td style={{ padding: '12px 16px' }}>{c.stage_name}</td>
                <td style={{ padding: '12px 16px' }}>{c.priority}</td>
                <td style={{ padding: '12px 16px' }}>{c.assignee || '-'}</td>
                <td style={{ padding: '12px 16px' }}>
                  {c.final_conclusion ? <ConclusionBadge conclusion={c.final_conclusion} compact /> : '-'}
                </td>
                <td style={{ padding: '12px 16px' }}>
                  <span style={{
                    padding: '3px 10px', borderRadius: 10, fontSize: 12,
                    background: c.status === 'done' ? '#ecfdf5' : '#eff6ff',
                    color: c.status === 'done' ? '#059669' : '#2563eb',
                  }}>
                    {c.status === 'done' ? '已结案' : `第${c.stage}/9环节`}
                  </span>
                </td>
                <td style={{ padding: '12px 16px' }}>
                  <button
                    onClick={(e) => handleDelete(e, c)}
                    disabled={deleting === c.id || c.status === 'running'}
                    title={c.status === 'running' ? '自动核查中，暂不能删除' : '删除案件'}
                    style={{
                      padding: '5px 12px', borderRadius: 6, fontSize: 12, cursor: 'pointer',
                      border: '1px solid #fecaca', background: '#fef2f2', color: '#dc2626',
                      opacity: deleting === c.id ? 0.6 : 1,
                    }}>
                    {deleting === c.id ? '删除中…' : '删除'}
                  </button>
                </td>
              </tr>
            ))}
            {list.length === 0 && (
              <tr><td colSpan={8} style={{ padding: 24, textAlign: 'center', color: '#9ca3af' }}>暂无案件</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
