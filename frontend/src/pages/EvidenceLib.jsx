import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client.js'

export default function EvidenceLib() {
  const [cases, setCases] = useState([])
  const navigate = useNavigate()
  useEffect(() => { api.listCases().then(setCases).catch(() => {}) }, [])

  const allEvidence = cases.flatMap((c) => (c.evidence || []).map((e) => ({ ...e, case_no: c.case_no, case_id: c.id })))

  return (
    <div>
      <h2 style={{ fontSize: 20, marginBottom: 4 }}>证据库</h2>
      <p style={{ color: '#6b7280', fontSize: 13, marginBottom: 20 }}>
        全部核查案件的证据条目，共 {allEvidence.length} 条
      </p>
      <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #e5e7eb', overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr style={{ background: '#f9fafb', color: '#6b7280', textAlign: 'left' }}>
              <th style={{ padding: '12px 16px' }}>案件</th>
              <th style={{ padding: '12px 16px' }}>证据名称</th>
              <th style={{ padding: '12px 16px' }}>来源机构</th>
              <th style={{ padding: '12px 16px' }}>日期</th>
              <th style={{ padding: '12px 16px' }}>关系</th>
              <th style={{ padding: '12px 16px' }}>类型</th>
            </tr>
          </thead>
          <tbody>
            {allEvidence.map((e, i) => (
              <tr key={i} style={{ borderTop: '1px solid #f3f4f6', cursor: 'pointer' }}
                onClick={() => navigate(`/cases/${e.case_id}`)}>
                <td style={{ padding: '10px 16px', color: '#2563eb' }}>{e.case_no}</td>
                <td style={{ padding: '10px 16px', maxWidth: 240, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{e.name}</td>
                <td style={{ padding: '10px 16px' }}>{e.source_org}</td>
                <td style={{ padding: '10px 16px' }}>{e.publish_date}</td>
                <td style={{ padding: '10px 16px' }}>{e.relation}</td>
                <td style={{ padding: '10px 16px' }}>{e.source_type}</td>
              </tr>
            ))}
            {allEvidence.length === 0 && <tr><td colSpan={6} style={{ padding: 24, textAlign: 'center', color: '#9ca3af' }}>暂无证据</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  )
}
