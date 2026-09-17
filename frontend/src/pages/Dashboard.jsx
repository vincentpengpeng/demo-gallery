import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client.js'

export default function Dashboard() {
  const [cases, setCases] = useState([])
  const [clues, setClues] = useState([])
  const [health, setHealth] = useState(null)
  const navigate = useNavigate()

  useEffect(() => {
    api.listCases().then(setCases).catch(() => {})
    api.listClues().then(setClues).catch(() => {})
    api.health().then(setHealth).catch(() => {})
  }, [])

  const done = cases.filter((c) => c.status === 'done').length
  const active = cases.length - done

  const cards = [
    { label: '进行中核查', value: active, color: '#2563eb' },
    { label: '已结案', value: done, color: '#059669' },
    { label: '累计线索', value: clues.length, color: '#d97706' },
    { label: '案件总数', value: cases.length, color: '#7c3aed' },
  ]

  return (
    <div>
      <h2 style={{ fontSize: 20, marginBottom: 4 }}>工作台</h2>
      <p style={{ color: '#6b7280', fontSize: 13, marginBottom: 20 }}>
        快速发起核查，追踪进行中的任务
      </p>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 24 }}>
        {cards.map((c) => (
          <div key={c.label} style={{ background: '#fff', borderRadius: 12, padding: 20, border: '1px solid #e5e7eb' }}>
            <div style={{ fontSize: 28, fontWeight: 700, color: c.color }}>{c.value}</div>
            <div style={{ fontSize: 13, color: '#6b7280', marginTop: 4 }}>{c.label}</div>
          </div>
        ))}
      </div>

      {health && (
        <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: '14px 18px', marginBottom: 24, fontSize: 13, color: '#374151' }}>
          能力状态：
          {health.llm_ark ? <Badge ok>Ark LLM 已启用（{health.llm_model || ''}）</Badge> : <Badge>LLM 未配置</Badge>}
          {health.search_google ? <Badge ok>Google 联网搜索已启用</Badge> : <Badge>搜索未配置</Badge>}
          {health.reverse_image ? <Badge ok>反向搜图已启用</Badge> : <Badge>识图未配置</Badge>}
          {health.image_host_github ? <Badge ok>GitHub 图床已配置</Badge> : <Badge>图床未配置</Badge>}
          <span style={{ color: '#9ca3af' }}>
            （全部能力均为真实数据；未配置的能力会在对应环节明确报错提示，不会返回演示数据）
          </span>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 16 }}>
        <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #e5e7eb', padding: 18 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <span style={{ fontWeight: 600 }}>待处理任务</span>
            <button onClick={() => navigate('/cases')} style={{ fontSize: 12, color: '#2563eb', background: 'none', border: 'none', cursor: 'pointer' }}>
              查看全部 →
            </button>
          </div>
          {cases.slice(0, 6).map((c) => (
            <div key={c.id} onClick={() => navigate(`/cases/${c.id}`)}
              style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 0', borderBottom: '1px solid #f3f4f6', cursor: 'pointer' }}>
              <span style={{ fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '60%' }}>
                {c.case_no} · {c.title}
              </span>
              <span style={{ fontSize: 12, color: '#6b7280' }}>{c.stage_name}</span>
            </div>
          ))}
          {cases.length === 0 && <div style={{ color: '#9ca3af', fontSize: 13, padding: 12 }}>暂无任务，去线索中心发起核查</div>}
        </div>

        <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #e5e7eb', padding: 18 }}>
          <div style={{ fontWeight: 600, marginBottom: 12 }}>快捷发起核查</div>
          <button onClick={() => navigate('/clues')}
            style={{ width: '100%', padding: 12, background: '#2563eb', color: '#fff', border: 'none', borderRadius: 8, fontSize: 14, cursor: 'pointer' }}>
            新建核查线索
          </button>
          <div style={{ marginTop: 12, fontSize: 12, color: '#6b7280', lineHeight: 1.8 }}>
            支持提交：文字内容 / 网页链接 / 截图 / 图片
            <br />音视频内容当前以转写后文字流程处理
          </div>
        </div>
      </div>
    </div>
  )
}

function Badge({ children, ok }) {
  return (
    <span style={{
      display: 'inline-block', marginLeft: 8, padding: '2px 10px', borderRadius: 10,
      fontSize: 12, background: ok ? '#ecfdf5' : '#fef3c7', color: ok ? '#059669' : '#b45309',
    }}>{children}</span>
  )
}
