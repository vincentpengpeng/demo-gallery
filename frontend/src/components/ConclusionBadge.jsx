import React from 'react'

// 结论标签：按结论类型配色（真实=绿 / 警示=橙 / 误导虚假=红），含义提示悬浮显示
export const CONCLUSION_STYLE = {
  '真实': { bg: '#ecfdf5', color: '#059669', icon: '✓', tip: '结论属实' },
  '基本真实': { bg: '#ecfdf5', color: '#059669', icon: '✓', tip: '基本属实' },
  '缺乏语境': { bg: '#fffbeb', color: '#d97706', icon: '!', tip: '事实存疑，缺乏背景语境' },
  '误导': { bg: '#fef2f2', color: '#dc2626', icon: '✕', tip: '表述具有误导性' },
  '基本错误': { bg: '#fef2f2', color: '#dc2626', icon: '✕', tip: '基本错误' },
  '虚假': { bg: '#fef2f2', color: '#dc2626', icon: '✕', tip: '虚假' },
  '尚待核实': { bg: '#f8fafc', color: '#64748b', icon: '?', tip: '尚待进一步核实' },
  '无法核查': { bg: '#f8fafc', color: '#64748b', icon: '?', tip: '现有证据无法核查' },
}
const DEFAULT_CONCLUSION_STYLE = { bg: '#eff6ff', color: '#2563eb', icon: '•', tip: '' }

export default function ConclusionBadge({ conclusion, compact = false }) {
  const st = CONCLUSION_STYLE[conclusion] || DEFAULT_CONCLUSION_STYLE
  return (
    <span title={st.tip || conclusion} style={{
      display: 'inline-flex', alignItems: 'center', gap: compact ? 3 : 6,
      fontSize: compact ? 12 : 14, fontWeight: 700, padding: compact ? '3px 10px' : '5px 16px',
      borderRadius: 10, background: st.bg, color: st.color,
      border: `1px solid ${st.color}33`, whiteSpace: 'nowrap',
    }}>
      <span style={{ fontSize: compact ? 11 : 13, fontWeight: 800 }}>{st.icon}</span>
      {conclusion || '未定'}
    </span>
  )
}
