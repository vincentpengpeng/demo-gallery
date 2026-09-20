import React from 'react'
import { Routes, Route, NavLink, useNavigate } from 'react-router-dom'
import Dashboard from './pages/Dashboard.jsx'
import ClueCenter from './pages/ClueCenter.jsx'
import TaskList from './pages/TaskList.jsx'
import CaseDetail from './pages/CaseDetail.jsx'
import EvidenceLib from './pages/EvidenceLib.jsx'
import HistoryCases from './pages/HistoryCases.jsx'
import KnowledgeBase from './pages/KnowledgeBase.jsx'
import Statistics from './pages/Statistics.jsx'
import UserManagement from './pages/UserManagement.jsx'

const NAV = [
  { path: '/', label: '工作台', end: true },
  { path: '/clues', label: '线索中心' },
  { path: '/cases', label: '核查任务' },
  { path: '/evidence', label: '证据库' },
  { path: '/history', label: '历史案例' },
  { path: '/knowledge', label: '知识库' },
  { path: '/stats', label: '数据统计' },
  { path: '/users', label: '用户管理' },
]

export default function App() {
  const navigate = useNavigate()
  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      {/* 侧边栏 */}
      <aside style={{
        width: 220, background: '#0f1b2d', color: '#cbd5e1',
        display: 'flex', flexDirection: 'column', position: 'fixed', top: 0, bottom: 0,
      }}>
        <div style={{ padding: '20px 20px 12px' }}>
          <div style={{ color: '#fff', fontSize: 17, fontWeight: 700 }}>真探</div>
          <div style={{ fontSize: 11, color: '#64748b', marginTop: 2 }}>
            海外涉华信息智能核查平台
          </div>
        </div>
        <nav style={{ flex: 1, padding: '8px 12px' }}>
          {NAV.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.end}
              style={({ isActive }) => ({
                display: 'block', padding: '10px 14px', borderRadius: 8,
                marginBottom: 4, fontSize: 14, textDecoration: 'none',
                color: isActive ? '#fff' : '#94a3b8',
                background: isActive ? '#1d4ed8' : 'transparent',
              })}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div style={{ padding: 16, fontSize: 11, color: '#475569' }}>
          真探工作室 · 求真 · 求证 · 求实
        </div>
      </aside>

      {/* 主区域 */}
      <div style={{ flex: 1, marginLeft: 220, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        <header style={{
          height: 56, background: '#fff', borderBottom: '1px solid #e5e7eb',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '0 24px', position: 'sticky', top: 0, zIndex: 10,
        }}>
          <input
            placeholder="搜索线索、案件、关键词或链接..."
            style={{
              width: 320, padding: '8px 14px', borderRadius: 8,
              border: '1px solid #d1d5db', fontSize: 13, outline: 'none',
            }}
            onKeyDown={(e) => { if (e.key === 'Enter' && e.target.value) navigate(`/cases?q=${encodeURIComponent(e.target.value)}`) }}
          />
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <span style={{ position: 'relative', cursor: 'pointer' }} title="通知">🔔</span>
            <span style={{ fontSize: 13, color: '#374151' }}>真探工作室</span>
          </div>
        </header>
        <main style={{ flex: 1, padding: 24, minWidth: 0 }}>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/clues" element={<ClueCenter />} />
            <Route path="/cases" element={<TaskList />} />
            <Route path="/cases/:id" element={<CaseDetail />} />
            <Route path="/evidence" element={<EvidenceLib />} />
            <Route path="/history" element={<HistoryCases />} />
            <Route path="/knowledge" element={<KnowledgeBase />} />
            <Route path="/stats" element={<Statistics />} />
            <Route path="/users" element={<UserManagement />} />
          </Routes>
        </main>
      </div>
    </div>
  )
}
