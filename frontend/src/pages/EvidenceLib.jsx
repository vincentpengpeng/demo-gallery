import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client.js'

// 演示数据：真实案件为空时展示，便于演示效果
const DEMO_EVIDENCE = [
  { case_no: 'ZT-2026-0001', case_id: -1, name: '中国出入境管理法（2024年修订版）全文', source_org: '全国人大常委会', publish_date: '2024-06-28', relation: '支持', source_type: '中方官方', reliability: '高', url: '' },
  { case_no: 'ZT-2026-0001', case_id: -1, name: '国家移民管理局：出入境新规政策解读', source_org: '国家移民管理局', publish_date: '2026-07-05', relation: '支持', source_type: '中方官方', reliability: '高', url: '' },
  { case_no: 'ZT-2026-0001', case_id: -1, name: '环球时报社评：规范出入境就是"封闭"？无稽之谈', source_org: '环球时报', publish_date: '2026-08-02', relation: '反驳', source_type: '中方媒体', reliability: '较高', url: '' },
  { case_no: 'ZT-2026-0001', case_id: -1, name: 'CNN 报道：中国新出入境规定实施细则公布', source_org: 'CNN', publish_date: '2026-08-10', relation: '背景', source_type: '外媒官方喉舌', reliability: '中', url: '' },
  { case_no: 'ZT-2026-0001', case_id: -1, name: '人权观察（HRW）年度报告：边境管控章节', source_org: 'Human Rights Watch', publish_date: '2026-01-15', relation: '待确认', source_type: '国际组织', reliability: '中', url: '' },
  { case_no: 'ZT-2026-0002', case_id: -2, name: '外交部例行记者会实录（2026年8月14日）', source_org: '中华人民共和国外交部', publish_date: '2026-08-14', relation: '支持', source_type: '中方官方', reliability: '高', url: '' },
  { case_no: 'ZT-2026-0002', case_id: -2, name: '国防部新闻发言人回应实录', source_org: '中华人民共和国国防部', publish_date: '2026-08-15', relation: '支持', source_type: '中方官方', reliability: '高', url: '' },
  { case_no: 'ZT-2026-0002', case_id: -2, name: '路透社：中方就相关事件最新表态', source_org: 'Reuters', publish_date: '2026-08-15', relation: '背景', source_type: '国际媒体', reliability: '较高', url: '' },
  { case_no: 'ZT-2026-0002', case_id: -2, name: 'VOA 报道：渲染所谓"区域紧张"', source_org: 'VOA 美国之音', publish_date: '2026-08-16', relation: '背景', source_type: '外媒官方喉舌', reliability: '低', url: '' },
  { case_no: 'ZT-2026-0003', case_id: -3, name: '新华社：涉疆报道事实核查专题', source_org: '新华社', publish_date: '2026-07-20', relation: '支持', source_type: '中方媒体', reliability: '较高', url: '' },
  { case_no: 'ZT-2026-0003', case_id: -3, name: '新疆维吾尔自治区人民政府新闻发布会', source_org: '新疆自治区政府', publish_date: '2026-07-22', relation: '支持', source_type: '中方官方', reliability: '高', url: '' },
  { case_no: 'ZT-2026-0003', case_id: -3, name: '外媒转载对比：原始报道与转述偏差分析', source_org: 'FactCheck.org', publish_date: '2026-07-25', relation: '反驳', source_type: '事实核查机构', reliability: '高', url: '' },
]

const REL_COLORS = {
  '支持': { bg: '#ecfdf5', color: '#059669' },
  '反驳': { bg: '#fef2f2', color: '#dc2626' },
  '背景': { bg: '#eff6ff', color: '#2563eb' },
  '待确认': { bg: '#f3f4f6', color: '#6b7280' },
}

export default function EvidenceLib() {
  const [cases, setCases] = useState([])
  const [keyword, setKeyword] = useState('')
  const [relFilter, setRelFilter] = useState('all')
  const [typeFilter, setTypeFilter] = useState('all')
  const [usingDemo, setUsingDemo] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    api.listCases().then((list) => {
      setCases(list || [])
      const real = (list || []).flatMap((c) => (c.evidence || []).map((e) => ({ ...e, case_no: c.case_no, case_id: c.id })))
      setUsingDemo(real.length === 0)
    }).catch(() => {
      setUsingDemo(true)
    })
  }, [])

  const realEvidence = cases.flatMap((c) => (c.evidence || []).map((e) => ({ ...e, case_no: c.case_no, case_id: c.id })))
  const all = usingDemo ? DEMO_EVIDENCE : realEvidence

  let list = all
  if (keyword) {
    const k = keyword.toLowerCase()
    list = list.filter((e) => (e.name + (e.source_org || '') + (e.case_no || '')).toLowerCase().includes(k))
  }
  if (relFilter !== 'all') list = list.filter((e) => e.relation === relFilter)
  if (typeFilter !== 'all') list = list.filter((e) => (e.source_type || '').includes(typeFilter))

  const rels = ['all', '支持', '反驳', '背景', '待确认']
  const types = ['all', '中方官方', '中方媒体', '国际媒体', '外媒官方喉舌', '事实核查机构', '国际组织']

  return (
    <div>
      <h2 style={{ fontSize: 20, marginBottom: 4 }}>证据库</h2>
      <p style={{ color: '#6b7280', fontSize: 13, marginBottom: 16 }}>
        全部核查案件的证据条目，共 {list.length} 条
        {usingDemo && <span style={{ color: '#d97706', marginLeft: 8 }}>（当前展示演示数据）</span>}
      </p>

      {/* 筛选栏 */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}>
        <input
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          placeholder="搜索证据名称 / 来源机构 / 案件编号…"
          style={{ padding: '8px 14px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: 13, width: 280 }}
        />
        <select value={relFilter} onChange={(e) => setRelFilter(e.target.value)}
          style={{ padding: '8px 10px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: 13 }}>
          {rels.map((r) => <option key={r} value={r}>{r === 'all' ? '全部关系' : `关系：${r}`}</option>)}
        </select>
        <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}
          style={{ padding: '8px 10px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: 13 }}>
          {types.map((t) => <option key={t} value={t}>{t === 'all' ? '全部信源' : `信源：${t}`}</option>)}
        </select>
        {usingDemo && (
          <span style={{ fontSize: 12, color: '#9ca3af' }}>（演示数据：提交真实线索后自动切换为真实证据）</span>
        )}
      </div>

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
              <th style={{ padding: '12px 16px' }}>可信度</th>
            </tr>
          </thead>
          <tbody>
            {list.map((e, i) => {
              const rc = REL_COLORS[e.relation] || REL_COLORS['待确认']
              const isType = e.source_type || ''
              return (
                <tr key={i} style={{ borderTop: '1px solid #f3f4f6', cursor: e.case_id > 0 ? 'pointer' : 'default' }}
                  onClick={() => e.case_id > 0 && navigate(`/cases/${e.case_id}`)}>
                  <td style={{ padding: '10px 16px', color: e.case_id > 0 ? '#2563eb' : '#6b7280' }}>{e.case_no}</td>
                  <td style={{ padding: '10px 16px', maxWidth: 260, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{e.name}</td>
                  <td style={{ padding: '10px 16px', maxWidth: 150, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{e.source_org}</td>
                  <td style={{ padding: '10px 16px' }}>{e.publish_date}</td>
                  <td style={{ padding: '10px 16px' }}>
                    <span style={{ padding: '2px 10px', borderRadius: 10, fontSize: 12, background: rc.bg, color: rc.color }}>{e.relation}</span>
                  </td>
                  <td style={{ padding: '10px 16px' }}>
                    {isType.includes('中方官方') ? (
                      <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 8, background: '#ecfdf5', color: '#059669' }}>{isType}</span>
                    ) : isType.includes('外媒官方喉舌') ? (
                      <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 8, background: '#fef2f2', color: '#dc2626' }}>{isType}</span>
                    ) : (
                      <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 8, background: '#f3f4f6', color: '#6b7280' }}>{isType}</span>
                    )}
                  </td>
                  <td style={{ padding: '10px 16px' }}>{e.reliability}</td>
                </tr>
              )
            })}
            {list.length === 0 && <tr><td colSpan={7} style={{ padding: 24, textAlign: 'center', color: '#9ca3af' }}>暂无匹配证据</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  )
}
